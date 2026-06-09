import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any

from .schemas import (
    RuntimeMemory, SceneChronicle,
    RelationshipState, MemoryCandidate,
    DialogueTurn, NPCMemoryEntry,
)
from .db import get_session, init_db, RuntimeMemoryRow, SceneChronicleRow, StoryCanonRow, NPCMemoryRow

_MAX_CANDIDATES = 100
_BUFFER_SIZE    = 3

_EVENT_WORLD_EFFECTS: Dict[str, Dict[str, Any]] = {
    "chamber_entered": {"chamber_entered": True},
    "joohee_terror":   {"joohee_terror_occurred": True},
    "commandments":    {"commandments_read": True},
    "trap_springs":    {"entrance_door": "closed", "trap_sprung": True},
}

_SCENE_ID = "double_dungeon"


class MemoryStore:
    def __init__(self):
        init_db()
        self._runtime = self._load_runtime()
        self._buffer: Dict[str, List[DialogueTurn]] = {}
        # Snapshot of relationship values at scene start — used to compute delta at scene end
        self._relationship_start: Dict[str, Dict[str, int]] = {}

    # ── Dialogue buffer (ephemeral, never persisted) ───────────────────────────

    def add_dialogue_turn(self, npc_id: str, turn: DialogueTurn) -> None:
        buf = self._buffer.setdefault(npc_id, [])
        buf.append(turn)
        if len(buf) > _BUFFER_SIZE:
            self._buffer[npc_id] = buf[-_BUFFER_SIZE:]

    def get_dialogue_buffer(self, npc_id: str) -> List[DialogueTurn]:
        return self._buffer.get(npc_id, [])

    # ── World state ────────────────────────────────────────────────────────────

    def update_world_state(self, updates: Dict[str, Any]) -> None:
        self._runtime.world_state.update(updates)
        self._save_runtime()

    def on_event_fired(self, event_name: str) -> None:
        if event_name not in self._runtime.events_fired:
            self._runtime.events_fired.append(event_name)
        effects = _EVENT_WORLD_EFFECTS.get(event_name, {})
        if effects:
            self._runtime.world_state.update(effects)
        self._save_runtime()

    # ── Relationships ──────────────────────────────────────────────────────────

    def get_relationship(self, npc_id: str) -> RelationshipState:
        if npc_id not in self._runtime.relationships:
            self._runtime.relationships[npc_id] = RelationshipState()
        return self._runtime.relationships[npc_id]

    def update_relationship(self, npc_id: str, delta: Dict[str, int]) -> None:
        rel = self.get_relationship(npc_id)
        for key, val in delta.items():
            if hasattr(rel, key):
                setattr(rel, key, max(0, min(100, getattr(rel, key) + val)))
        self._save_runtime()

    # ── Knowledge ──────────────────────────────────────────────────────────────

    def add_knowledge(self, fact: str) -> None:
        if fact not in self._runtime.knowledge:
            self._runtime.knowledge.append(fact)
            self._save_runtime()

    # ── Memory candidates ──────────────────────────────────────────────────────

    def accumulate_candidates(self, candidates: List[MemoryCandidate]) -> None:
        for c in candidates:
            if c.category == "knowledge":
                self.add_knowledge(c.fact)
            self._runtime.candidates.append(c)
        if len(self._runtime.candidates) > _MAX_CANDIDATES:
            self._runtime.candidates = self._runtime.candidates[-_MAX_CANDIDATES:]
        self._save_runtime()

    # ── Situation ──────────────────────────────────────────────────────────────

    def update_situation(self, situation: str) -> None:
        self._runtime.current_situation = situation
        self._save_runtime()

    def get_situation(self) -> str:
        return self._runtime.current_situation

    # ── Context builders ───────────────────────────────────────────────────────

    def get_npc_context(self, npc_id: str) -> dict:
        return {
            "world_state":     self._runtime.world_state,
            "relationship":    self.get_relationship(npc_id).model_dump(),
            "knowledge":       self._runtime.knowledge,
            "events_fired":    self._runtime.events_fired,
            "situation":       self._runtime.current_situation,
            "canon_facts":     self._load_canon_facts(),
            "dialogue_buffer": self.get_dialogue_buffer(npc_id),
            "past_memory":     self.get_npc_past_memory(npc_id),
        }

    def get_event_context(self) -> dict:
        return {
            "world_state":  self._runtime.world_state,
            "knowledge":    self._runtime.knowledge,
            "events_fired": self._runtime.events_fired,
            "situation":    self._runtime.current_situation,
        }

    # ── Scene end ──────────────────────────────────────────────────────────────

    def get_runtime_snapshot(self) -> RuntimeMemory:
        return self._runtime

    def archive_chronicle(self, chronicle: SceneChronicle) -> None:
        row_id = f"{chronicle.scene_id}_{datetime.now(timezone.utc).isoformat()}"
        with get_session() as session:
            row = SceneChronicleRow(
                id                   = row_id,
                scene_id             = chronicle.scene_id,
                summary              = chronicle.summary,
                major_events         = chronicle.major_events,
                relationship_changes = chronicle.relationship_changes,
                knowledge_gained     = chronicle.knowledge_gained,
                character_deaths     = chronicle.character_deaths,
                mysteries_revealed   = chronicle.mysteries_revealed,
            )
            session.merge(row)
            session.commit()

    def promote_to_canon(self, candidates: List[MemoryCandidate], scene_id: str) -> None:
        with get_session() as session:
            for c in candidates:
                row = StoryCanonRow(
                    id           = str(uuid.uuid4()),
                    fact         = c.fact,
                    category     = c.category,
                    scene_origin = scene_id,
                )
                session.add(row)
            session.commit()

    def reset_runtime(self, new_scene_id: str = "") -> None:
        self._runtime = RuntimeMemory(scene_id=new_scene_id or _SCENE_ID)
        self._buffer.clear()
        self._relationship_start.clear()
        self._save_runtime()

    # ── Full reset (new game) ──────────────────────────────────────────────────

    def reset(self) -> None:
        self._runtime = RuntimeMemory(scene_id=_SCENE_ID)
        self._buffer.clear()
        self._relationship_start.clear()
        self._save_runtime()

    # ── NPC Memory ─────────────────────────────────────────────────────────────

    def snapshot_relationships(self) -> None:
        """Call at scene start to record baseline relationship values for delta computation."""
        self._relationship_start = {
            npc_id: rel.model_dump()
            for npc_id, rel in self._runtime.relationships.items()
        }

    def compute_relationship_delta(self, npc_id: str) -> Dict[str, int]:
        start = self._relationship_start.get(npc_id, {"trust": 50, "fear": 0, "respect": 50})
        current = self.get_relationship(npc_id).model_dump()
        return {k: current[k] - start[k] for k in current if current[k] != start[k]}

    def get_npcs_with_interactions(self) -> List[str]:
        return list(self._buffer.keys())

    def save_npc_memory(self, entry: NPCMemoryEntry) -> None:
        row_id = f"{entry.npc_id}__{entry.scene_id}"
        with get_session() as session:
            row = NPCMemoryRow(
                id                 = row_id,
                npc_id             = entry.npc_id,
                scene_id           = entry.scene_id,
                key_exchanges      = entry.key_exchanges,
                relationship_delta = entry.relationship_delta,
                shared_events      = entry.shared_events,
                emotional_state    = entry.emotional_state,
            )
            session.merge(row)
            session.commit()

    def get_npc_past_memory(self, npc_id: str) -> List[NPCMemoryEntry]:
        with get_session() as session:
            rows = (
                session.query(NPCMemoryRow)
                .filter(NPCMemoryRow.npc_id == npc_id)
                .order_by(NPCMemoryRow.created_at)
                .all()
            )
            return [
                NPCMemoryEntry(
                    npc_id             = r.npc_id,
                    scene_id           = r.scene_id,
                    key_exchanges      = r.key_exchanges or [],
                    relationship_delta = r.relationship_delta or {},
                    shared_events      = r.shared_events or [],
                    emotional_state    = r.emotional_state or "",
                )
                for r in rows
            ]

    # ── DB persistence ─────────────────────────────────────────────────────────

    def _save_runtime(self) -> None:
        rels = {
            npc_id: (rel.model_dump() if isinstance(rel, RelationshipState) else rel)
            for npc_id, rel in self._runtime.relationships.items()
        }
        candidates = [
            (c.model_dump() if isinstance(c, MemoryCandidate) else c)
            for c in self._runtime.candidates
        ]
        with get_session() as session:
            row = RuntimeMemoryRow(
                scene_id          = self._runtime.scene_id or _SCENE_ID,
                world_state       = self._runtime.world_state,
                relationships     = rels,
                knowledge         = self._runtime.knowledge,
                events_fired      = self._runtime.events_fired,
                candidates        = candidates,
                current_situation = self._runtime.current_situation,
                updated_at        = datetime.now(timezone.utc),
            )
            session.merge(row)
            session.commit()

    def _load_runtime(self) -> RuntimeMemory:
        with get_session() as session:
            row = session.get(RuntimeMemoryRow, _SCENE_ID)
            if not row:
                return RuntimeMemory(scene_id=_SCENE_ID)
            return RuntimeMemory(
                scene_id          = row.scene_id,
                world_state       = row.world_state or {},
                relationships     = {
                    npc: RelationshipState.model_validate(rel)
                    for npc, rel in (row.relationships or {}).items()
                },
                knowledge         = row.knowledge or [],
                events_fired      = row.events_fired or [],
                candidates        = [
                    MemoryCandidate.model_validate(c)
                    for c in (row.candidates or [])
                ],
                current_situation = row.current_situation or "",
            )

    def _load_canon_facts(self) -> List[str]:
        with get_session() as session:
            rows = session.query(StoryCanonRow).all()
            return [r.fact for r in rows]
