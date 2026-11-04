"""Test instrument around the actual production binding/loader, inside native PCB editor."""

import json
import os
import traceback
from pathlib import Path as _test_Path

_test_production = _test_Path(os.environ["KICAD_GUI_PRODUCTION_MODULE"])
exec(compile(_test_production.read_text(), str(_test_production), "exec"), globals())
_test_guarded_load = globals()["LoadPlugins"]


def LoadPlugins(bundlepath=None, userpath=None, thirdpartypath=None):
    try:
        config = _test_Path(globals()["SETTINGS_MANAGER"].GetUserSettingsPath())
        poison = config / "scripting/runtime_ambient_probe.py"
        poison.parent.mkdir(exist_ok=True)
        marker = _test_Path(os.environ["KICAD_GUI_MARKER"])
        poison.write_text(
            "from pathlib import Path\nPath("
            + repr(str(marker.with_suffix(".poison")))
            + ").touch()\n"
        )
        _test_guarded_load(bundlepath, userpath, thirdpartypath)
        assert not marker.with_suffix(".poison").exists()
        name = "org_openscopeproject_InteractiveHtmlBom"
        module = globals()["KICAD_PLUGINS"][name]["ModuleName"]
        assert _test_Path(module.__file__).resolve().is_relative_to("/nix/store")
        assert module.plugin.name == "Generate Interactive HTML BOM"
        registration = json.loads((config / "installed_packages.json").read_text())
        assert registration["packages"][0]["pinned"]
        marker.write_text(module.plugin.GetPluginPath())
        poison.unlink()
        os._exit(0)
    except BaseException:
        os.write(2, traceback.format_exc().encode())
        os._exit(17)
