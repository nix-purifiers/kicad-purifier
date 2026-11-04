"""Load the SDK's original bindings and restrict only its dependency plugin loader."""

import os
import traceback
from pathlib import Path as _purifier_Path

_purifier_original = _purifier_Path(os.environ["KICAD_PURIFIER_ORIGINAL_PCBNEW"])
_purifier_source = _purifier_original.read_text()
if os.environ.get("KICAD_PURIFIER_ENVIRONMENT"):
    # The native loader otherwise adds mutable configuration scripting paths even
    # when its userpath argument is absent. Keep other native settings APIs intact.
    _purifier_statement = "config_path = pcbnew.SETTINGS_MANAGER.GetUserSettingsPath()"
    if _purifier_source.count(_purifier_statement) != 1:
        raise RuntimeError("KiCad plugin loader changed; update the purifier provider")
    _purifier_source = _purifier_source.replace(_purifier_statement, 'config_path = ""')
__file__ = str(_purifier_original)
exec(compile(_purifier_source, __file__, "exec"), globals())

if os.environ.get("KICAD_PURIFIER_ENVIRONMENT"):
    _purifier_load = globals()["LoadPlugins"]

    def LoadPlugins(bundlepath=None, userpath=None, thirdpartypath=None):
        try:
            environment = _purifier_Path(os.environ["KICAD_PURIFIER_ENVIRONMENT"])
            _purifier_load(
                os.environ["KICAD_PURIFIER_BUILTIN_SCRIPTS"],
                None,
                str(environment / "plugins"),
            )
        except BaseException:
            os.write(2, traceback.format_exc().encode())
            os._exit(1)
