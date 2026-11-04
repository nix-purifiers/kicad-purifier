import os
import subprocess
from pathlib import Path

from kicad_purifier_prepare import prepare

state = Path(os.environ["TMPDIR"]) / "kicad-state"
env = os.environ.copy()
env.update(
    prepare(
        state,
        os.environ["KICAD_PURIFIER_ENVIRONMENT"],
        os.environ["KICAD_PURIFIER_VERSION"],
    )
)
env["HOME"] = str(state / "home")
subprocess.run(
    [os.environ["KICAD_PURIFIER_COMMAND_BINARY"], os.environ["KICAD_PURIFIER_SCRIPT"]],
    env=env,
    check=True,
)
