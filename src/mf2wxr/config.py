"""Settings and credentials, kept in ~/.config/mf2wxr (or $XDG_CONFIG_HOME/mf2wxr)."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "mf2wxr"


@dataclass
class Config:
    client_id: str | None = None
    """The id of the service you registered under weightxreps settings → Developer API."""
    exports: Path | None = None
    """Where MacroFactor exports land, used when `push` gets no path."""

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_dir() / "config.toml"
        data = {}
        if path.exists():
            with path.open("rb") as f:
                data = tomllib.load(f)

        exports = data.get("exports")
        return cls(
            client_id=os.environ.get("MF2WXR_CLIENT_ID") or data.get("client_id"),
            exports=Path(exports).expanduser() if exports else None,
        )
