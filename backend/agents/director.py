import json
import logging

from langsmith import traceable

from .llm import generate_json, generate_json_background
from .prompts import DIRECTOR_SYSTEM_PROMPT, CHARACTER_PROFILE_EXTRACTION_PROMPT, PLAN_VALIDATION_PROMPT
from .schemas import ScenePlan, PlannedEvent
from .scene_config import get_scene_config
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

        self._extract_missing_profiles()

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

        events = self._validate_plan(events)

        plan = ScenePlan(scene_id=_SCENE_ID, events=events)
        self._save(plan)
        return plan

    def _extract_missing_profiles(self) -> None:
        config  = get_scene_config(_SCENE_ID)
        missing = self.memory.get_missing_profiles(config["characters"], config["arc"])
        for char_id in missing:
            user_prompt = f"Character: {char_id}\nArc: {config['arc']}"
            raw = generate_json_background(CHARACTER_PROFILE_EXTRACTION_PROMPT, user_prompt)
            profile = raw.get("profile", "")
            if profile:
                self.memory.save_character_profile(char_id, config["arc"], profile)
                print(f"[Profiles] Extracted profile for {char_id}")
            else:
                print(f"[Profiles] Extraction returned empty for {char_id}")

    def _validate_plan(self, events: list) -> list:
        config   = get_scene_config(_SCENE_ID)
        profiles = self.memory.get_character_profiles(config["characters"], config["arc"])
        if not profiles:
            return events

        for event in events:
            if not event.npc_reactions:
                continue
            reactions_to_check = {
                npc: reaction
                for npc, reaction in event.npc_reactions.items()
                if npc in profiles
            }
            if not reactions_to_check:
                continue

            user_prompt = (
                f"Event: {event.id}\n"
                f"NPC reactions:\n{json.dumps(reactions_to_check, indent=2)}\n\n"
                f"Character profiles:\n"
                + "\n".join(f"[{npc}]: {profiles[npc]}" for npc in reactions_to_check)
            )
            result = generate_json_background(PLAN_VALIDATION_PROMPT, user_prompt)
            violations = result.get("violations", [])
            if violations:
                logger.warning("[Validation] Event '%s' violations: %s", event.id, violations)

        return events

    def _build_user_prompt(self) -> str:
        config      = get_scene_config(_SCENE_ID)
        mandatory   = self.memory.get_lore_facts(_SCENE_ID, tiers=["mandatory"])
        structural  = self.memory.get_lore_facts(_SCENE_ID, tiers=["structural"])
        world_rules = [f for f in structural if f.category in ("world", "rule")]
        profiles    = self.memory.get_character_profiles(config["characters"], config["arc"])

        beats_text    = "\n".join(f"  - {f.fact}" for f in mandatory)
        rules_text    = "\n".join(f"  - {f.fact}" for f in world_rules)
        profiles_text = "\n\n".join(
            f"  [{char_id.upper()}]\n  {profile}"
            for char_id, profile in profiles.items()
        ) or "  (not yet extracted — use source material knowledge)"

        return f"""Generate the scene plan for the Double Dungeon.

MANDATORY STORY BEATS — generate events that collectively cover ALL of these:
{beats_text or '  (none loaded — use your knowledge of the arc)'}

STRUCTURAL RULES — the DM needs these for accurate narration:
{rules_text or '  (none loaded)'}

CHARACTER PROFILES — use these when writing npc_reactions for each event:
{profiles_text}
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

    def get_director_event(self, event_id: str) -> dict:
        plan = self.get_scene_plan()
        if not plan:
            return {}
        for event in plan.events:
            if event.id == event_id:
                return event.model_dump()
        return {}

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
            description   = "Lee Joohee notices the God Statue's eyes tracking the party. It is aware — watching them. She freezes mid-step, stutters in pure terror, grabs Jinwoo's arm and backs toward him specifically. NOT Song Chi-yul. The statue does not move — only the eyes.",
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
            description   = "Massive stone doors slam shut with a sound like a mountain collapsing. The entrance is sealed — no escape. The divine trap triggered the moment the commandments were read. Screen shakes. The party is trapped.",
            trigger_type  = "chain",
            trigger_value = "commandments_revealed",
        ),
        PlannedEvent(
            id            = "hunter_killed_at_door",
            description   = "Mr. Park's composure shatters. He cannot take it — he breaks ranks and sprints for the sealed entrance. The guard statues flanking the door activate the instant he crosses the threshold and cut him down. No heroics. No last words. Sudden, violent, first death.",
            trigger_type  = "chain",
            trigger_value = "doors_seal",
        ),
        PlannedEvent(
            id            = "laser_sweep",
            description   = "The God Statue's eyes burn red. Twin laser beams fire and begin a slow clockwise sweep across the entire chamber floor, burning scorch marks into stone. Any hunter still standing when the sweep reaches them is incinerated. Jinwoo follows the commandments — he presses his forehead to the stone, face down, prostrating completely. Those who do the same survive.",
            trigger_type  = "chain",
            trigger_value = "hunter_killed_at_door",
        ),
    ]
