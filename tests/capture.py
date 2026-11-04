"""Fresh native capture, cold replay and atomic failure against the public catalog."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

cli = Path(sys.argv[1]).resolve() / "bin/kicad-purifier"
source = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="kicad-capture-") as temporary:
    project = Path(temporary)
    shutil.copyfile(
        source / "examples/minimal/kicad-purifier.json",
        project / "kicad-purifier.json",
    )
    env = os.environ.copy() | {"KICAD_PURIFIER_PROJECT": str(project)}
    subprocess.run([str(cli), "lock", "--update"], check=True, env=env, cwd=project)
    lock = project / "kicad-purifier.lock.json"
    before = lock.read_bytes()
    subprocess.run([str(cli), "lock"], check=True, env=env, cwd=project)
    subprocess.run([str(cli), "prefetch"], check=True, env=env, cwd=project)
    assert lock.read_bytes() == before
    mismatched = json.loads(before)
    mismatched["entries"][0]["kicad"]["version"] = "99.0.0"
    external = project / "mismatched-lock.json"
    external.write_text(json.dumps(mismatched))
    failed = subprocess.run(
        [str(cli), "--lock", str(external), "prefetch"],
        check=False,
        env=env,
        cwd=project,
    )
    assert failed.returncode != 0 and lock.read_bytes() == before
    selection_file = project / "kicad-purifier.json"
    selection = json.loads(selection_file.read_text())
    selection["plugins"].append("purifier_missing_plugin_probe")
    selection_file.write_text(json.dumps(selection))
    failed = subprocess.run(
        [str(cli), "lock", "--update"], check=False, env=env, cwd=project
    )
    assert failed.returncode != 0 and lock.read_bytes() == before
    empty = project / "empty"
    empty.mkdir()
    (empty / "kicad-purifier.json").write_text('{"plugins": []}\n')
    empty_env = env | {"KICAD_PURIFIER_PROJECT": str(empty)}
    subprocess.run([str(cli), "lock", "--update"], check=True, env=empty_env, cwd=empty)
    subprocess.run(
        [
            str(cli),
            "exec",
            "--",
            "-c",
            "import pcbnew; print(pcbnew.GetBuildVersion())",
        ],
        check=True,
        env=empty_env,
        cwd=empty,
    )

print("native KICAD capture and atomic failure passed")
