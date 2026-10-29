"""Ollama HTTP client (WBS 6.1, CLAUDE.md section 2.2).

This is the single loader of `config/model.json` (docs/conventions.md section
1): the model name is read here and appears nowhere else in code. Every
request carries `num_ctx` and every sampling option, so that no Ollama default
leaks into a run (docs/hardware.md section 4, docs/model_selection.md section
4). No `think` or `format` field is sent: the model has no thinking capability,
and tool calls use plain prompt mode (WBS 3.7).

Replies are not streamed, so the read timeout bounds the whole generation and a
stalled server raises instead of hanging the run. Connection errors, timeouts
and 5xx replies are retried at most `MAX_TRANSPORT_RETRIES` times. A retry
reaches a server that may already have seen the request, and earlier requests
can change a reply (docs/model_selection.md section 3.2), so every reply
carries `transport_retries`: a run with any retry is not guaranteed to replay
byte-identically (invariant 4). This retry is the transport's; the turn loop's
retry budget of two (CLAUDE.md section 7.1) is separate.

`fresh_load` unloads and reloads the model. Every run calls it first, and
nothing else uses the server during the run (CLAUDE.md section 15, item 25).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "model.json"
DEFAULT_HOST = "http://localhost:11434"

Phase = Literal["toolcall", "narration", "summary"]
Message = dict[str, str]
Doc = dict[str, Any]

# Seconds. The worst case at 8192 tokens is about 6 s of prompt evaluation plus
# 5 s for 300 tokens (docs/hardware.md section 3, docs/model_benchmark.md). The
# first load after a reboot took 35 s.
CONNECT_TIMEOUT_S = 5.0
CHAT_TIMEOUT_S = 60.0
LOAD_TIMEOUT_S = 120.0

MAX_TRANSPORT_RETRIES = 2
RETRY_BACKOFF_S = (1.0, 2.0)

UNLOAD_POLL_S = 0.5
UNLOAD_WAIT_S = 30.0

# Tool calls and the rolling summary are sampled greedily (CLAUDE.md sections
# 2.2 and 8.1). The summary's hard cap is 200 tokens; a reply that hits it ends
# with done_reason "length", and the summary module truncates it.
TOOLCALL_TEMPERATURE = 0.0
SUMMARY_TEMPERATURE = 0.0
SUMMARY_MAX_TOKENS = 200

# llama.cpp takes the seed as uint32 and treats 0xFFFFFFFF (what -1 becomes)
# as "pick a random seed", which would silently break invariant 4.
MAX_SEED = 2**32 - 2

# Keep the model loaded however long a session idles, so that it is never
# reloaded part-way through a run.
KEEP_LOADED = -1


class ModelConfig(BaseModel):
    """The frozen values of config/model.json (WBS 3.6)."""

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    model: str
    model_digest: str
    quantisation: str
    ollama_version: str
    context_tokens: int
    K_verbatim_turns: int
    temperature: float
    narration_max_tokens: int
    toolcall_max_tokens: int
    seed: int | None


def load_model_config(path: Path = CONFIG_PATH) -> ModelConfig:
    return ModelConfig.model_validate_json(path.read_text(encoding="utf-8"))


def build_options(config: ModelConfig, phase: Phase, seed: int) -> Doc:
    """Every Ollama option, set explicitly. A non-null config seed overrides the run's."""
    seed = config.seed if config.seed is not None else seed
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be in 0..{MAX_SEED} for Ollama, got {seed}")
    temperature, num_predict = {
        "toolcall": (TOOLCALL_TEMPERATURE, config.toolcall_max_tokens),
        "narration": (config.temperature, config.narration_max_tokens),
        "summary": (SUMMARY_TEMPERATURE, SUMMARY_MAX_TOKENS),
    }[phase]
    return {
        "num_ctx": config.context_tokens,
        "num_predict": num_predict,
        "temperature": temperature,
        "top_p": 1.0,
        "top_k": 0,
        "min_p": 0.0,
        "seed": seed,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
    }


@dataclass(frozen=True)
class ModelReply:
    """One model call: what the audit record's model_call needs, plus transport facts.

    `latency_ms` is wall time and includes prompt evaluation. `eval_ms` is the
    server's generation time alone, so tokens per second (M6) is
    `completion_tokens / eval_ms`, as in the 3.4 benchmark (docs/model_benchmark.md).
    """

    raw_output: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    eval_ms: int
    done_reason: str | None
    transport_retries: int

    def model_call(self, phase: Phase, attempt: int) -> Doc:
        """The turn record's `model_calls` entry for this call (docs/audit_log.md section 1)."""
        return {
            "phase": phase,
            "attempt": attempt,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": self.latency_ms,
            "eval_ms": self.eval_ms,
            "raw_output": self.raw_output,
        }


class ModelError(Exception):
    """The model could not be used. A programming or environment error, never a turn failure."""


class ModelUnavailable(ModelError):
    """The server did not answer, even after the transport retries."""


class ModelProtocolError(ModelError):
    """The server answered with a client error or a body that is not a chat reply."""


class ModelConfigMismatch(ModelError):
    """The server's version or the model's digest is not the one config/model.json pins."""


class ModelClient(Protocol):
    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply: ...


class OllamaClient:
    def __init__(
        self,
        config: ModelConfig,
        *,
        host: str = DEFAULT_HOST,
        transport: httpx.BaseTransport | None = None,
        connect_timeout: float = CONNECT_TIMEOUT_S,
        chat_timeout: float = CHAT_TIMEOUT_S,
        load_timeout: float = LOAD_TIMEOUT_S,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.config = config
        self._http = httpx.Client(
            base_url=host,
            transport=transport,
            timeout=httpx.Timeout(chat_timeout, connect=connect_timeout),
        )
        self._load_timeout = httpx.Timeout(load_timeout, connect=connect_timeout)
        self._sleep = sleep
        self._clock = clock

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # --- model calls ---

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        body = {
            "model": self.config.model,
            "messages": list(messages),
            "stream": False,
            "keep_alive": KEEP_LOADED,
            "options": build_options(self.config, phase, seed),
        }
        response, retries, latency_ms = self._request("POST", "/api/chat", body)
        reply = _json(response)
        try:
            content = reply["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ModelProtocolError(f"/api/chat reply has no message content: {reply}") from exc
        if not isinstance(content, str):
            raise ModelProtocolError(f"/api/chat message content is not a string: {content!r}")
        return ModelReply(
            raw_output=content,
            prompt_tokens=int(reply.get("prompt_eval_count") or 0),
            completion_tokens=int(reply.get("eval_count") or 0),
            latency_ms=latency_ms,
            eval_ms=round(int(reply.get("eval_duration") or 0) / 1_000_000),
            done_reason=reply.get("done_reason"),
            transport_retries=retries,
        )

    # --- run set-up ---

    def verify(self) -> None:
        """Refuse a server or model other than the pinned one (docs/model_selection.md §4)."""
        version = _json(self._request("GET", "/api/version")[0]).get("version")
        if version != self.config.ollama_version:
            raise ModelConfigMismatch(
                f"Ollama is {version}, but config/model.json pins {self.config.ollama_version}"
            )
        installed = {
            m.get("name"): m for m in _json(self._request("GET", "/api/tags")[0]).get("models", [])
        }
        if self.config.model not in installed:
            raise ModelConfigMismatch(f"{self.config.model} is not installed in Ollama")
        digest = str(installed[self.config.model].get("digest", ""))
        if _bare(digest) != _bare(self.config.model_digest):
            raise ModelConfigMismatch(
                f"{self.config.model} has digest {digest}, "
                f"but config/model.json pins {self.config.model_digest}"
            )

    def fresh_load(self) -> float | None:
        """Unload the model, wait until it is gone, then load it. Returns its GPU share."""
        model = self.config.model
        unload = {"model": model, "keep_alive": 0, "stream": False}
        self._request("POST", "/api/generate", unload, timeout=self._load_timeout)
        deadline = self._clock() + UNLOAD_WAIT_S
        while self._loaded() is not None:
            if self._clock() >= deadline:
                raise ModelUnavailable(f"{model} did not unload within {UNLOAD_WAIT_S} s")
            self._sleep(UNLOAD_POLL_S)

        # No prompt, so loading evaluates nothing and leaves no cache behind.
        load = {
            "model": model,
            "keep_alive": KEEP_LOADED,
            "stream": False,
            "options": {"num_ctx": self.config.context_tokens},
        }
        self._request("POST", "/api/generate", load, timeout=self._load_timeout)
        loaded = self._loaded()
        if loaded is None:
            raise ModelUnavailable(f"{model} is not loaded after the load request")
        size = loaded.get("size")
        return loaded.get("size_vram", 0) / size if size else None

    # --- transport ---

    def _loaded(self) -> Doc | None:
        for entry in _json(self._request("GET", "/api/ps")[0]).get("models", []):
            if self.config.model in (entry.get("name"), entry.get("model")):
                return entry
        return None

    def _request(
        self,
        method: str,
        path: str,
        body: Doc | None = None,
        *,
        timeout: httpx.Timeout | None = None,
    ) -> tuple[httpx.Response, int, int]:
        """The response, the number of retries it took, and the last attempt's latency in ms."""
        last_error = ""
        for attempt in range(MAX_TRANSPORT_RETRIES + 1):
            if attempt:
                self._sleep(RETRY_BACKOFF_S[attempt - 1])
            started = self._clock()
            try:
                response = self._http.request(
                    method,
                    path,
                    json=body,
                    timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                )
            except httpx.TransportError as exc:  # includes every timeout
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            latency_ms = round((self._clock() - started) * 1000)
            if response.status_code >= 500:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue
            if response.is_error:
                raise ModelProtocolError(
                    f"{method} {path}: HTTP {response.status_code}: {response.text[:200]}"
                )
            return response, attempt, latency_ms
        raise ModelUnavailable(
            f"{method} {path} failed after {MAX_TRANSPORT_RETRIES + 1} attempts: {last_error}"
        )


def _json(response: httpx.Response) -> Doc:
    try:
        parsed = response.json()
    except ValueError as exc:
        raise ModelProtocolError(f"{response.request.url.path} reply is not JSON") from exc
    if not isinstance(parsed, dict):
        raise ModelProtocolError(f"{response.request.url.path} reply is not a JSON object")
    return parsed


def _bare(digest: str) -> str:
    return digest.removeprefix("sha256:")
