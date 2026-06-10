from pydantic import BaseModel
from typing import Optional, Dict, List, Literal, Any
import logging

logger = logging.getLogger(__name__)

INANIMATE_OBJECTS   = {"stone_tablet", "giant_statue", "entrance_door", "god_statue"}
EVENTS_REQUIRING_JS = {"trap_springs"}

# Fallback movement directives used when a critical event omits them
FALLBACK_MOVEMENT_DIRECTIVES: Dict[str, List[Dict]] = {
    "trap_springs": [
        {"npc_id": "joohee",      "behavior": "flee", "flee_from": "giant_statue", "step_cooldown": 8},
        {"npc_id": "song_chiyul", "behavior": "flee", "flee_from": "giant_statue", "step_cooldown": 10},
        {"npc_id": "mr_park",     "behavior": "flee", "flee_from": "giant_statue", "step_cooldown": 10},
        {"npc_id": "mr_kim",      "behavior": "flee", "flee_from": "giant_statue", "step_cooldown": 10},
    ],
}

# Fallback game_actions used if Call 1 omits them for a critical event.
FALLBACK_GAME_ACTIONS: Dict[str, List[Dict]] = {
    "trap_springs": [
        {"type": "shake_screen",     "params": {"intensity": 10, "duration_ms": 500}},
        {"type": "set_entity_state", "params": {"entity_id": "entrance_door", "state": "closed"}},
    ],
}

# ── Ephemeral ──────────────────────────────────────────────────────────────────

class DialogueTurn(BaseModel):
    jinwoo_says: str = ""
    jinwoo_does: str = ""
    response:    str

class NPCDialogueBuffer(BaseModel):
    scene_summary: str              = ""   # LLM-compressed older exchanges
    recent_turns:  List[DialogueTurn] = [] # last N verbatim turns
    total_turns:   int              = 0    # lifetime counter for this scene

# ── Memory candidates ──────────────────────────────────────────────────────────

class MemoryCandidate(BaseModel):
    fact:         str
    category:     Literal["world", "relationship", "knowledge", "plot", "death", "mystery", "quest"]
    npc_involved: Optional[str] = None

# ── Level 1: Runtime Memory ────────────────────────────────────────────────────

class RelationshipState(BaseModel):
    trust:   int = 50
    fear:    int = 0
    respect: int = 50

class RuntimeMemory(BaseModel):
    scene_id:          str                          = ""
    world_state:       Dict[str, Any]               = {}
    relationships:     Dict[str, RelationshipState] = {}
    knowledge:         List[str]                    = []
    events_fired:      List[str]                    = []
    candidates:        List[MemoryCandidate]        = []
    current_situation: str                          = ""

# ── Level 2: Scene Chronicle ───────────────────────────────────────────────────

class SceneChronicle(BaseModel):
    scene_id:             str
    summary:              str
    major_events:         List[str] = []
    relationship_changes: List[str] = []
    knowledge_gained:     List[str] = []
    character_deaths:     List[str] = []
    mysteries_revealed:   List[str] = []

# ── Level 2.5: NPC Memory ─────────────────────────────────────────────────────

class NPCMemoryEntry(BaseModel):
    npc_id:             str
    scene_id:           str
    key_exchanges:      List[str]      = []   # 3-5 significant dialogue moments (LLM-summarized)
    relationship_delta: Dict[str, int] = {}   # {trust: +12, fear: -5, respect: +3}
    shared_events:      List[str]      = []   # director event IDs this NPC witnessed
    emotional_state:    str            = ""   # how NPC felt at scene end

# ── Lore facts ────────────────────────────────────────────────────────────────

class LoreFact(BaseModel):
    id:                  str
    fact:                str
    category:            str
    scene_relevance:     List[str] = []
    characters_involved: List[str] = []
    entities_involved:   List[str] = []
    tier:                str        # mandatory | structural | contextual
    temporal_status:     str = "always_true"
    superseded:          bool = False
    superseded_by:       Optional[str] = None

# ── Level 3: Story Canon ───────────────────────────────────────────────────────

class CanonFact(BaseModel):
    fact:         str
    category:     str
    scene_origin: str

class StoryCanon(BaseModel):
    facts: List[CanonFact] = []

# ── Game actions (Call 1 → Call 2 bridge) ─────────────────────────────────────

class GameAction(BaseModel):
    type:   str                  # e.g. "beam", "glow", "shake_screen", "set_entity_state"
    params: Dict[str, Any] = {}  # type-specific parameters

# ── NPC Movement Directives ────────────────────────────────────────────────────

class NPCMovementDirective(BaseModel):
    npc_id:        str
    behavior:      Literal["idle", "wander", "flee", "seek", "patrol"]
    step_cooldown: Optional[int]             = None   # frames between steps
    target:        Optional[str]             = None   # entity_id (seek / battle)
    flee_from:     Optional[str]             = None   # entity_id (flee / battle)
    wander_radius: Optional[int]             = None
    orbit_radius:  Optional[int]             = None
    waypoints:     Optional[List[Dict[str, int]]] = None  # [{x, y}, ...]

# ── Director scene plan ────────────────────────────────────────────────────────

class PlannedEvent(BaseModel):
    id:            str
    description:   str                    # director's note for the DM
    trigger_type:  Literal["auto", "position", "interact", "chain", "action_count"]
    trigger_value: Optional[str]  = None  # depends on type (see below)
    delay_ms:      Optional[int]  = None  # for trigger_type="auto"
    # trigger_value semantics:
    #   position     → "player.gridY < 30"
    #   interact     → entity_id string e.g. "stone_tablet"
    #   chain        → event_id to chain after e.g. "commandments"
    #   action_count → number as string e.g. "5"
    #   auto         → null (use delay_ms instead)

class ScenePlan(BaseModel):
    scene_id: str
    events:   List[PlannedEvent] = []

# ── Call 1: Narrative response ─────────────────────────────────────────────────

class NarrativeResponse(BaseModel):
    narrative:               str
    speaker:                 str
    new_situation:           Optional[str]                        = None
    new_entity_states:       Optional[Dict[str, str]]             = None
    memory_candidates:       Optional[List[MemoryCandidate]]      = None
    game_actions:            Optional[List[GameAction]]           = None
    npc_movement_directives: Optional[List[NPCMovementDirective]] = None

# ── Call 2: JS generation response ────────────────────────────────────────────

class JSResponse(BaseModel):
    js: str = ""

# ── Director response ──────────────────────────────────────────────────────────

class TriggerDefinition(BaseModel):
    id:        str
    condition: str
    event:     str

class DirectorResponse(BaseModel):
    event_queue: List[str]               = []
    triggers:    List[TriggerDefinition] = []

# ── Scene end responses ────────────────────────────────────────────────────────

class PromotionDecision(BaseModel):
    promote: List[MemoryCandidate] = []
    discard: List[MemoryCandidate] = []

# ── Validation helpers ─────────────────────────────────────────────────────────

_VALID_BEHAVIORS = {"idle", "wander", "flee", "seek", "patrol"}

def _sanitize_movement_directives(raw: dict) -> None:
    directives = raw.get("npc_movement_directives")
    if not isinstance(directives, list):
        return
    filtered = [d for d in directives if isinstance(d, dict) and d.get("behavior") in _VALID_BEHAVIORS]
    if len(filtered) != len(directives):
        dropped = [d.get("behavior") for d in directives if d not in filtered]
        logger.warning("Dropped invalid npc_movement_directives with unknown behaviors: %s", dropped)
    raw["npc_movement_directives"] = filtered

def parse_narrative_response(raw: dict, action_type: str, target: str = "") -> NarrativeResponse:
    _sanitize_movement_directives(raw)
    response = NarrativeResponse.model_validate(raw)

    if action_type == "director_event":
        if not response.new_situation:
            logger.warning("director_event '%s' returned no new_situation.", target)
        if target in EVENTS_REQUIRING_JS and not response.game_actions:
            fallback = FALLBACK_GAME_ACTIONS.get(target)
            if fallback:
                logger.warning("director_event '%s' returned no game_actions — using fallback.", target)
                response.game_actions = [GameAction.model_validate(a) for a in fallback]
        if not response.npc_movement_directives:
            fallback_mv = FALLBACK_MOVEMENT_DIRECTIVES.get(target)
            if fallback_mv:
                logger.warning("director_event '%s' returned no npc_movement_directives — using fallback.", target)
                response.npc_movement_directives = [NPCMovementDirective.model_validate(d) for d in fallback_mv]
    elif action_type == "interact" and target in INANIMATE_OBJECTS:
        if not response.new_situation:
            logger.warning("Object interaction '%s' returned no new_situation.", target)

    return response

def parse_js_response(raw: dict) -> JSResponse:
    return JSResponse.model_validate(raw)

def parse_director_response(raw: dict) -> DirectorResponse:
    return DirectorResponse.model_validate(raw)

def parse_scene_chronicle(raw: dict, scene_id: str) -> SceneChronicle:
    raw.setdefault("scene_id", scene_id)
    return SceneChronicle.model_validate(raw)

def parse_promotion_decision(raw: dict) -> PromotionDecision:
    return PromotionDecision.model_validate(raw)
