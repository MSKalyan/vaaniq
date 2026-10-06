"""Sarvam realtime protocol tests that need no network.

Covers the parts of the STT/TTS providers that are pure functions: the STT query
string (including JSON key-terms encoding) and TTS message classification.
"""

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from app.integrations.sarvam.client import SarvamError
from app.integrations.sarvam.stt import SarvamRealtimeSTT
from app.integrations.sarvam.tts import SarvamTTS, _classify

API_KEY = "test-key"


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


def test_stt_query_contains_required_parameters():
    stt = SarvamRealtimeSTT(api_key=API_KEY, language="te-IN", sample_rate=8000)

    query = _query(stt._build_url())

    assert query["language_code"] == ["te-IN"]
    assert query["sample_rate"] == ["8000"]
    assert query["endpointing"] == ["vad"]
    assert query["encoding"]
    assert query["stream_type"] == ["fast"]
    assert query["model"]


def test_stt_url_is_not_corrupted_by_json_key_terms():
    """keyterms is JSON; unencoded quotes/brackets would break the query string."""
    key_terms = ["Nenu AI Kadu", "Bengaluru", "3BHK"]
    stt = SarvamRealtimeSTT(api_key=API_KEY, key_terms=key_terms)

    url = stt._build_url()
    query = _query(url)

    assert json.loads(query["keyterms"][0]) == key_terms
    assert url.count("?") == 1


def test_stt_rejects_unsupported_sample_rate():
    stt = SarvamRealtimeSTT(api_key=API_KEY, sample_rate=44100)

    with pytest.raises(SarvamError):
        stt._build_url()


def test_stt_defaults_to_a_concrete_language_code():
    """`auto` is not a documented language_code; the default must be valid on its own."""
    query = _query(SarvamRealtimeSTT(api_key=API_KEY)._build_url())

    assert query["language_code"] == ["en-IN"]


def test_tts_url_carries_model_and_completion_flag():
    """websockets.connect() has no additional_query, so params must be in the URI."""
    tts = SarvamTTS(api_key=API_KEY, model="bulbul:v2")

    query = _query(tts._build_url())

    assert query["model"] == ["bulbul:v2"]
    assert query["send_completion_event"] == ["true"]


def test_tts_classifies_audio_messages():
    import base64

    payload = base64.b64encode(b"pcm-bytes").decode()
    raw = json.dumps({"type": "audio", "data": {"audio": payload}})

    assert _classify(raw) == ("audio", payload)


def test_tts_classifies_terminal_messages():
    for raw, expected in [
        (json.dumps({"type": "completion"}), "completion"),
        (json.dumps({"type": "close"}), "close"),
        (json.dumps({"event_type": "final"}), "final"),
    ]:
        kind, _ = _classify(raw)
        assert kind == expected


def test_tts_classifies_errors():
    kind, payload = _classify(json.dumps({"type": "error", "message": "bad voice"}))

    assert kind == "error"
    assert payload == "bad voice"


def test_tts_classifies_junk_as_unknown():
    for raw in ["not json", b"binary", json.dumps([1, 2, 3]), json.dumps({"type": "x"})]:
        assert _classify(raw)[0] == "unknown"


def test_tts_rejects_text_over_the_api_limit():
    tts = SarvamTTS(api_key=API_KEY)

    import asyncio
    from collections.abc import AsyncIterator

    async def drain() -> None:
        stream: AsyncIterator[bytes] = tts.synthesize_stream(text="x" * 2501)
        async for _ in stream:
            pass

    with pytest.raises(ValueError):
        asyncio.run(drain())


def test_tts_requires_an_api_key():
    tts = SarvamTTS(api_key="")

    import asyncio
    from collections.abc import AsyncIterator

    async def drain() -> None:
        stream: AsyncIterator[bytes] = tts.synthesize_stream(text="hello")
        async for _ in stream:
            pass

    with pytest.raises(SarvamError):
        asyncio.run(drain())
