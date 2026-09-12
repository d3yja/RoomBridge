"""The structured-output extractor must survive real models wrapping JSON in prose,
markdown fences, or stray braces (plan: OpenRouter provider hardening)."""
import json

import pytest

from roombridge.providers.base import extract_json


@pytest.mark.parametrize("raw", [
    '[{"a":1},{"b":2}]',
    'Here you go:\n[{"need_id":"need_001"}]',
    'Note: {see} below: [{"a":1},{"c":2}]',          # stray brace before the real array
    '```json\n{"status":"preserved"}\n```',
    '{"text":"use {curly} braces","n":2}',           # braces inside a string
    '{"escalate":false}\nHope that helps!',
])
def test_extract_json_returns_parseable(raw):
    json.loads(extract_json(raw))  # must not raise
