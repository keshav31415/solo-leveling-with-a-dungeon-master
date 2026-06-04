import json
import asyncio
import yaml
import random
import os
import sys
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# LangChain Imports
from langchain_google_genai import ChatGoogleGenerativeAI

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Using the verified model from your diagnostic
MODEL_ID = "models/gemini-2.5-flash" 
DB_FILE = "pro_solo_leveling_db.json"
CONFIG_FILE = "world_config.yaml"

# --- SCHEMAS ---

class CharacterSchema(BaseModel):
    character_id: str
    name: str
    role: str
    hunter_rank: str
    affiliation: str = Field(default="Independent")
    disposition: str
    secret_goal: str

class LocationSchema(BaseModel):
    location_id: str
    name: str
    danger_level: str
    description: str
    boss_entity: Optional[str]
    exits: Dict[str, str]

class QuestSchema(BaseModel):
    quest_id: str
    title: str
    goal: str
    success_condition: str
    reward_on_completion: str

class ItemSchema(BaseModel):
    item_id: str
    name: str
    grade: str = Field(description="E to S Rank, or Unique")
    item_type: str = Field(description="Weapon, Armor, Consumable, or Key Item")
    description: str
    effect: str = Field(description="Magical properties or stat buffs")

# --- LLM SETUP ---

llm = ChatGoogleGenerativeAI(
    model=MODEL_ID,
    google_api_key=API_KEY,
    temperature=0.2,
    transport="rest"
)

async def call_llm_structured(prompt_text: str, schema: Any) -> Any:
    """Helper for structured generation with Hard Stop for Daily Quota."""
    structured_llm = llm.with_structured_output(schema)
    
    try:
        result = await structured_llm.ainvoke(prompt_text)
        return result.model_dump() if hasattr(result, 'model_dump') else result
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "resource_exhausted" in error_msg:
            if "daily" in error_msg:
                print("\n🚨 CRITICAL: Daily Quota reached. Stopping script.")
                sys.exit(1)
            else:
                print(f"\n⚠️ RPM Limit hit. Suggested wait: {error_msg}")
                # We return None so the orchestrator can wait and retry or move on
                return "RETRY"
        print(f"❌ Error: {e}")
        return None

# --- CORE UTILITIES ---

def load_db():
    """Load existing data and verify category keys."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure all categories exist in the dict
                for cat in ["locations", "characters", "quests", "items"]:
                    if cat not in data: data[cat] = []
                return data
        except Exception as e:
            print(f"⚠️ Could not load {DB_FILE}: {e}")
    return {"locations": [], "characters": [], "quests": [], "items": []}

async def generate_entry(category: str, metadata: Dict):
    """Router for generating entries based on category."""
    item_id = metadata.get('id')
    name = metadata.get('name', item_id)
    notes = metadata.get('notes', 'Solo Leveling Season 1 context.')

    print(f"  -> Seeding NEW {category[:-1]}: {item_id}")

    prompts = {
        "locations": f"Define Solo Leveling location '{name}' (ID: {item_id}). Context: {notes}. Describe its atmosphere, exits, and potential boss.",
        "characters": f"Define Solo Leveling character '{name}' (ID: {item_id}). Context: {notes}. Define their hunter rank, role, and secret goal.",
        "quests": f"Define Solo Leveling quest '{item_id}'. Context: {notes}. Define cinematic goals and success conditions.",
        "items": f"Define Solo Leveling item '{name}' (ID: {item_id}). Context: {notes}. Define its Grade, Type, and magical effects."
    }
    
    schemas = {
        "locations": LocationSchema,
        "characters": CharacterSchema,
        "quests": QuestSchema,
        "items": ItemSchema
    }
    
    return await call_llm_structured(prompts[category], schemas[category])

# --- MAIN ORCHESTRATOR ---

async def run_pro_pipeline():
    if not API_KEY:
        print("❌ API_KEY not found in Secrets.")
        return

    if not os.path.exists(CONFIG_FILE):
        print(f"❌ {CONFIG_FILE} not found. Create your YAML first.")
        return

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    db = load_db()
    
    # Map YAML categories to JSON Schema primary keys
    cat_map = {
        "locations": "location_id",
        "characters": "character_id",
        "quests": "quest_id",
        "items": "item_id"
    }

    # SAFE_DELAY: 15 seconds ensures we stay well within the 20 RPM limit (which is 3s/req)
    # This provides a massive buffer for network latency and burst protection.
    SAFE_DELAY = 15.0 

    for cat, id_field in cat_map.items():
        # Get existing IDs from the current JSON file
        existing_ids = {item[id_field] for item in db.get(cat, []) if id_field in item}
        
        yaml_entries = config.get(cat, [])
        if not yaml_entries: continue

        print(f"\n--- Checking {cat.upper()} ---")
        
        for entry in yaml_entries:
            y_id = entry['id'] if isinstance(entry, dict) else entry
            
            # INCREMENTAL CHECK: Skip if ID already exists
            if y_id in existing_ids:
                print(f"  (skip) {y_id} is already in the database.")
                continue

            # API CALL FOR NEW ENTRY
            metadata = entry if isinstance(entry, dict) else {"id": entry}
            result = await generate_entry(cat, metadata)
            
            if result == "RETRY":
                # Wait 30s on a 429 and try this specific item one more time
                print("  ⏳ Waiting 30s for quota reset...")
                await asyncio.sleep(30)
                result = await generate_entry(cat, metadata)

            if result and result != "RETRY":
                db[cat].append(result)
                # ATOMIC SAVE: Save after every successful generation
                with open(DB_FILE, 'w', encoding='utf-8') as f:
                    json.dump(db, f, indent=4)
                print(f"  ✅ Saved {y_id} to {DB_FILE}")
                
                # PACE CONTROL: Sleep between calls
                await asyncio.sleep(SAFE_DELAY + random.uniform(0, 2))
            else:
                print(f"  ❌ Failed to generate {y_id}. Moving to next.")

    print(f"\n✨ Sync Process Complete. Final DB is in {DB_FILE}")

if __name__ == "__main__":
    try:
        asyncio.run(run_pro_pipeline())
    except SystemExit:
        print("\n🛑 Pipeline halted by Quota Monitor.")
    except KeyboardInterrupt:
        print("\n🛑 Pipeline halted by user.")