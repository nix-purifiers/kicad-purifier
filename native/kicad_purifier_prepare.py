"""Bind native mutable preferences to immutable package code and registration."""

import json
import os
import sys
from pathlib import Path


def prepare(state, environment, version):
    state = Path(state).resolve()
    environment = Path(environment).resolve()
    config = state / "config/kicad" / version
    config.mkdir(parents=True, exist_ok=True)
    for name in ["home", "data", "cache"]:
        (state / name).mkdir(exist_ok=True)
    for path in [
        config / "scripting",
        state / "data/kicad" / version / "scripting",
        state / "data/kicad" / version / "plugins",
    ]:
        if path.exists() and any(path.iterdir()):
            raise ValueError(f"unlocked KiCad plugin state: {path}")
    alias = config / "installed_packages.json"
    target = str(environment / "installed_packages.json")
    record = state / "registration.json"
    previous = json.loads(record.read_text()) if record.exists() else None
    if alias.is_symlink():
        if os.readlink(alias) not in {target, previous}:
            raise ValueError("KiCad package registration alias changed")
        if os.readlink(alias) != target:
            alias.unlink()
    elif alias.exists():
        raise ValueError("unlocked KiCad package registration")
    if not alias.is_symlink():
        alias.symlink_to(target)
    record.write_text(json.dumps(target) + "\n")
    return {
        "XDG_CONFIG_HOME": str(state / "config"),
        "XDG_DATA_HOME": str(state / "data"),
        "XDG_CACHE_HOME": str(state / "cache"),
        "KICAD_CONFIG_HOME": str(state / "config/kicad"),
        "KICAD_DOCUMENTS_HOME": str(state / "data/kicad"),
        "KICAD" + version.split(".")[0] + "_3RD_PARTY": str(environment),
        "KICAD_PURIFIER_ENVIRONMENT": str(environment),
    }


if __name__ == "__main__":
    print(json.dumps(prepare(*sys.argv[1:])))
