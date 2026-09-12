"""No prompt file may contain nationality-persona constructions -- the exact pattern
imported from MAD (sec5_infer_api.py:138) / CultureSPA (utils.py:35) that RoomBridge exists
to avoid (plan sections 1.3, 10 failure mode 1)."""
import re
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "roombridge" / "prompts"

BANNED = [
    re.compile(r"you are a respondent from", re.I),
    re.compile(r"typical .{0,20}values in .{0,20}culture", re.I),
    re.compile(r"answer .{0,30}based on .{0,20}cultural values", re.I),
    re.compile(r"you are a .{0,20}(person|respondent) (with|from) .{0,20}"
               r"(national|cultural) background", re.I),
]


def test_no_prompt_contains_nationality_persona():
    offenders = []
    for f in PROMPT_DIR.glob("*.md"):
        text = f.read_text()
        for pat in BANNED:
            if pat.search(text):
                offenders.append((f.name, pat.pattern))
    assert not offenders, f"banned persona prompt patterns found: {offenders}"
