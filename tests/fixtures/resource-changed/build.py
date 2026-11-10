"""Use the locked plugin's native board parser and HTML generator."""

import os
import sys
from pathlib import Path

os.environ["INTERACTIVE_HTML_BOM_CLI_MODE"] = "1"
os.environ["INTERACTIVE_HTML_BOM_NO_DISPLAY"] = "1"

from org_openscopeproject_InteractiveHtmlBom import generate_interactive_bom

output = Path(os.environ.get("KICAD_PURIFIER_OUTPUT", "output")).resolve()
sys.argv = [
    "generate_interactive_bom",
    str(Path(__file__).with_name("board.kicad_pcb")),
    "--no-browser",
    "--no-compression",
    "--dest-dir",
    str(output),
    "--name-format",
    "bom",
]
generate_interactive_bom.main()
