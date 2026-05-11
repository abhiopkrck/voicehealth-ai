"""
agents/synthesis_agent.py
Agent 4: Synthesis — Writes the final localised health advisory script.
Uses ONLY Groq (llama-3.3-70b-versatile).
Fully compatible with the current research_agent.py
"""

import httpx
import asyncio
from pathlib import Path
from core.config import settings
from typing import Dict, Any

PROMPT_PATH = Path("prompts/synthesis_prompt.txt")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Shown only if Groq also fails
HARD_FALLBACK = (
    "क्षमा करें, तकनीकी समस्या के कारण मैं अभी जानकारी नहीं दे पा रहा हूँ। "
    "कृपया नजदीकी डॉक्टर से संपर्क करें।"
)


def _build_prompt(
    location: str,
    symptoms: str,
    search_data: list,
    target_language: str,
    research_payload: Dict[str, Any]
) -> str:
    """Builds the prompt using your synthesis_prompt.txt"""
    data_str = "\n".join(
        f"- [{item.get('source', 'Unknown')}] {item.get('title', '')}: {item.get('snippet', '')}"
        for item in search_data
    ) or "No official records found."

    template = PROMPT_PATH.read_text(encoding="utf-8")

    base_prompt = template.format(
        location=location,
        symptoms=symptoms,
        all_combined_search_data=data_str,
        source_priority=research_payload.get("source_priority", 5),
        source_label=research_payload.get("source_label", "Static Fallback")
    )
    
    # ADDED BACK: Forces the LLM to output in the requested target language
    return base_prompt + f"\n\nCRITICAL: Write the final audio script entirely in the {target_language} language."


async def synthesis_agent(
    location: str,
    symptoms: str,
    search_data: list,
    target_language: str,
    research_payload: Dict[str, Any],
    max_retries: int = 3,
) -> str:
    """
    Uses ONLY Groq.
    Fully compatible with current research_agent.py
    """
    print(f"[SYNTHESIS] Generating {target_language} advisory using Groq...")

    prompt = _build_prompt(location, symptoms, search_data, target_language, research_payload)

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3, # CHANGED BACK TO 0.3 TO PREVENT HALLUCINATIONS/FORMATTING ISSUES
        "max_tokens": 600,
    }

    for attempt in range(max_retries):
        try:
            print(f"[SYNTHESIS] Groq attempt {attempt + 1}...")
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(GROQ_URL, headers=headers, json=payload)
                resp.raise_for_status()

            text = resp.json()["choices"][0]["message"]["content"].strip()
            print("[SYNTHESIS] ✅ Groq succeeded.")
            return text

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"[SYNTHESIS] Groq rate limit — retrying in {wait}s...")
                await asyncio.sleep(wait)
                continue
            print(f"[SYNTHESIS] Groq failed ({e.response.status_code})")
            break

        except Exception as e:
            print(f"[SYNTHESIS] Groq error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
                continue
            break

    print("[SYNTHESIS] Groq failed completely.")
    return HARD_FALLBACK


# Quick test
if __name__ == "__main__":
    import asyncio
    async def test():
        fake_payload = {
            "data": [{"source": "News Sources", "title": "H3N2 surge", "snippet": "Rising H3N2 cases in Jaipur with fever and cough"}],
            "source_priority": 4,
            "source_label": "News Sources"
        }
        result = await synthesis_agent(
            location="Jaipur",
            symptoms="high fever chills cough headache",
            search_data=fake_payload["data"],
            target_language="Hindi",
            research_payload=fake_payload
        )
        print("\n=== FINAL OUTPUT ===\n", result)

    asyncio.run(test())