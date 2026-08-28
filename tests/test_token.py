from pathlib import Path
import tempfile

from scripts.init_token import ensure_token
from scripts.regenerate_token import regenerate


def test_token_lifecycle(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / ".env"
        env_file.write_text("DANA_AUTH_TOKEN=GENERATE_WITH_SCRIPT\n", encoding="utf-8")
        monkeypatch.setattr("scripts.init_token.ENV_FILE", env_file)
        monkeypatch.setattr("scripts.regenerate_token.ENV_FILE", env_file)
        first = ensure_token()
        assert len(first) >= 60
        assert ensure_token() == first
        second = regenerate()
        assert second != first
        assert f"DANA_AUTH_TOKEN={second}" in env_file.read_text(encoding="utf-8")
