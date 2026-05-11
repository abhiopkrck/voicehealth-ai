"""
agents/intake_agent.py
Agent 1: ASR — transcribes audio and translates to English using Groq.
  Step 1: Groq Whisper (whisper-large-v3)     → transcription in native language
  Step 2: Groq Llama 3.3 70b (versatile)      → English translation
Lightning fast. No Gemini RPM bottleneck.
"""

import json
import httpx
import asyncio
from core.config import settings
from core.utils import detect_language

GROQ_AUDIO_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL  = "https://api.groq.com/openai/v1/chat/completions"

GROQ_HEADERS = {
    "Authorization": f"Bearer {settings.GROQ_API_KEY}"
}

async def intake_agent(audio_bytes: bytes, filename: str = "audio.webm", max_retries: int = 3) -> dict:
    """
    Transcribes audio and translates to English using Groq.

    Returns:
        {
            "original_text":    str,  # Native language transcription (Hindi/Tamil/English)
            "english_text":     str,  # English translation for downstream agents
            "detected_language": str  # "hi", "ta", or "en"
        }
    """
    print("[INTAKE] Starting Groq processing...")

    # ── Detect MIME type from filename ──
    mime_map = {
        ".webm": "audio/webm",
        ".mp3":  "audio/mp3",
        ".wav":  "audio/wav",
        ".ogg":  "audio/ogg",
        ".m4a":  "audio/mp4",
    }
    ext       = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".webm"
    mime_type = mime_map.get(ext, "audio/webm")

    # ── Safe default in case translation loop never runs ──
    english_text = ""
    original_text = ""

    async with httpx.AsyncClient(timeout=20) as client:

        # ══════════════════════════════════════════════════
        # STEP 1: Transcribe with Groq Whisper Large V3
        # ══════════════════════════════════════════════════
        try:
            print("[INTAKE] 🎙️ Running Groq Whisper Large V3...")
            files = {"file": (filename, audio_bytes, mime_type)}
            data  = {
                "model":           "whisper-large-v3",
                "response_format": "json",
            }
            audio_resp = await client.post(
                GROQ_AUDIO_URL, headers=GROQ_HEADERS, data=data, files=files
            )
            audio_resp.raise_for_status()
            original_text = audio_resp.json().get("text", "").strip()
            print(f"[INTAKE] ✅ Whisper done. Raw: {original_text[:60]}...")

        except httpx.HTTPStatusError as e:
            print(f"❌ [INTAKE] Groq Whisper error: {e.response.text}")
            raise  # Whisper failure is fatal — can't proceed without transcription

        # Guard: if Whisper returned nothing, return early
        if not original_text:
            print("[INTAKE] ⚠️ Whisper returned empty text.")
            return {"original_text": "", "english_text": "", "detected_language": "en"}

        # ══════════════════════════════════════════════════
        # STEP 2: Translate to English with Groq Llama 3.3 70b
        # ══════════════════════════════════════════════════
        system_prompt = (
            "You are an expert medical translator specialising in Indian languages. "
            "Translate the user's raw spoken text into clear, natural English. "
            "Preserve all symptom details — do not summarise or omit anything. "
            "If the text is already in English, return it unchanged. "
            "Respond ONLY with a valid JSON object in this exact format (no markdown): "
            '{"english": "<English translation here>"}'
        )

        chat_payload = {
            "model": "llama-3.3-70b-versatile",   # 70b for accurate medical Hindi/Tamil translation
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Raw spoken text: {original_text}"}
            ],
            "response_format": {"type": "json_object"},  # Forces valid JSON — no parse failures
            "temperature": 0.1,                          # Low temp for precise translation
            "max_tokens":  300,
        }

        # ── Safe default before retry loop ──
        english_text = original_text  # Fallback: use original if translation fails

        for attempt in range(max_retries):
            try:
                print(f"[INTAKE] 📝 Running Groq Translation (attempt {attempt + 1})...")
                chat_resp = await client.post(
                    GROQ_CHAT_URL, headers=GROQ_HEADERS, json=chat_payload
                )
                chat_resp.raise_for_status()

                raw_json     = chat_resp.json()["choices"][0]["message"]["content"]
                result       = json.loads(raw_json)
                english_text = result.get("english", original_text).strip()
                print(f"[INTAKE] ✅ Translation done: {english_text[:60]}...")
                break  # Success — exit retry loop

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    print(f"⚠️ [INTAKE] Groq 429 rate limit. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                print(f"❌ [INTAKE] Groq Llama error: {e.response.text}")
                # Non-429 error — fall back to original text, don't crash
                break

            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ [INTAKE] JSON parse error: {e}. Using original text.")
                break  # english_text already set to original_text above

    detected_lang = detect_language(original_text)
    print(f"[INTAKE] ✅ Complete | Lang: {detected_lang} | English: {english_text[:60]}...")

    return {
        "original_text":     original_text,
        "english_text":      english_text,
        "detected_language": detected_lang,
    }