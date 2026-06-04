from typing import Dict, Any, List
from .llm import generate_json
from .prompts import DIRECTOR_SYSTEM_PROMPT
from .schemas import parse_director_response

class DirectorAgent:
    def __init__(self):
        pass

    def evaluate_scene(self, state: Dict[str, Any], actions_taken: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates the current scene and generates new JIT triggers.
        """
        user_prompt = f"""
Current State:
{state}

Recent Actions:
{actions_taken}

Generate the updated event queue and triggers.
"""
        raw = generate_json(DIRECTOR_SYSTEM_PROMPT, user_prompt)
        response = parse_director_response(raw)

        return {
            "event_queue": response.event_queue,
            "triggers": [t.model_dump() for t in response.triggers],
        }
