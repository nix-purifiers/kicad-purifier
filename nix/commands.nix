{
  lib,
  runCommand,
  makeWrapper,
  python3,
  python,
  original,
}:
let
  overlay = ../native;
in
runCommand "kicad-purifier-native-commands" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in kicad pcbnew kicad-cli; do
    cp ${original}/bin/$name "$out/bin/$name"
    chmod u+w "$out/bin/$name"
    substituteInPlace "$out/bin/$name" \
      --replace-fail "export PYTHONPATH='" "export PYTHONPATH='${overlay}:"
  done
  makeWrapper ${python}/bin/python "$out/bin/kicad-python" \
    --set PYTHONPATH ${overlay}:${original.base}/${python3.sitePackages} \
    --run 'if [ -n "''${KICAD_PURIFIER_ENVIRONMENT:-}" ]; then export PYTHONPATH="$PYTHONPATH:$KICAD_PURIFIER_ENVIRONMENT/plugins"; fi'
''
