{
  runCommand,
  commands,
  native,
}:
let
  probe = runCommand "kicad-gui-probe-module" { } ''
    mkdir -p "$out"
    cp ${./gui-probe.py} "$out/pcbnew.py"
  '';
in
runCommand "kicad-gui-test-commands" { } ''
    mkdir -p "$out/bin"
    cp -r ${commands}/bin/. "$out/bin/"
    chmod -R u+w "$out/bin"
    substituteInPlace "$out/bin/pcbnew" \
      --replace-fail "export PYTHONPATH='" "export KICAD_GUI_PRODUCTION_MODULE=${native}/pcbnew.py
  export PYTHONPATH='${probe}:"
''
