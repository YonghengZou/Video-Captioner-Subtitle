import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class SiliconFlowError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str


def load_dotenv(path: Path | None = None) -> None:
    env_file = path or PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key:
        raise SiliconFlowError(
            "SILICONFLOW_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return Settings(
        api_key=api_key,
        base_url=os.environ.get("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        model=os.environ.get("SILICONFLOW_MODEL", DEFAULT_MODEL),
    )


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    timeout: int = 300,
) -> str:
    settings = get_settings()
    payload = json.dumps(
        {
            "model": model or settings.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{settings.base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SiliconFlowError(f"SiliconFlow returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SiliconFlowError(f"Could not reach SiliconFlow: {exc.reason}") from exc

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise SiliconFlowError(f"Unexpected response shape: {body}") from exc


@dataclass(frozen=True)
class Segment:
    text: str
    start: float
    end: float


def asr(
    audio_path: str | Path,
    *,
    model: str | None = None,
    language: str = "zh",
) -> str:
    settings = get_settings()
    boundary = f"----KiloBoundary-{uuid.uuid4().hex}"
    audio_bytes = Path(audio_path).read_bytes()
    lines: list[bytes] = []
    lines.append(f"--{boundary}".encode())
    lines.append(
        b'Content-Disposition: form-data; name="file"; filename="audio.wav"'
    )
    lines.append(b"Content-Type: audio/wav")
    lines.append(b"")
    lines.append(audio_bytes)
    lines.append(f"--{boundary}".encode())
    lines.append(b'Content-Disposition: form-data; name="model"')
    lines.append(b"")
    lines.append((model or DEFAULT_ASR_MODEL).encode())
    lines.append(f"--{boundary}".encode())
    lines.append(b'Content-Disposition: form-data; name="language"')
    lines.append(b"")
    lines.append(language.encode())
    lines.append(f"--{boundary}".encode())
    lines.append(b'Content-Disposition: form-data; name="response_format"')
    lines.append(b"")
    lines.append(b"json")
    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    body = b"\r\n".join(lines)

    request = urllib.request.Request(
        f"{settings.base_url}/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            resp_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SiliconFlowError(f"SiliconFlow ASR returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SiliconFlowError(f"Could not reach SiliconFlow ASR: {exc.reason}") from exc

    try:
        return resp_body["text"].strip()
    except (KeyError, TypeError) as exc:
        raise SiliconFlowError(f"Unexpected ASR response shape: {resp_body}") from exc
