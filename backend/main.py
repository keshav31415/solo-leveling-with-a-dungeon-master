import os
from dotenv import load_dotenv

# Load env vars FIRST — LangSmith and Groq both read from os.environ at init time
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

from fastapi import FastAPI, HTTPException, BackgroundTasks
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
from agents.prompts import CHRONICLE_SYSTEM_PROMPT, PROMOTION_SYSTEM_PROMPT, NPC_MEMORY_SYSTEM_PROMPT
from agents.schemas import parse_scene_chronicle, parse_promotion_decision, NPCMemoryEntry

memory   = MemoryStore()
memory.seed_lore_if_empty()
director = DirectorAgent(memory)
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

    instructions = dict(current_director_instructions)

    if action.action_type == "director_event":
        instructions["director_event"] = director.get_director_event(action.target or "")

    return dm.handle_action(state.model_dump(), instructions, action.model_dump())


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

    # 3. Generate NPC memory summaries for each NPC that had interactions
    npc_ids = memory.get_npcs_with_interactions()
    for npc_id in npc_ids:
        buf = memory.get_dialogue_buffer(npc_id)
        if not buf.recent_turns and not buf.scene_summary:
            continue

        buf_lines = []
        if buf.scene_summary:
            buf_lines.append(f"[Earlier conversation summary]: {buf.scene_summary}")
        for turn in buf.recent_turns:
            if turn.jinwoo_says: buf_lines.append(f"Jinwoo says: \"{turn.jinwoo_says}\"")
            if turn.jinwoo_does: buf_lines.append(f"Jinwoo does: *{turn.jinwoo_does}*")
            buf_lines.append(f"{npc_id} responds: {turn.response}")

        npc_memory_prompt = f"""NPC: {npc_id}
Scene: {scene_id}

Dialogue this scene:
{chr(10).join(buf_lines)}

Events witnessed together: {runtime.events_fired}

Summarize what this NPC will remember."""

        raw_npc = generate_json(NPC_MEMORY_SYSTEM_PROMPT, npc_memory_prompt)
        delta   = memory.compute_relationship_delta(npc_id)

        entry = NPCMemoryEntry(
            npc_id             = npc_id,
            scene_id           = scene_id,
            key_exchanges      = raw_npc.get("key_exchanges", []),
            relationship_delta = delta,
            shared_events      = runtime.events_fired,
            emotional_state    = raw_npc.get("emotional_state", ""),
        )
        memory.save_npc_memory(entry)

    # 4. Archive chronicle and clear runtime
    memory.archive_chronicle(chronicle)
    memory.reset_runtime(new_scene_id="")

    return {
        "status":    "Scene archived.",
        "chronicle": chronicle.model_dump(),
        "promoted":  [c.model_dump() for c in decision.promote] if decision else [],
    }


@app.post("/api/reset")
def reset_memory(background_tasks: BackgroundTasks):
    """Full reset — wipes DB, reseeds lore, force-regenerates scene plan."""
    memory.full_reset()
    memory.snapshot_relationships()
    background_tasks.add_task(lambda: director.generate_scene_plan(force=True))
    return {"status": "ok", "message": "Database cleared. Scene plan generating."}


@app.post("/api/force_reset")
def force_reset(background_tasks: BackgroundTasks):
    """Hard reset — reseeds lore facts, clears all memory, force-regenerates scene plan."""
    memory.reseed_lore()
    memory.reset()
    memory.snapshot_relationships()
    background_tasks.add_task(lambda: director.generate_scene_plan(force=True))
    return {"status": "ok", "message": "Lore reseeded. Memory cleared. Scene plan force-regenerating."}


@app.get("/api/scene_plan")
def get_scene_plan():
    """Returns the current scene plan generated by the Director."""
    plan = director.get_scene_plan()
    if not plan:
        return {"events": []}
    return {"events": [e.model_dump() for e in plan.events]}
