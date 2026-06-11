import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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

        # Fire extraction in background — don't block plan generation
        threading.Thread(target=self._extract_missing_profiles, daemon=True).start()

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
        if not missing:
            return

        def extract_one(char_id: str) -> None:
            user_prompt = f"Character: {char_id}\nArc: {config['arc']}"
            raw = generate_json_background(CHARACTER_PROFILE_EXTRACTION_PROMPT, user_prompt)
            profile = raw.get("profile", "")
            if profile:
                self.memory.save_character_profile(char_id, config["arc"], profile)
                print(f"[Profiles] Extracted: {char_id}")
            else:
                print(f"[Profiles] Empty result for {char_id}")

        # All characters extracted in parallel — each thread tries Groq first,
        # falls through to OpenRouter if rate-limited, distributing load naturally
        with ThreadPoolExecutor(max_workers=len(missing)) as executor:
            futures = {executor.submit(extract_one, cid): cid for cid in missing}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[Profiles] Failed: {e}")

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
            description   = "The party steps into the Double Dungeon chamber. Blue flames ignite one by one around the perimeter. No monsters anywhere — vast silence. This is secretly S-rank danger disguised as D-rank.",
            trigger_type  = "auto",
            trigger_value = None,
            delay_ms      = 800,
            speaker       = "NARRATOR",
            npc_reactions = {
                "mr_kim":      "stops walking, scans the room, mutters about the mana density being all wrong for a D-rank",
                "song_chiyul": "raises a fist to halt the group, eyes sweeping the chamber with unease",
                "mr_park":     "lets out a low whistle, hand instinctively moving to his weapon",
                "joohee":      "stays close to Jinwoo, gripping her healer's kit tightly",
            },
            visual_notes  = "vast circular stone chamber, blue flames lighting one by one around the perimeter, complete silence, no monsters",
        ),
        PlannedEvent(
            id            = "statue_awakens",
            description   = "Lee Joohee notices the God Statue's eyes tracking the party. It is aware — watching them. She freezes mid-step, stutters in pure terror and grabs Jinwoo's arm, backing toward him.",
            trigger_type  = "position",
            trigger_value = "player.gridY < 30",
            speaker       = "joohee",
            npc_reactions = {
                "joohee": "freezes mid-step, stutters in pure terror, grabs Jinwoo's arm and presses against him — Jinwoo specifically, not the party leader",
            },
            visual_notes  = "the statue's body remains completely still — only the eyes move, slowly tracking the party",
        ),
        PlannedEvent(
            id            = "commandments_revealed",
            description   = "The stone tablet glows. Three commandments in ancient script: 'Revere God.' / 'Praise God.' / 'Prove your devotion to God.' Final line: 'Any soul that fails to abide shall not leave this place alive.'",
            trigger_type  = "interact",
            trigger_value = "stone_tablet",
            speaker       = "NARRATOR",
            npc_reactions = {},
            visual_notes  = "NARRATOR only — no NPC dialogue or reactions during the reading",
        ),
        PlannedEvent(
            id            = "doors_seal",
            description   = "Massive stone doors slam shut with a sound like a mountain collapsing. The entrance is sealed. The divine trap triggered the moment the commandments were read. The party is trapped.",
            trigger_type  = "chain",
            trigger_value = "commandments_revealed",
            speaker       = "NARRATOR",
            npc_reactions = {
                "song_chiyul": "spins toward the door, shouts for everyone to stay calm — his voice cracks",
                "mr_park":     "sprints toward the door, slamming his fists against the stone — it doesn't move",
                "mr_kim":      "stands frozen, processing, then says quietly that this is not a D-rank dungeon",
                "joohee":      "grabs Jinwoo's arm with both hands, trembling",
            },
        ),
        PlannedEvent(
            id            = "hunter_killed_at_door",
            description   = "Mr. Park's composure shatters. He breaks ranks and sprints for the sealed entrance. The guard statues flanking the door activate the instant he crosses the threshold and cut him down. First death. No last words.",
            trigger_type  = "chain",
            trigger_value = "doors_seal",
            speaker       = "NARRATOR",
            npc_reactions = {
                "mr_park":     "breaks ranks, sprints for the door in blind panic — does not make it",
                "joohee":      "screams, buries her face against Jinwoo's arm, unable to look",
                "song_chiyul": "shouts for Park to stop — too late, watches in horror",
                "mr_kim":      "goes completely still, face pale, staring at where Park fell",
            },
        ),
        PlannedEvent(
            id            = "laser_sweep",
            description   = "The God Statue's eyes burn red. Twin laser beams sweep slowly across the chamber floor in a clockwise circle, leaving scorch marks. Those still standing are incinerated. Jinwoo presses his forehead to the stone floor.",
            trigger_type  = "chain",
            trigger_value = "hunter_killed_at_door",
            speaker       = "NARRATOR",
            npc_reactions = {
                "joohee":      "collapses to her knees beside Jinwoo, forehead to the floor, following his lead",
                "song_chiyul": "drops to the floor and prostrates himself, screaming at the others to bow",
                "mr_kim":      "throws himself flat, arms over his head",
            },
            visual_notes  = "laser beams sweep slowly clockwise — the floor shows scorch marks where the beam passes",
        ),
    ]
