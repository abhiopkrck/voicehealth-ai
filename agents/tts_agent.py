"""
agents/tts_agent.py
Agent 5: TTS — converts final text to audio using Sarvam AI (Indic TTS).
Sarvam AI is recommended over Bhashini for live demos — faster and more stable.
"""

import base64
import httpx
from core.config import settings

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"

VOICE_MAP = {
    "hi": "meera",   # Hindi female voice
    "ta": "arjun",   # Tamil voice
    "en": "meera",   # Fallback
}

async def tts_agent(text: str, language: str = "hi") -> str:
    """
    Converts text to speech using Sarvam AI.

    Args:
        text: Final advisory text (in Hindi or Tamil)
        language: "hi" or "ta"

    Returns:
        Base64-encoded audio string (WAV format).
    """
    headers = {
        "api-subscription-key": settings.SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": [text],
        "target_language_code": f"{language}-IN",
        "speaker": VOICE_MAP.get(language, "meera"),
        "pace": 1.0,
        "enable_preprocessing": True,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(SARVAM_TTS_URL, headers=headers, json=payload)
        resp.raise_for_status()
        audio_b64 = resp.json()["audios"][0]

    return f"data:audio/wav;base64,{audio_b64}"  # Already base64 from Sarvam
