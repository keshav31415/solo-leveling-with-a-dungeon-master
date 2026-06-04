import os
from dotenv import load_dotenv

# Load env vars FIRST — LangSmith and Groq both read from os.environ at init time
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

app = FastAPI(title="Solo Leveling AI RPG Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ─────────────────────────────────────────────────────────────

class PlayerAction(BaseModel):
    action_type: str
    target: Optional[str] = None
    context: Dict[str, Any] = {}

class GameState(BaseModel):
    scene_id: str
    player_stats: Dict[str, Any]
    entity_states: Dict[str, Any]
    event_queue: List[str] = []
    scene_state: Dict[str, Any] = {}
    sandbox_tracking: Dict[str, Any] = {}
    recent_history: List[str] = []

# ── Agents & memory ────────────────────────────────────────────────────────────

from agents.director import DirectorAgent
from agents.dm import DMAgent
from agents.memory import MemoryStore
from agents.llm import generate_json
from agents.prompts import CHRONICLE_SYSTEM_PROMPT, PROMOTION_SYSTEM_PROMPT
from agents.schemas import parse_scene_chronicle, parse_promotion_decision

memory   = MemoryStore()
director = DirectorAgent()
dm       = DMAgent(memory)

current_director_instructions: Dict[str, Any] = {
    "event_queue": [],
    "triggers": [],
}

# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Solo Leveling RPG Engine is running."}


@app.post("/api/action")
def handle_action(action: PlayerAction, state: GameState):
    global current_director_instructions

    if action.action_type == "evaluate_scene":
        instructions = director.evaluate_scene(state.model_dump(), [action.model_dump()])
        current_director_instructions = instructions
        return {"status": "Scene evaluated", "instructions": instructions}

    return dm.handle_action(state.model_dump(), current_director_instructions, action.model_dump())


@app.post("/api/end_scene")
def end_scene():
    """
    Called when a scene finishes. Generates a Scene Chronicle, runs Director
    promotion, archives the chronicle, updates Story Canon, then clears runtime.
    """
    runtime = memory.get_runtime_snapshot()
    scene_id = runtime.scene_id

    if not runtime.events_fired and not runtime.knowledge:
        raise HTTPException(status_code=400, detail="No scene data to archive.")

    # 1. Generate Scene Chronicle
    chronicle_prompt = f"""Scene ID: {scene_id}

Events fired: {runtime.events_fired}
World state: {runtime.world_state}
Party knowledge: {runtime.knowledge}
Relationships: { {k: v.model_dump() for k, v in runtime.relationships.items()} }
Current situation: {runtime.current_situation}
Memory candidates proposed: {[c.model_dump() for c in runtime.candidates]}

Generate the Scene Chronicle."""

    raw_chronicle = generate_json(CHRONICLE_SYSTEM_PROMPT, chronicle_prompt)
    chronicle = parse_scene_chronicle(raw_chronicle, scene_id)

    # 2. Director decides which candidates to promote to Story Canon
    if runtime.candidates:
        promotion_prompt = f"""Scene ID: {scene_id}

Memory candidates from this scene:
{[c.model_dump() for c in runtime.candidates]}

Decide which to promote to Story Canon."""

        raw_promotion = generate_json(PROMOTION_SYSTEM_PROMPT, promotion_prompt)
        decision = parse_promotion_decision(raw_promotion)
        memory.promote_to_canon(decision.promote, scene_id)
    else:
        decision = None

    # 3. Archive chronicle and clear runtime
    memory.archive_chronicle(chronicle)
    memory.reset_runtime(new_scene_id="")

    return {
        "status":    "Scene archived.",
        "chronicle": chronicle.model_dump(),
        "promoted":  [c.model_dump() for c in decision.promote] if decision else [],
    }


@app.post("/api/reset")
def reset_memory():
    """Full reset — clears all memory for a new game."""
    memory.reset()
    return {"status": "ok", "message": "Memory cleared."}
