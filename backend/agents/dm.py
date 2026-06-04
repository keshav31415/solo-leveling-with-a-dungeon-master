import json
from typing import Dict, Any, List

from langsmith import traceable

from .llm import generate_json
from .prompts import DM_SYSTEM_PROMPT, JS_GENERATION_SYSTEM_PROMPT
from .schemas import (
    parse_narrative_response,
    GameAction, DialogueTurn,
    EVENTS_REQUIRING_JS, FALLBACK_GAME_ACTIONS,
)

_MOVEMENT_NPC_IDS = {"joohee", "song_chiyul", "mr_park", "mr_kim", "giant_statue"}
from .memory import MemoryStore

_JS_MAX_RETRIES = 2


class DMAgent:
    def __init__(self, memory: MemoryStore):
        self.memory = memory

    # ── Call 1: Narrative prompt ───────────────────────────────────────────────

    def _npc_positions_block(self, entity_states: Dict[str, Any]) -> str:
        lines = []
        for eid, data in entity_states.items():
            if eid in _MOVEMENT_NPC_IDS or data.get("isPlayer"):
                prefix = "[Player] " if data.get("isPlayer") else ""
                lines.append(
                    f"  {prefix}{eid}: ({data.get('gridX','?')}, {data.get('gridY','?')}) | state: {data.get('state','idle')}"
                )
        return "\n".join(lines) if lines else "  (no NPCs)"

    def _build_narrative_prompt(self, state: Dict[str, Any], action: Dict[str, Any]) -> str:
        action_type = action.get("action_type", "")
        target_id   = action.get("target", "")

        if action_type == "director_event":
            return self._director_event_prompt(target_id, state)
        if action_type == "interact":
            return self._interact_prompt(state, action, target_id)

        return f"Current Game State:\n{state}\n\nPlayer's Action:\n{action}\n\nGenerate the response."

    def _director_event_prompt(self, event_name: str, state: Dict[str, Any]) -> str:
        ctx = self.memory.get_event_context()

        world_block     = "\n".join(f"  {k}: {v}" for k, v in ctx["world_state"].items()) or "  (none yet)"
        events_block    = "\n".join(f"  - {e}" for e in ctx["events_fired"]) or "  (none yet)"
        knowledge_block = "\n".join(f"  - {k}" for k in ctx["knowledge"]) or "  (none yet)"
        npc_block       = self._npc_positions_block(state.get("entity_states", {}))

        return f"""Event to narrate: {event_name}

Current situation:
  {ctx["situation"] or "(scene just started)"}

World state:
{world_block}

Events already fired — do NOT repeat or reference these as new:
{events_block}

What the party currently knows:
{knowledge_block}

NPC positions (grid coordinates) — use for movement directives:
{npc_block}

Generate the response."""

    def _interact_prompt(self, state: Dict[str, Any], action: Dict[str, Any], target_id: str) -> str:
        entity       = state.get("entity_states", {}).get(target_id, {})
        ctx          = action.get("context", {})
        player_msg   = ctx.get("player_message", "")
        player_act   = ctx.get("player_action", "")
        player_stats = state.get("player_stats", {})
        label        = entity.get("label", target_id)

        npc_ctx = self.memory.get_npc_context(target_id)
        rel     = npc_ctx["relationship"]

        jinwoo_parts = []
        if player_msg: jinwoo_parts.append(f'says: "{player_msg}"')
        if player_act: jinwoo_parts.append(f"*{player_act}*")
        if not jinwoo_parts: jinwoo_parts.append("(approaches silently — just listens)")
        jinwoo_turn = " | ".join(jinwoo_parts)

        world_block     = "\n".join(f"  {k}: {v}" for k, v in npc_ctx["world_state"].items()) or "  (none yet)"
        events_block    = "\n".join(f"  - {e}" for e in npc_ctx["events_fired"]) or "  (none yet)"
        knowledge_block = "\n".join(f"  - {k}" for k in npc_ctx["knowledge"]) or "  (none yet)"
        canon_block     = "\n".join(f"  - {f}" for f in npc_ctx["canon_facts"]) or "  (none yet)"

        buffer = npc_ctx["dialogue_buffer"]
        if buffer:
            buf_lines = []
            for t in buffer:
                parts = []
                if t.jinwoo_says: parts.append(f'says: "{t.jinwoo_says}"')
                if t.jinwoo_does: parts.append(f"*{t.jinwoo_does}*")
                if parts: buf_lines.append(f"  [Jinwoo]: {' | '.join(parts)}")
                buf_lines.append(f"  [{label}]: {t.response}")
            buffer_block = "\n".join(buf_lines)
        else:
            buffer_block = "  (no prior exchanges this session)"

        npc_block = self._npc_positions_block(state.get("entity_states", {}))

        return f"""You are responding AS: {label} (id: {target_id})
ONLY this character speaks. Do NOT write responses from any other NPC.

WORLD STATE:
{world_block}

EVENTS EVERYONE WITNESSED (in order):
{events_block}

WHAT THE PARTY KNOWS:
{knowledge_block}

YOUR RELATIONSHIP WITH SUNG JINWOO:
  Trust: {rel["trust"]}/100 | Fear: {rel["fear"]}/100 | Respect: {rel["respect"]}/100

STORY CANON:
{canon_block}

RECENT EXCHANGES (last {len(buffer)} turns):
{buffer_block}

NPC positions (grid coordinates) — use for movement directives:
{npc_block}

Player: {player_stats.get("name")}, {player_stats.get("rank")}, HP {player_stats.get("hp")}
Your current state: {entity.get("state", "idle")}

*** CURRENT ACTION from Jinwoo: {jinwoo_turn} ***
React to THIS action. Your response MUST reflect the world state."""

    # ── Call 2: JS generation ─────────────────────────────────────────────────
    #
    # Simple actions (shake_screen, set_entity_state, etc.) are translated
    # deterministically — no LLM involved, no reliability risk.
    # VFX actions (beam, glow, ring, particles, etc.) go to the LLM with retry.

    _SIMPLE_ACTIONS = {
        "shake_screen":     lambda p: f"GameAPI.shakeScreen({p.get('intensity', 5)}, {p.get('duration_ms', 300)});",
        "set_entity_state": lambda p: f"GameAPI.setEntityState('{p['entity_id']}', '{p['state']}');",
        "set_entity_color": lambda p: f"GameAPI.setEntityColor('{p['entity_id']}', '{p['color']}');",
    }

    def _generate_js(
        self,
        game_actions: List[GameAction],
        entity_states: Dict[str, Any],
    ) -> str:
        simple_lines: List[str] = []
        vfx_actions:  List[GameAction] = []

        for action in game_actions:
            translator = self._SIMPLE_ACTIONS.get(action.type)
            if translator:
                simple_lines.append(translator(action.params))
            else:
                vfx_actions.append(action)

        # Deterministic JS for simple actions
        simple_js = "\n".join(simple_lines)

        # LLM-generated JS for VFX actions (with retry)
        vfx_js = ""
        if vfx_actions:
            vfx_js = self._generate_vfx_js(vfx_actions, entity_states)

        combined = "\n".join(filter(None, [vfx_js, simple_js]))
        return combined

    @traceable(run_type="chain", name="VFX JS Generation")
    def _generate_vfx_js(
        self,
        vfx_actions: List[GameAction],
        entity_states: Dict[str, Any],
    ) -> str:
        involved: set = set()
        for a in vfx_actions:
            for key in ("entity_id", "from_entity", "to_entity"):
                if key in a.params:
                    involved.add(a.params[key])

        entity_context = {
            eid: {k: v for k, v in data.items() if k in ("gridX", "gridY", "state", "label", "width", "height")}
            for eid, data in entity_states.items()
            if eid in involved
        }

        actions_json  = json.dumps([a.model_dump() for a in vfx_actions], indent=2)
        entities_json = json.dumps(entity_context, indent=2)

        user_prompt = (
            f"VFX actions to animate:\n{actions_json}\n\n"
            f"Relevant entities (grid positions):\n{entities_json}\n\n"
            f"Write the JavaScript. Use GameAPI.getEntity(id) to get screen coordinates."
        )

        last_error = ""
        for attempt in range(_JS_MAX_RETRIES):
            prompt = user_prompt if not last_error else (
                user_prompt + f"\n\nPrevious attempt failed: {last_error}. Fix and retry."
            )
            raw = generate_json(JS_GENERATION_SYSTEM_PROMPT, prompt)
            js  = (raw.get("js") or "").strip()

            if not js:
                last_error = "returned empty js field"
                continue
            if "```" in js:
                last_error = "js contained markdown backticks — output raw JS only"
                continue

            print(f"[VFX JS] attempt {attempt + 1} succeeded")
            return js

        print(f"[VFX JS] all {_JS_MAX_RETRIES} attempts failed")
        return ""

    # ── Main handler ──────────────────────────────────────────────────────────

    @traceable(run_type="chain", name="DM Agent")
    def handle_action(
        self,
        state: Dict[str, Any],
        _instructions: Dict[str, Any],
        action: Dict[str, Any],
    ) -> Dict[str, Any]:
        action_type = action.get("action_type", "")
        target_id   = action.get("target", "")

        # ── Call 1: Narrative ──────────────────────────────────────────────────
        narrative_prompt = self._build_narrative_prompt(state, action)
        raw = generate_json(DM_SYSTEM_PROMPT, narrative_prompt)
        print("--- NARRATIVE RESPONSE ---")
        print(raw)

        if "error" in raw:
            return {
                "narrative":     raw["error"],
                "speaker":       "SYSTEM",
                "js_injection":  "",
                "new_situation": None,
                "new_state":     state,
            }

        response = parse_narrative_response(raw, action_type, target_id)

        # ── Update memory ──────────────────────────────────────────────────────
        if response.new_situation:
            self.memory.update_situation(response.new_situation)
        if response.memory_candidates:
            self.memory.accumulate_candidates(response.memory_candidates)
        if action_type == "director_event":
            self.memory.on_event_fired(target_id)
        elif action_type == "interact":
            ctx = action.get("context", {})
            self.memory.add_dialogue_turn(target_id, DialogueTurn(
                jinwoo_says=ctx.get("player_message", ""),
                jinwoo_does=ctx.get("player_action", ""),
                response=response.narrative,
            ))
        if response.new_entity_states:
            self.memory.update_world_state(response.new_entity_states)
            for eid, new_state in response.new_entity_states.items():
                if eid in state["entity_states"]:
                    state["entity_states"][eid]["state"] = new_state

        # ── Call 2: JS generation ──────────────────────────────────────────────
        js_injection = ""
        game_actions = response.game_actions

        # Last resort: inject fallback actions if required event returned nothing
        if not game_actions and action_type == "director_event" and target_id in EVENTS_REQUIRING_JS:
            fallback = FALLBACK_GAME_ACTIONS.get(target_id, [])
            if fallback:
                game_actions = [GameAction.model_validate(a) for a in fallback]

        if game_actions:
            print(f"--- JS GEN ({len(game_actions)} actions) ---")
            js_injection = self._generate_js(game_actions, state.get("entity_states", {}))

        movement_directives = [
            d.model_dump(exclude_none=True)
            for d in (response.npc_movement_directives or [])
        ]

        return {
            "narrative":               response.narrative,
            "speaker":                 response.speaker,
            "js_injection":            js_injection,
            "new_situation":           response.new_situation,
            "new_state":               state,
            "npc_movement_directives": movement_directives,
        }
