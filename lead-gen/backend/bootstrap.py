from __future__ import annotations

import os
from pathlib import Path


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def configure_runtime() -> None:
    """
    Configure runtime env vars early (before importing CrewAI/LiteLLM).

    Why:
    - CrewAI stores state in an appdirs user_data_dir (often under $HOME/.local/share).
      In some sandboxed/containerized environments $HOME can be read-only, which causes
      "Database initialization error: unable to open database file".
    - LiteLLM may try to fetch a remote model cost map; this should be optional.
    """

    # Avoid LiteLLM remote fetches (uses packaged backup instead).
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")

    # Suppress CrewAI tracing prompt + disable telemetry in non-interactive runs.
    os.environ.setdefault("CREWAI_TESTING", "true")
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")

    # Load backend-local .env deterministically, regardless of current working directory.
    # This prevents "wrong Groq org/key" confusion when starting uvicorn from a different folder.
    try:
        from dotenv import load_dotenv

        dotenv_path = Path(__file__).resolve().parent / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=False)
    except Exception:
        # dotenv is optional at runtime; ignore if unavailable.
        pass

    # Prefer a project-local, writable XDG data/cache home to keep CrewAI storage working.
    base_dir = Path(os.environ.get("LEADGEN_RUNTIME_DIR", "")) if os.environ.get("LEADGEN_RUNTIME_DIR") else None
    if not base_dir:
        base_dir = Path(__file__).resolve().parent / ".runtime"

    # Match project conventions: lead-gen/backend/.runtime/{data,cache}
    data_dir = base_dir / "data"
    cache_dir = base_dir / "cache"

    # Only override if not already set by the user.
    if "XDG_DATA_HOME" not in os.environ:
        _ensure_dir(data_dir)
        os.environ["XDG_DATA_HOME"] = str(data_dir)
    if "XDG_CACHE_HOME" not in os.environ:
        _ensure_dir(cache_dir)
        os.environ["XDG_CACHE_HOME"] = str(cache_dir)
