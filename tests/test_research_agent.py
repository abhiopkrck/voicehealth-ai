"""
tests/test_research_agent.py
Tests for the research agent's 4-level priority fallback chain.
Run with: pytest tests/ -v
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.research_agent import research_agent, is_relevant, deduplicate, p5_static_fallback

# ── Unit tests ──

def test_is_relevant_returns_true_for_keyword_match():
    results = [
        {"title": "Pune dengue outbreak 2026", "snippet": "IDSP reports dengue cases"},
        {"title": "Maharashtra health advisory", "snippet": "fever cases rising in Pune"},
    ]
    assert is_relevant(results, "fever", "Pune") is True

def test_is_relevant_returns_false_for_no_match():
    results = [
        {"title": "Stock market news", "snippet": "Sensex rises today"},
    ]
    assert is_relevant(results, "fever joint pain", "Pune") is False

def test_deduplicate_removes_same_url():
    results = [
        {"link": "https://idsp.gov.in/report1", "title": "Report 1"},
        {"link": "https://idsp.gov.in/report1", "title": "Report 1 duplicate"},
        {"link": "https://idsp.gov.in/report2", "title": "Report 2"},
    ]
    assert len(deduplicate(results)) == 2

def test_p5_static_fallback_always_returns_data():
    result = p5_static_fallback("fever", "Pune")
    assert len(result) > 0
    assert result[0]["source"] == "Static Fallback"
    assert "Pune" in result[0]["snippet"]

# ── Integration test (requires real SERPER_API_KEY in .env) ──

@pytest.mark.asyncio
async def test_research_agent_returns_valid_payload():
    payload = await research_agent("fever joint pain", "Pune")
    assert "data" in payload
    assert "source_priority" in payload
    assert payload["source_priority"] in [1, 2, 4, 5]
    assert len(payload["data"]) > 0
    print(f"\n✅ Used Priority {payload['source_priority']}: {payload['source_label']}")
