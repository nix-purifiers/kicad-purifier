"""Test the actual working-tree plugin workflow, native preferences and fallback."""

import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin"
original = Path(sys.argv[2]).resolve() / "bin/kicad-cli"
source = Path(__file__).resolve().parents[1]


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"project networking works")

    def log_message(self, *args):
        pass


with tempfile.TemporaryDirectory(prefix="kicad-native-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".kicad-purifier", "output"),
    )
    for name in ["home", "config", "data", "cache"]:
        (root / name).mkdir()
    env = os.environ.copy() | {
        "KICAD_PURIFIER_PROJECT": str(project),
        "KICAD_PURIFIER_OUTPUT": str(project / "output"),
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CACHE_HOME": str(root / "cache"),
    }
    for name in [
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "WAYLAND_SOCKET",
        "DBUS_SESSION_BUS_ADDRESS",
    ]:
        env.pop(name, None)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env["KICAD_TEST_URL"] = f"http://127.0.0.1:{server.server_port}/"
    script = project / "build.py"
    script.write_text(
        script.read_text()
        + """
import json, stat, urllib.request, wx, pcbnew
import org_openscopeproject_InteractiveHtmlBom as plugin
assert Path(plugin.__file__).resolve().is_relative_to("/nix/store")
assert not (Path(plugin.__file__).stat().st_mode & stat.S_IWUSR)
app = wx.AppConsole()
settings = wx.FileConfig(localFilename=str(Path(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath()) / "purifier.ini"))
counter = settings.ReadInt("counter",0) + 1
settings.WriteInt("counter",counter)
settings.Flush()
with urllib.request.urlopen(os.environ["KICAD_TEST_URL"]) as response:
    assert response.read() == b"project networking works"
(output / "proof.json").write_text(json.dumps({"counter":counter}))
"""
    )
    board = project / "board.kicad_pcb"
    original_board = board.read_text()
    lock = project / "kicad-purifier.lock.json"
    lock_bytes = lock.read_bytes()
    hashes = []
    try:
        for counter, value in enumerate(["42k", "43k", "42k"], 1):
            board.write_text(
                original_board.replace(
                    '(property "Value" "42k"', f'(property "Value" "{value}"'
                )
            )
            result = subprocess.run(
                [cli / "kicad-python", script],
                env=env,
                cwd=project,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            html = project / "output/bom.html"
            assert value in html.read_text()
            hashes.append(hashlib.sha256(html.read_bytes()).hexdigest())
            assert (
                json.loads((project / "output/proof.json").read_text())["counter"]
                == counter
            )
            assert lock.read_bytes() == lock_bytes
    finally:
        server.shutdown()
        server.server_close()
    assert hashes[0] != hashes[1] and hashes[0] == hashes[2]
    state = project / ".kicad-purifier"
    assert (state / "environment").resolve().is_relative_to("/nix/store")
    registration = state / "config/kicad/10.0/installed_packages.json"
    assert registration.resolve().is_relative_to("/nix/store")
    assert all(
        item["pinned"] for item in json.loads(registration.read_text())["packages"]
    )
    poison = state / "config/kicad/10.0/scripting/ambient.py"
    poison.parent.mkdir()
    poison.write_text("raise AssertionError('ambient plugin executed')\n")
    rejected = subprocess.run(
        [cli / "kicad-cli", "version"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode and "unlocked KiCad plugin state" in rejected.stderr
    assert poison.exists()
    poison.unlink()
    selection = project / "kicad-purifier.json"
    selection.write_text('{"plugins": []}')
    rejected = subprocess.run(
        [cli / "kicad-cli", "version"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode and "selection changed" in rejected.stderr
    lock.unlink()
    for arguments in [["version"], ["unknown-command"]]:
        expected = subprocess.run(
            [original, *arguments], env=env, capture_output=True, check=False
        )
        actual = subprocess.run(
            [cli / "kicad-cli", *arguments], env=env, capture_output=True, check=False
        )
        assert actual.returncode == expected.returncode
        assert actual.stdout == expected.stdout
        assert (
            actual.stderr
            == b"warning: no KiCad purifier lock; using ordinary, impure plugin resolution\n"
            + expected.stderr
        )
print("KiCad native source/preference/immutable-code/network/fallback checks passed")
