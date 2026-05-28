from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_local_env(base_dir: Path | None = None) -> bool:
    root = base_dir or Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.exists():
        return False
    return bool(load_dotenv(env_path, override=False))
