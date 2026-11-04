"""Reject unsupported IPC descriptors before any native package extraction."""

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

helper = Path(sys.argv[1]).resolve()
source = Path(__file__).resolve().parents[1]
lock = json.loads((source / "examples/minimal/kicad-purifier.lock.json").read_text())
name = lock["entries"][0]["path"]
version = lock["entries"][0]["kicad"]["version"]
with tempfile.TemporaryDirectory(prefix="kicad-provider-") as temporary:
    root = Path(temporary)
    archive = root / "unsupported.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("metadata.json", json.dumps(lock["native"]["catalog"][name]))
        zipped.writestr("plugins/plugin.json", "{}")
    result = subprocess.run(
        [
            helper / "bin/kicad-native-pcm",
            "install",
            archive,
            root / "output",
            name,
            version,
            helper / "share/pcm.v2.schema.json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode and "IPC plugin descriptors" in result.stderr
    assert not (root / "output").exists()
print("KiCad unsupported managed-environment provider fails before extraction")
