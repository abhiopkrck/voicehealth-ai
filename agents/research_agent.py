"""
VoiceHealth AI — Research Agent (SMART AGENTIC VERSION)
- Groq generates the best search query intelligently
- STRICT anti-hallucination prompt to prevent mixing diseases
- Relevance gating ensures only accurate data passes
"""

import httpx
import asyncio
from typing import Optional
from core.config import settings

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
SERPER_URL = "https://google.serper.dev/search"
HEADERS    = {"X-API-KEY": settings.SERPER_API_KEY, "Content-Type": "application/json"}

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_HEADERS = {
    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# ─────────────────────────────────────────────
# AI QUERY GENERATOR (The strict brain)
# ─────────────────────────────────────────────
async def generate_smart_search_query(symptoms: str, location: str) -> str:
    """Groq intelligently creates the best possible search query without mixing diseases."""
    prompt = f"""
You are an expert public health researcher.
User symptoms: {symptoms}
Location: {location}

Translate the symptoms into ONE short, highly targeted Google search query (max 8-10 words) to find official local health alerts.

CRITICAL RULES:
1. Diagnose the broad category of the symptoms (e.g., heat-related, viral/respiratory, vector-borne, or water-borne).
2. Format the query strictly like this: [Location] [1 or 2 specific medical keywords] (outbreak OR alert OR advisory)
3. DO NOT mix unrelated conditions. If the symptoms are clearly heat-related, do NOT include flu or mosquito diseases.
4. Keep it short. Google search fails if there are too many words.

Return ONLY the exact query string. No preamble.
"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,  # Strict robotic output
        "max_tokens": 50
    }

    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=GROQ_HEADERS)
            resp.raise_for_status()
            query = resp.json()["choices"][0]["message"]["content"].strip()
            
            # Clean up any accidental quotes the LLM might add
            query = query.replace('"', '').replace("'", "")
            
            print(f"[QUERY GENERATOR] 🧠 AI created query → {query}")
            return query
    except Exception as e:
        print(f"[QUERY GENERATOR] ⚠️ Groq failed: {e} → using fallback")
        return f"{location} {symptoms} (outbreak OR alert OR advisory)"


# ─────────────────────────────────────────────
# SERPER HELPER
# ─────────────────────────────────────────────
async def serper_search(query: str, num: int = 10) -> list[dict]:
    payload = {"q": query, "num": num, "tbs": "qdr:m3"}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(SERPER_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json().get("organic", [])


# ─────────────────────────────────────────────
# RELEVANCE HELPERS
# ─────────────────────────────────────────────
def relevance_score(results: list[dict], symptoms: str, location: str) -> int:
    symptom_words = set(symptoms.lower().split())
    location_words = set(location.lower().split())
    health_keywords = {
        "outbreak", "alert", "advisory", "cases", "dengue", "malaria", "chikungunya",
        "fever", "heatwave", "heat", "dizziness", "sunstroke", "flu", "influenza",
        "h3n2", "h1n1", "respiratory", "cough", "health", "idsp", "mohfw", "ncdc"
    }

    score = 0
    for r in results:
        text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
        has_symptom = any(kw in text for kw in symptom_words | health_keywords)
        has_location = any(kw in text for kw in location_words)
        if has_symptom and has_location:
            score += 1
    return score


def deduplicate(results: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for r in results:
        link = r.get("link", "")
        if link not in seen:
            seen.add(link)
            unique.append(r)
    return unique


def format_for_llm(results: list[dict], source_label: str) -> list[dict]:
    return [
        {
            "source": source_label,
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "link": r.get("link", ""),
        }
        for r in results
    ]


# ─────────────────────────────────────────────
# PRIORITY FUNCTIONS
# ─────────────────────────────────────────────
async def p1_idsp_serper(smart_query: str) -> Optional[list[dict]]:
    query = f"{smart_query} site:idsp.mohfw.gov.in"
    print(f"[P1] IDSP Official: {query}")
    results = await serper_search(query, num=10)
    return format_for_llm(results, "IDSP Official (Serper)") if results else None


async def p2_mohfw_serper(smart_query: str) -> Optional[list[dict]]:
    print(f"[P2] Broad MoHFW/NCDC: {smart_query}")
    results = await serper_search(smart_query, num=10)
    return format_for_llm(results, "MoHFW/NCDC (Serper)") if results else None


async def p4_news_search(smart_query: str) -> Optional[list[dict]]:
    print(f"[P4] News: {smart_query}")
    results = await serper_search(smart_query, num=8)
    return format_for_llm(results, "News Sources") if results else None


# ─────────────────────────────────────────────
# STATIC FALLBACK
# ─────────────────────────────────────────────
def p5_static_fallback(symptoms: str, location: str) -> list[dict]:
    print("[P5] ⚠️ Using static fallback.")
    return [{
        "source": "Static Fallback",
        "title": "No recent official data found",
        "snippet": f"No major outbreaks reported in official records for {location} in the last 3 months related to {symptoms}.",
        "link": "https://idsp.mohfw.gov.in"
    }]


# ─────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ─────────────────────────────────────────────
async def research_agent(symptoms: str, location: str) -> dict:
    print(f"\n{'='*60}")
    print(f"🚀 Research Agent Started | Location: {location} | Symptoms: {symptoms}")
    print(f"{'='*60}")

    # 1. Let AI create perfect query
    smart_query = await generate_smart_search_query(symptoms, location)

    # 2. Run all searches in parallel
    p1_res, p2_res, p4_res = await asyncio.gather(
        p1_idsp_serper(smart_query),
        p2_mohfw_serper(smart_query),
        p4_news_search(smart_query),
        return_exceptions=True
    )

    # 3. Score and filter candidates
    candidates = []
    for priority, label, res in [
        (1, "IDSP Official (Serper)", p1_res),
        (2, "MoHFW/NCDC (Serper)", p2_res),
        (4, "News Sources", p4_res),
    ]:
        if isinstance(res, list) and res:
            score = relevance_score(res, symptoms, location)
            if score >= 2:                                      
                candidates.append((priority, label, res, score))
                print(f"[SCORE] P{priority} → {score} relevance hits")

    if candidates:
        # Pick best (higher relevance wins, tie broken by priority)
        best = max(candidates, key=lambda x: (x[3], -x[0]))
        priority, label, data, score = best
        print(f"[ORCHESTRATOR] ✅ P{priority} selected ({score} hits) — {label}")
        return {
            "data": deduplicate(data),
            "source_priority": priority,
            "source_label": label,
        }

    # 4. Final fallback
    print("[ORCHESTRATOR] ⚠️ All sources failed → Static fallback")
    return {
        "data": p5_static_fallback(symptoms, location),
        "source_priority": 5,
        "source_label": "Static Fallback",
    }


# ─────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        payload = await research_agent("headache, hot feeling inside the body", "Pune")
        print(f"\n✅ Final: P{payload['source_priority']} — {payload['source_label']}")
        for item in payload["data"]:
            print(f"🔹 {item['title']}")
            
    asyncio.run(test())