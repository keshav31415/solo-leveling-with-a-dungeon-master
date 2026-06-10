import logging

from langsmith import traceable

from .llm import generate_json
from .prompts import DIRECTOR_SYSTEM_PROMPT
from .schemas import ScenePlan, PlannedEvent
from .db import get_session, ScenePlanRow, init_db

logger = logging.getLogger(__name__)

_SCENE_ID = "double_dungeon"


class DirectorAgent:
    def __init__(self, memory):
        init_db()
        self.memory = memory

    @traceable(run_type="chain", name="Director — Generate Scene Plan")
    def generate_scene_plan(self, force: bool = False) -> ScenePlan:
        if not force:
            existing = self.get_scene_plan()
            if existing and existing.events:
                logger.info("Scene plan already exists — skipping regeneration.")
                return existing

        user_prompt = self._build_user_prompt()
        raw = generate_json(DIRECTOR_SYSTEM_PROMPT, user_prompt)
        print("--- DIRECTOR SCENE PLAN ---")
        print(raw)

        try:
            events = [PlannedEvent.model_validate(e) for e in raw.get("events", [])]
        except Exception as exc:
            logger.error("Director returned invalid events: %s", exc)
            events = _fallback_events()

        if not events:
            logger.warning("Director returned empty events — using fallback.")
            events = _fallback_events()

        plan = ScenePlan(scene_id=_SCENE_ID, events=events)
        self._save(plan)
        return plan

    def _build_user_prompt(self) -> str:
        mandatory   = self.memory.get_lore_facts(_SCENE_ID, tiers=["mandatory"])
        structural  = self.memory.get_lore_facts(_SCENE_ID, tiers=["structural"])

        # Filter structural to world/rule facts only (character profiles are for DM, not Director)
        world_rules = [f for f in structural if f.category in ("world", "rule")]

        beats_text = "\n".join(f"  - {f.fact}" for f in mandatory)
        rules_text = "\n".join(f"  - {f.fact}" for f in world_rules)

        return f"""Generate the scene plan for the Double Dungeon.

MANDATORY STORY BEATS — generate events that collectively cover ALL of these:
{beats_text or '  (none loaded — use your knowledge of the arc)'}

STRUCTURAL RULES — the DM needs these for accurate narration (include relevant ones in event descriptions):
{rules_text or '  (none loaded)'}
"""

    def get_scene_plan(self) -> ScenePlan | None:
        with get_session() as session:
            row = session.get(ScenePlanRow, _SCENE_ID)
            if not row:
                return None
            return ScenePlan(
                scene_id = row.scene_id,
                events   = [PlannedEvent.model_validate(e) for e in (row.events or [])],
            )

    def get_director_note(self, event_id: str) -> str:
        plan = self.get_scene_plan()
        if not plan:
            return ""
        for event in plan.events:
            if event.id == event_id:
                return event.description
        return ""

    def _save(self, plan: ScenePlan) -> None:
        with get_session() as session:
            row = ScenePlanRow(
                scene_id = plan.scene_id,
                events   = [e.model_dump() for e in plan.events],
            )
            session.merge(row)
            session.commit()


def _fallback_events():
    return [
        PlannedEvent(
            id            = "chamber_revealed",
            description   = "The party steps into the Double Dungeon chamber. Blue flames ignite one by one around the perimeter. No monsters anywhere — vast silence. This is secretly S-rank danger disguised as D-rank. Someone remarks this doesn't look right.",
            trigger_type  = "auto",
            trigger_value = None,
            delay_ms      = 800,
        ),
        PlannedEvent(
            id            = "statue_awakens",
            description   = "Lee Joohee notices the God Statue's eyes tracking the party. It is aware — watching them. She freezes mid-step, stutters in pure terror, backs toward Jinwoo. The statue does not move — only the eyes.",
            trigger_type  = "position",
            trigger_value = "player.gridY < 30",
        ),
        PlannedEvent(
            id            = "commandments_revealed",
            description   = "The stone tablet glows. Three commandments in ancient script: 'Revere God.' / 'Praise God.' / 'Prove your devotion to God.' Final line: 'Any soul that fails to abide shall not leave this place alive.' NARRATOR only — no NPC reactions.",
            trigger_type  = "interact",
            trigger_value = "stone_tablet",
        ),
        PlannedEvent(
            id            = "doors_seal",
            description   = "Massive stone doors slam shut. The entrance is sealed — no escape. The divine trap triggered the moment the commandments were read. Screen shakes. The party is trapped.",
            trigger_type  = "chain",
            trigger_value = "commandments_revealed",
        ),
    ]
