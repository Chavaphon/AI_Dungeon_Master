"""Ollama client wrapper (WBS 6.1): the frozen configuration reaches every
request, transport failures are retried a bounded number of times, and a
stalled generation raises instead of hanging the run.

No test calls a model. The fake server is an httpx.MockTransport, except in the
stall test, which uses a local socket that never answers.

Run: pytest tests/orchestration/test_client.py -v
"""

import json
import socket
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from adm.orchestration import client as cl

Doc = dict[str, Any]
Handler = Callable[[httpx.Request], httpx.Response]

CONFIG = cl.load_model_config()
MESSAGES = [
    {"role": "system", "content": "You are the Dungeon Master."},
    {"role": "user", "content": "I look around the cellar"},
]
SAMPLING = {
    "top_p": 1.0,
    "top_k": 0,
    "min_p": 0.0,
    "repeat_penalty": 1.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}


class FakeTime:
    """A clock that moves only when slept on or advanced by a handler."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _chat_reply(content: str = '{"tool": null}', **extra: Any) -> httpx.Response:
    body = {
        "model": CONFIG.model,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 1500,
        "eval_count": 40,
        **extra,
    }
    return httpx.Response(200, json=body)


def _client(handler: Handler, fake: FakeTime | None = None) -> cl.OllamaClient:
    fake = fake or FakeTime()
    return cl.OllamaClient(
        CONFIG,
        host="http://ollama.test",
        transport=httpx.MockTransport(handler),
        sleep=fake.sleep,
        clock=fake.clock,
    )


def _sequence(*steps: Handler | httpx.Response) -> tuple[Handler, list[httpx.Request]]:
    """A handler that answers each request with the next step and records it."""
    seen: list[httpx.Request] = []
    pending = list(steps)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        step = pending.pop(0)
        return step(request) if callable(step) else step

    return handler, seen


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


def _body(request: httpx.Request) -> Doc:
    return json.loads(request.content)


# --- configuration ---


def test_config_is_loaded_from_model_json() -> None:
    raw = json.loads(cl.CONFIG_PATH.read_text(encoding="utf-8"))
    assert CONFIG.model_dump() == raw


def test_config_rejects_unknown_keys(tmp_path: Any) -> None:
    raw = json.loads(cl.CONFIG_PATH.read_text(encoding="utf-8"))
    path = tmp_path / "model.json"
    path.write_text(json.dumps({**raw, "extra": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        cl.load_model_config(path)


# --- request options ---


@pytest.mark.parametrize(
    ("phase", "temperature", "num_predict"),
    [
        ("toolcall", 0.0, CONFIG.toolcall_max_tokens),
        ("narration", CONFIG.temperature, CONFIG.narration_max_tokens),
        ("summary", 0.0, cl.SUMMARY_MAX_TOKENS),
    ],
)
def test_options_per_phase(phase: cl.Phase, temperature: float, num_predict: int) -> None:
    assert cl.build_options(CONFIG, phase, 12345) == {
        "num_ctx": 8192,
        "num_predict": num_predict,
        "temperature": temperature,
        "seed": 12345,
        **SAMPLING,
    }


def test_phase_values_match_claude_md() -> None:
    assert cl.build_options(CONFIG, "toolcall", 0)["temperature"] == 0.0
    assert cl.build_options(CONFIG, "toolcall", 0)["num_predict"] == 200
    assert cl.build_options(CONFIG, "narration", 0)["temperature"] == 0.7
    assert cl.build_options(CONFIG, "narration", 0)["num_predict"] == 300
    assert cl.build_options(CONFIG, "summary", 0)["num_predict"] == 200


def test_config_seed_overrides_run_seed() -> None:
    pinned = CONFIG.model_copy(update={"seed": 7})
    assert cl.build_options(pinned, "toolcall", 12345)["seed"] == 7


@pytest.mark.parametrize("seed", [0, 12345, cl.MAX_SEED])
def test_seed_in_range_is_accepted(seed: int) -> None:
    assert cl.build_options(CONFIG, "toolcall", seed)["seed"] == seed


@pytest.mark.parametrize("seed", [-1, -12345, cl.MAX_SEED + 1])
def test_seed_out_of_range_is_rejected(seed: int) -> None:
    """-1 reaches llama.cpp as 0xFFFFFFFF, its "random seed" value."""
    with pytest.raises(ValueError, match="seed"):
        cl.build_options(CONFIG, "toolcall", seed)


def test_chat_request_body() -> None:
    handler, seen = _sequence(_chat_reply())
    with _client(handler) as client:
        client.chat(MESSAGES, phase="narration", seed=42)

    (request,) = seen
    assert request.method == "POST"
    assert request.url.path == "/api/chat"
    assert _body(request) == {
        "model": CONFIG.model,
        "messages": MESSAGES,
        "stream": False,
        "keep_alive": -1,
        "options": cl.build_options(CONFIG, "narration", 42),
    }


def test_chat_sends_no_think_or_format_field() -> None:
    handler, seen = _sequence(_chat_reply())
    with _client(handler) as client:
        client.chat(MESSAGES, phase="toolcall", seed=0)
    assert "think" not in _body(seen[0])
    assert "format" not in _body(seen[0])


def test_chat_and_load_timeouts_are_finite() -> None:
    """A non-streaming reply arrives in one piece, so the read timeout bounds generation."""
    handler, seen = _sequence(_chat_reply())
    with _client(handler) as client:
        client.chat(MESSAGES, phase="toolcall", seed=0)
    timeout = seen[0].extensions["timeout"]
    assert timeout["read"] == cl.CHAT_TIMEOUT_S
    assert timeout["connect"] == cl.CONNECT_TIMEOUT_S


# --- replies ---


def test_reply_fields() -> None:
    fake = FakeTime()

    def answer(request: httpx.Request) -> httpx.Response:
        fake.now += 1.2345
        return _chat_reply('{"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}')

    handler, _ = _sequence(answer)
    with _client(handler, fake) as client:
        reply = client.chat(MESSAGES, phase="toolcall", seed=0)

    assert reply == cl.ModelReply(
        raw_output='{"tool": "dodge", "arguments": {"actor_id": "pc_lyra"}}',
        prompt_tokens=1500,
        completion_tokens=40,
        latency_ms=1234,
        done_reason="stop",
        transport_retries=0,
    )


def test_missing_token_counts_are_zero() -> None:
    response = httpx.Response(200, json={"message": {"role": "assistant", "content": "Hi."}})
    handler, _ = _sequence(response)
    with _client(handler) as client:
        reply = client.chat(MESSAGES, phase="narration", seed=0)
    assert (reply.prompt_tokens, reply.completion_tokens, reply.done_reason) == (0, 0, None)


def test_length_cap_is_reported() -> None:
    handler, _ = _sequence(_chat_reply("A long summary", done_reason="length"))
    with _client(handler) as client:
        assert client.chat(MESSAGES, phase="summary", seed=0).done_reason == "length"


# --- retries ---


def test_timeout_then_success_is_retried_and_flagged() -> None:
    fake = FakeTime()
    handler, seen = _sequence(_timeout, _chat_reply())
    with _client(handler, fake) as client:
        reply = client.chat(MESSAGES, phase="toolcall", seed=0)
    assert len(seen) == 2
    assert reply.transport_retries == 1
    assert fake.sleeps == [cl.RETRY_BACKOFF_S[0]]


def test_server_errors_are_retried() -> None:
    def busy(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "server busy"})

    handler, seen = _sequence(busy, busy, _chat_reply())
    with _client(handler) as client:
        reply = client.chat(MESSAGES, phase="toolcall", seed=0)
    assert len(seen) == 3
    assert reply.transport_retries == 2


def test_connection_error_is_retried() -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    handler, _ = _sequence(refused, _chat_reply())
    with _client(handler) as client:
        assert client.chat(MESSAGES, phase="toolcall", seed=0).transport_retries == 1


def test_retries_are_bounded() -> None:
    fake = FakeTime()
    handler, seen = _sequence(_timeout, _timeout, _timeout, _chat_reply())
    with _client(handler, fake) as client, pytest.raises(cl.ModelUnavailable, match="ReadTimeout"):
        client.chat(MESSAGES, phase="toolcall", seed=0)
    assert len(seen) == 1 + cl.MAX_TRANSPORT_RETRIES
    assert fake.sleeps == list(cl.RETRY_BACKOFF_S)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"error": "model not found"}),
        httpx.Response(400, json={"error": "bad request"}),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"done": True}),
        httpx.Response(200, json={"message": {"role": "assistant", "content": None}}),
    ],
)
def test_bad_reply_is_not_retried(response: httpx.Response) -> None:
    handler, seen = _sequence(response, _chat_reply())
    with _client(handler) as client, pytest.raises(cl.ModelProtocolError):
        client.chat(MESSAGES, phase="toolcall", seed=0)
    assert len(seen) == 1


def test_stalled_generation_does_not_hang() -> None:
    """WBS 6.1 done-when: a server that accepts the request and never replies."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", 0))
        server.listen(8)  # the kernel completes the connection; nothing ever answers
        host, port = server.getsockname()
        fake = FakeTime()
        client = cl.OllamaClient(
            CONFIG,
            host=f"http://{host}:{port}",
            chat_timeout=0.2,
            sleep=fake.sleep,
        )
        started = time.monotonic()
        with client, pytest.raises(cl.ModelUnavailable, match="ReadTimeout"):
            client.chat(MESSAGES, phase="toolcall", seed=0)
        assert time.monotonic() - started < 10
        assert len(fake.sleeps) == cl.MAX_TRANSPORT_RETRIES
    finally:
        server.close()


# --- verify ---


def _tags(digest: str = CONFIG.model_digest.removeprefix("sha256:")) -> httpx.Response:
    return httpx.Response(200, json={"models": [{"name": CONFIG.model, "digest": digest}]})


def _version(version: str = CONFIG.ollama_version) -> httpx.Response:
    return httpx.Response(200, json={"version": version})


def test_verify_passes_on_pinned_version_and_digest() -> None:
    handler, seen = _sequence(_version(), _tags())
    with _client(handler) as client:
        client.verify()
    assert [r.url.path for r in seen] == ["/api/version", "/api/tags"]


def test_verify_accepts_prefixed_digest() -> None:
    handler, _ = _sequence(_version(), _tags(CONFIG.model_digest))
    with _client(handler) as client:
        client.verify()


@pytest.mark.parametrize(
    ("version", "tags", "match"),
    [
        (_version("0.36.0"), _tags(), "0.36.0"),
        (_version(), _tags("0" * 64), "digest"),
        (_version(), httpx.Response(200, json={"models": []}), "not installed"),
    ],
)
def test_verify_rejects_mismatch(version: httpx.Response, tags: httpx.Response, match: str) -> None:
    handler, _ = _sequence(version, tags)
    with _client(handler) as client, pytest.raises(cl.ModelConfigMismatch, match=match):
        client.verify()


# --- fresh load ---


def _ps(loaded: bool) -> httpx.Response:
    models = [{"name": CONFIG.model, "size": 1000, "size_vram": 1000}] if loaded else []
    return httpx.Response(200, json={"models": models})


def _done() -> httpx.Response:
    return httpx.Response(200, json={"model": CONFIG.model, "done": True})


def test_fresh_load_unloads_then_loads() -> None:
    fake = FakeTime()
    handler, seen = _sequence(_done(), _ps(True), _ps(False), _done(), _ps(True))
    with _client(handler, fake) as client:
        gpu_share = client.fresh_load()

    assert gpu_share == 1.0
    assert [(r.method, r.url.path) for r in seen] == [
        ("POST", "/api/generate"),
        ("GET", "/api/ps"),
        ("GET", "/api/ps"),
        ("POST", "/api/generate"),
        ("GET", "/api/ps"),
    ]
    assert _body(seen[0]) == {"model": CONFIG.model, "keep_alive": 0, "stream": False}
    assert _body(seen[3]) == {
        "model": CONFIG.model,
        "keep_alive": -1,
        "stream": False,
        "options": {"num_ctx": 8192},
    }
    assert seen[3].extensions["timeout"]["read"] == cl.LOAD_TIMEOUT_S
    assert fake.sleeps == [cl.UNLOAD_POLL_S]


def test_fresh_load_gives_up_if_the_model_never_unloads() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _ps(True) if request.url.path == "/api/ps" else _done()

    fake = FakeTime()
    with _client(handler, fake) as client, pytest.raises(cl.ModelUnavailable, match="unload"):
        client.fresh_load()
    assert fake.now >= cl.UNLOAD_WAIT_S


def test_fresh_load_fails_if_the_model_does_not_load() -> None:
    handler, _ = _sequence(_done(), _ps(False), _done(), _ps(False))
    with _client(handler) as client, pytest.raises(cl.ModelUnavailable, match="not loaded"):
        client.fresh_load()
