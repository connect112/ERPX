"""
The writing rules: a caption that arrives as one block gets paragraph breaks, the hashtags are tidied (no repeats, at most one of
the over-used broad tags), and the AI is briefed on short carousels, consistent step numbers, a hook line and a specific call to
action.
"""

import json

import pytest

from modules.social_media import studio
from packages.ai.client import AICompletionResult

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
BLOCK = (
    "A SOC analyst job is mostly about attention, not action. They spend hours watching dashboards that show logins, network "
    "traffic and system events. Most of what they see is normal, so the real skill is spotting the one alert that is not. "
    "When something looks off, they dig into logs to understand what happened. If it is real, they escalate it with clear "
    "evidence. Then they write it all down so the next shift knows exactly what happened."
)


def test_one_block_of_text_gets_a_hook_line_and_short_paragraphs():
    out = studio.format_caption(BLOCK)
    paragraphs = out.split("\n\n")
    assert paragraphs[0] == "A SOC analyst job is mostly about attention, not action."
    assert len(paragraphs) == 4 and all(len(p) < 260 for p in paragraphs)
    assert " ".join(out.split()) == " ".join(BLOCK.split()), "no words are added or lost"


def test_a_caption_that_already_has_paragraphs_or_is_short_is_left_alone():
    broken = "Hook line.\n\nSecond paragraph that is long enough. " * 10
    assert studio.format_caption(broken) == broken.strip()
    assert studio.format_caption("Short one. Two. Three. Four.") == "Short one. Two. Three. Four."


def test_hashtags_have_no_repeats_at_most_one_broad_tag_and_at_most_seven():
    tags = ["SOC", "CyberSecurity", "InfoSec", "BlueTeam", "soc", "#ThreatDetection", "a1", "b1", "c1", "d1"]
    out = studio.tidy_hashtags(tags)
    assert out[:4] == ["SOC", "CyberSecurity", "BlueTeam", "ThreatDetection"]
    assert len(out) == 7 and "InfoSec" not in out and out.count("SOC") == 1


def test_the_ai_is_briefed_on_short_carousels_numbered_steps_a_hook_and_a_specific_call_to_action():
    from modules.social_media.models import SocialSettings
    from modules.social_media import defaults

    settings = SocialSettings(brand=defaults.DEFAULT_BRAND, design_rules=defaults.DEFAULT_DESIGN_RULES, prohibited_claims=[])
    system = studio.build_system(settings, "carousel", None, None)
    assert "4 to 6 short slides" in system and "Never more than 6 slides" in system
    assert "Step 1:" in system and "unnumbered takeaway" in system
    assert "hook of under 90 characters" in system and "at most ONE of the very broad tags" in system
    assert 'Never a generic "follow us for more"' in system


class FakeAI:
    def __init__(self, answer):
        self.answer = answer

    async def complete(self, system_prompt, messages, max_tokens=None, temperature=0.7, timeout=None):
        return AICompletionResult(text=json.dumps(self.answer), model="fake-model", input_tokens=1500, output_tokens=700)


async def test_a_generated_draft_comes_back_with_paragraphs_and_tidy_hashtags(client, auth_headers, monkeypatch):
    answer = {
        "hooks": ["What does a SOC analyst do?"],
        "headline": "What does a SOC analyst do all day?",
        "caption": BLOCK,
        "cta": "Save this if you want a SOC career.",
        "hashtags": ["SOC", "CyberSecurity", "InfoSec", "BlueTeam"],
        "thumbnail_text": "What does a SOC analyst do?",
        "support_line": "They watch alerts and escalate what matters.",
        "visual_direction": "",
        "alt_text": "Text: What does a SOC analyst do all day?",
        "slides": [],
        "objective": "Explain the job.",
        "claims": [],
    }
    monkeypatch.setattr(studio, "get_ai_client", lambda: FakeAI(answer))
    response = await client.post(f"{_BASE}/studio/generate", json={"topic": "What does a SOC analyst do all day?", "format": "image", "pillar": "soc"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    content = response.json()["content"]
    assert content["caption"].count("\n\n") == 3 and content["hashtags"] == ["SOC", "CyberSecurity", "BlueTeam"]
