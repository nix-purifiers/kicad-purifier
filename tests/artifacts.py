"""Check the self-contained native BOM payload, external locks and exact release assets."""

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin/kicad-purifier"
source = Path(__file__).resolve().parents[1]


def call(arguments, *, env, cwd):
    result = subprocess.run(
        arguments, check=True, env=env, cwd=cwd, text=True, capture_output=True
    )
    return result.stdout.strip()


with tempfile.TemporaryDirectory(prefix="kicad-artifacts-") as temporary:
    root = Path(temporary)
    project = root / "project"
    shutil.copytree(
        source / "examples/minimal",
        project,
        ignore=shutil.ignore_patterns(".kicad-purifier"),
    )
    env = os.environ.copy() | {
        "HOME": str(root / "home"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "QT_QPA_PLATFORM": "offscreen",
    }
    for name in ["home", "data", "config", "cache"]:
        (root / name).mkdir()
    args = [str(cli), "--project", str(project)]
    build = Path(call([*args, "build"], env=env, cwd=root))
    html = (build / "bom.html").read_text()
    data = json.loads(re.search(r"var pcbdata = (\{[^\n]*\})", html).group(1))
    assert data["bom"]["fields"]["0"] == ["42k", "Resistor"]
    assert data["bom"]["both"] == [[["R1", 0]]]
    assert data["metadata"]["title"] == "Purifier PCB"
    assert data["footprints"] and data["edges"]
    release = Path(call([*args, "bundle"], env=env, cwd=root))
    archive = release / "kicad-project.tar.gz"
    with tarfile.open(archive) as tar:
        assert tar.extractfile("./bom.html").read() == (build / "bom.html").read_bytes()
    external = root / "external-lock.json"
    shutil.copyfile(project / "kicad-purifier.lock.json", external)
    replay = Path(call([*args, "--lock", str(external), "bundle"], env=env, cwd=root))
    assert (replay / archive.name).read_bytes() == archive.read_bytes()
    fake = root / "gh"
    fake.write_text(
        f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['UPLOAD_RECORD']).write_text(json.dumps(sys.argv[1:]))\n"
        "Path(os.environ['UPLOAD_BYTES']).write_bytes(Path(sys.argv[4]).read_bytes())\n"
    )
    fake.chmod(0o755)
    publish_env = env | {
        "KICAD_PURIFIER_GH": str(fake),
        "UPLOAD_RECORD": str(root / "upload.json"),
        "UPLOAD_BYTES": str(root / "upload.tar.gz"),
    }
    call([*args, "publish", "--tag", "proof"], env=publish_env, cwd=root)
    record = json.loads((root / "upload.json").read_text())
    assert record[:3] == ["release", "upload", "proof"] and record[3] == str(archive)
    assert (root / "upload.tar.gz").read_bytes() == archive.read_bytes()
print("KiCad BOM payload, external lock and exact release checks passed")
