import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any

from .schemas import (
    RuntimeMemory, SceneChronicle,
    RelationshipState, MemoryCandidate,
    DialogueTurn, NPCDialogueBuffer,
    NPCMemoryEntry, LoreFact,
)
from .db import (
    get_session, init_db,
    RuntimeMemoryRow, SceneChronicleRow, StoryCanonRow, NPCMemoryRow, LoreFactRow,
)

_MAX_CANDIDATES          = 100
_BUFFER_COMPRESS_THRESHOLD = 20   # trigger compression when recent_turns hits this
_BUFFER_KEEP_RECENT        = 10   # keep last N turns after compression
_BUFFER_COMPRESS_BATCH     = 10   # compress the oldest N turns + existing summary
_NPC_MEMORY_MAX_ENTRIES    = 3    # max past-scene entries injected into DM prompt

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
        self._buffer: Dict[str, NPCDialogueBuffer] = {}
        self._relationship_start: Dict[str, Dict[str, int]] = {}

    # ── Dialogue buffer (ephemeral, never persisted) ───────────────────────────

    def add_dialogue_turn(self, npc_id: str, turn: DialogueTurn) -> None:
        if npc_id not in self._buffer:
            self._buffer[npc_id] = NPCDialogueBuffer()
        buf = self._buffer[npc_id]
        buf.recent_turns.append(turn)
        buf.total_turns += 1
        if len(buf.recent_turns) >= _BUFFER_COMPRESS_THRESHOLD:
            self._compress_buffer(npc_id)

    def _compress_buffer(self, npc_id: str) -> None:
        # Deferred import to avoid circular dependency at module load time
        from .llm import generate_json
        from .prompts import DIALOGUE_COMPRESSION_PROMPT

        buf = self._buffer[npc_id]
        to_compress = buf.recent_turns[:_BUFFER_COMPRESS_BATCH]
        buf.recent_turns = buf.recent_turns[_BUFFER_COMPRESS_BATCH:]

        lines = []
        for t in to_compress:
            if t.jinwoo_says: lines.append(f'Jinwoo says: "{t.jinwoo_says}"')
            if t.jinwoo_does: lines.append(f'Jinwoo does: *{t.jinwoo_does}*')
            lines.append(f'{npc_id} responds: {t.response}')

        user_prompt = (
            f"Previous summary:\n{buf.scene_summary or '(none)'}\n\n"
            f"New exchanges to compress:\n" + "\n".join(lines)
        )
        raw = generate_json(DIALOGUE_COMPRESSION_PROMPT, user_prompt)
        buf.scene_summary = raw.get("summary", buf.scene_summary)

    def get_dialogue_buffer(self, npc_id: str) -> NPCDialogueBuffer:
        return self._buffer.get(npc_id, NPCDialogueBuffer())

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
        scene = self._runtime.scene_id or _SCENE_ID
        # Character-specific lore + world/rule structural lore
        all_structural = self.get_lore_facts(scene, tiers=["structural"])
        lore = [
            f.fact for f in all_structural
            if npc_id in (f.characters_involved or []) or f.category in ("world", "rule")
        ]
        return {
            "world_state":     self._runtime.world_state,
            "relationship":    self.get_relationship(npc_id).model_dump(),
            "knowledge":       self._runtime.knowledge,
            "events_fired":    self._runtime.events_fired,
            "situation":       self._runtime.current_situation,
            "canon_facts":     self._load_canon_facts(),
            "lore_facts":      lore,
            "dialogue_buffer": self.get_dialogue_buffer(npc_id),
            "past_memory":     self.retrieve_npc_memory(npc_id, self._runtime.events_fired),
        }

    def get_event_context(self) -> dict:
        scene = self._runtime.scene_id or _SCENE_ID
        # World/rule structural lore for director events
        lore = [
            f.fact for f in self.get_lore_facts(scene, tiers=["structural"])
            if f.category in ("world", "rule")
        ]
        return {
            "world_state":  self._runtime.world_state,
            "knowledge":    self._runtime.knowledge,
            "events_fired": self._runtime.events_fired,
            "situation":    self._runtime.current_situation,
            "lore_facts":   lore,
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

    def reset(self) -> None:
        self._runtime = RuntimeMemory(scene_id=_SCENE_ID)
        self._buffer.clear()
        self._relationship_start.clear()
        self._save_runtime()

    # ── NPC Memory ─────────────────────────────────────────────────────────────

    def snapshot_relationships(self) -> None:
        self._relationship_start = {
            npc_id: rel.model_dump()
            for npc_id, rel in self._runtime.relationships.items()
        }

    def compute_relationship_delta(self, npc_id: str) -> Dict[str, int]:
        start   = self._relationship_start.get(npc_id, {"trust": 50, "fear": 0, "respect": 50})
        current = self.get_relationship(npc_id).model_dump()
        return {k: current[k] - start[k] for k in current if current[k] != start[k]}

    def get_npcs_with_interactions(self) -> List[str]:
        return [
            npc_id for npc_id, buf in self._buffer.items()
            if buf.recent_turns or buf.scene_summary
        ]

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

    def retrieve_npc_memory(
        self,
        npc_id: str,
        events_fired: List[str],
        max_entries: int = _NPC_MEMORY_MAX_ENTRIES,
    ) -> List[NPCMemoryEntry]:
        """
        3-tier retrieval:
          Tier 1 — always include most recent scene entry
          Tier 2 — include any older entry whose shared_events overlaps current events_fired
          Tier 3 — (future) semantic search via pgvector
        Cap at max_entries total.
        """
        all_memories = self._load_npc_past_memory(npc_id)
        if not all_memories:
            return []

        selected: List[NPCMemoryEntry] = []
        seen_ids: set = set()

        # Tier 1: most recent
        latest = all_memories[-1]
        selected.append(latest)
        seen_ids.add(id(latest))

        # Tier 2: shared events overlap
        current_events = set(events_fired)
        for entry in reversed(all_memories[:-1]):
            if len(selected) >= max_entries:
                break
            if id(entry) not in seen_ids and set(entry.shared_events) & current_events:
                selected.append(entry)
                seen_ids.add(id(entry))

        return selected[:max_entries]

    def _load_npc_past_memory(self, npc_id: str) -> List[NPCMemoryEntry]:
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

    # ── Lore ───────────────────────────────────────────────────────────────────

    def seed_lore_if_empty(self) -> None:
        from .lore_seed import DOUBLE_DUNGEON_LORE
        with get_session() as session:
            if session.query(LoreFactRow).count() > 0:
                return
            for data in DOUBLE_DUNGEON_LORE:
                session.add(LoreFactRow(**data))
            session.commit()
            print(f"[LoreStore] Seeded {len(DOUBLE_DUNGEON_LORE)} lore facts.")

    def get_lore_facts(
        self,
        scene_id: str,
        tiers: List[str] | None = None,
    ) -> List[LoreFact]:
        with get_session() as session:
            rows = (
                session.query(LoreFactRow)
                .filter(LoreFactRow.superseded == False)  # noqa: E712
                .all()
            )
            facts = []
            for r in rows:
                relevance = r.scene_relevance or []
                if scene_id not in relevance and "all" not in relevance:
                    continue
                if tiers and r.tier not in tiers:
                    continue
                facts.append(LoreFact(
                    id                  = r.id,
                    fact                = r.fact,
                    category            = r.category,
                    scene_relevance     = r.scene_relevance or [],
                    characters_involved = r.characters_involved or [],
                    entities_involved   = r.entities_involved or [],
                    tier                = r.tier,
                    temporal_status     = r.temporal_status or "always_true",
                    superseded          = r.superseded or False,
                    superseded_by       = r.superseded_by,
                ))
            return facts

    def supersede_lore_fact(self, lore_fact_id: str, canon_fact_id: str) -> None:
        with get_session() as session:
            row = session.get(LoreFactRow, lore_fact_id)
            if row:
                row.superseded    = True
                row.superseded_by = canon_fact_id
                row.temporal_status = "was_true"
                session.commit()

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
