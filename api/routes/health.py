"""
api/routes/health.py
Health check endpoint — useful for demo and judge verification.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/")
async def root():
    return {"status": "ok", "project": "VoiceHealth AI", "version": "1.0.0"}

@router.get("/health")
async def health_check():
    return {"status": "healthy"}
