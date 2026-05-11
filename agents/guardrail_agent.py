"""
agents/guardrail_agent.py
Agent 2: Guardrail — Classifies emergencies and blocks direct diagnosis requests.
Powered by Groq (llama-3.3-70b-versatile) — sub-second, free tier, accurate.
"""

import json
import httpx
import asyncio
from pathlib import Path
from core.config import settings

PROMPT_PATH = Path("prompts/guardrail_prompt.txt")
GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"

GROQ_HEADERS = {
    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
    "Content-Type":  "application/json",
}

# Hardcoded emergency response — never goes through LLM
EMERGENCY_RESPONSE = (
    "मैं आपकी स्थिति समझता हूँ। यह एक आपातकालीन स्थिति लगती है। "
    "कृपया तुरंत नजदीकी अस्पताल जाएं या 112 पर कॉल करें। "
    "I cannot provide a diagnosis. Please see a doctor immediately."
)

async def guardrail_agent(english_text: str, max_retries: int = 3) -> dict:
    """
    Classifies user message as safe (B) or emergency/diagnostic (A).

    Returns:
        {
            "is_safe":             bool,
            "category":            "A" or "B",
            "extracted_symptoms":  str,
            "emergency_response":  str or None
        }
    """
    print("[GUARDRAIL] Analysing safety via Groq (llama-3.3-70b)...")

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    payload = {
        "model": "llama-3.3-70b-versatile",    # 70b for accurate Hindi medical classification
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"User message: {english_text}"}
        ],
        "response_format": {"type": "json_object"},  # Forces valid JSON — eliminates parse failures
        "temperature": 0.1,                          # Near-zero temp for strict rule following
        "max_tokens":  150,                          # Classification needs very few tokens
    }

    # ── Safe default BEFORE the retry loop ──
    # Guarantees result is always defined even if all retries fail
    result = {"category": "B", "extracted_symptoms": english_text}

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(max_retries):
            try:
                resp = await client.post(GROQ_URL, headers=GROQ_HEADERS, json=payload)
                resp.raise_for_status()

                raw_json = resp.json()["choices"][0]["message"]["content"]
                result   = json.loads(raw_json)
                print(f"[GUARDRAIL] ✅ Category {result.get('category')} | Symptoms: {result.get('extracted_symptoms', '')[:50]}")
                break  # Success — exit retry loop

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    print(f"⚠️ [GUARDRAIL] Groq 429 rate limit. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                print(f"❌ [GUARDRAIL] HTTP error: {e.response.text}")
                # Fail open to Category B — better to let a safe query through
                # than to block a real user with a non-emergency query
                break

            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ [GUARDRAIL] JSON parse error: {e}. Defaulting to safe.")
                break  # result already set to safe default above

    is_safe = result.get("category") == "B"

    return {
        "is_safe":            is_safe,
        "category":           result.get("category", "B"),
        "extracted_symptoms": result.get("extracted_symptoms", english_text),
        "emergency_response": None if is_safe else EMERGENCY_RESPONSE,
    }