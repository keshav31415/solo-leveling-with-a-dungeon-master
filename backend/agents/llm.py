import os
import json
from groq import Groq
from openai import OpenAI as OpenAIClient
from dotenv import load_dotenv
from langsmith import traceable

# Load env, checking multiple potential locations
load_dotenv(override=True)
if not os.getenv("GROQ_API_KEY"):
    load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"), override=True)
if not os.getenv("GROQ_API_KEY"):
    load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"), override=True)

# Groq — real-time DM and Director responses
groq_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_key) if groq_key else None

# OpenRouter — background tasks (profile extraction, validation)
openrouter_key = os.getenv("OPENROUTER_API_KEY")
_openrouter_client = OpenAIClient(
    api_key=openrouter_key,
    base_url="https://openrouter.ai/api/v1",
) if openrouter_key else None

_BACKGROUND_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]
    
@traceable(run_type="llm", name="Groq Call")
def generate_json(system_prompt: str, user_prompt: str) -> dict:
    """Calls Groq (Llama 3) to generate a JSON response based on the system and user prompts."""

    if not client:
        print("WARNING: GROQ_API_KEY not found. Returning mock response.")
        return mock_llm_response(system_prompt)

    try:
        models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
        ]

        last_exception = None

        for model_name in models:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )

                # Parse the JSON response
                text = response.choices[0].message.content
                return json.loads(text)
            
            except Exception as e:
                error_msg = str(e)
                # If we hit a rate limit OR a decommissioned model error (like 400), try the next fallback
                if "429" in error_msg or "rate_limit" in error_msg.lower() or "400" in error_msg or "decommissioned" in error_msg.lower():
                    print(f"[Warning] Error with model {model_name}. Trying next fallback...")
                    last_exception = e
                    continue # Try the next model
                else:
                    # If it's a completely different error (e.g. JSON parse fail), just raise it
                    raise e
                    
        # If we exhausted all models and they all threw rate limits
        if last_exception:
            raise last_exception
            
    except Exception as e:
        error_msg = str(e)
        print(f"Error calling LLM: {error_msg}")
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            # Extract the specific quota details if possible
            specific_reason = error_msg
            if "Rate limit reached" in error_msg:
                # Try to clean it up slightly if it's a JSON dict embedded in the string
                parts = error_msg.split("Rate limit reached")
                if len(parts) > 1:
                    specific_reason = "Rate limit reached" + parts[1].split("Please try again")[0] + "Please try again shortly."
            return {"error": f"[SYSTEM WARNING]: {specific_reason}"}
        return {"error": f"[SYSTEM ERROR]: LLM failed: {error_msg}"}

def generate_json_background(system_prompt: str, user_prompt: str) -> dict:
    """OpenRouter free-tier call for background tasks (profile extraction, validation).
    No tracing — these are non-critical background writes."""
    if not _openrouter_client:
        print("WARNING: OPENROUTER_API_KEY not found.")
        return {}

    for model_name in _BACKGROUND_MODELS:
        try:
            response = _openrouter_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            text = response.choices[0].message.content
            return json.loads(text)
        except Exception as e:
            print(f"[OpenRouter] {model_name} failed: {e}")
            continue

    return {}


def mock_llm_response(system_prompt: str) -> dict:
    """Provides a mock response if the API key is missing."""
    if "DIRECTOR" in system_prompt:
        return {
            "event_queue": ["The giant statue's eyes glow red."],
            "triggers": [
                {
                    "id": "statue_inspect",
                    "condition": "Player interacts with giant_statue",
                    "event": "The statue attacks."
                }
            ]
        }
    elif "DUNGEON MASTER" in system_prompt:
        return {
            "narrative": "A voice echoes: 'Mock response from the DM!'",
            "speaker": "SYSTEM",
            "new_entity_states": {},
            "js_injection": "console.log('Mock DM injection executed');"
        }
    return {}
