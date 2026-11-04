{
  lib,
  runCommand,
  writeText,
  makeWrapper,
  python3,
  original,
  commands,
  helper,
  sdk,
  nix,
  gh,
  cacert,
  nixpkgsSrc,
  purifierSrc,
}:
let
  integration = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../kicad_purifier
      ../native
      ./.
    ];
  };
  realize = writeText "kicad-purifier-realize.nix" ''
    { lockPath, projectPath, target ? "environment" }:
    let
      pkgs = import (builtins.storePath "${nixpkgsSrc}") {};
      scope = import ${integration}/nix/scope.nix {
        inherit pkgs;
        nixpkgsSrc = builtins.storePath "${nixpkgsSrc}";
        purifierSrc = builtins.storePath "${purifierSrc}";
      };
      lockFile = builtins.toPath lockPath;
      src = builtins.path {
        path = builtins.toPath projectPath;
        name = "kicad-project";
        filter = path: type: !(builtins.elem (baseNameOf path) [ ".git" ".kicad-purifier" "__pycache__" "result" ]);
      };
      build = scope.buildKicadProject { inherit src lockFile; };
    in if target == "environment" then scope.environment { lock = scope.readLock { inherit src lockFile; }; }
       else if target == "project" then build.packages.project
       else if target == "release" then build.release
       else throw "Unknown KICAD purifier target"
  '';
in
runCommand "kicad-purifier" { nativeBuildInputs = [ makeWrapper ]; } ''
  mkdir -p "$out/bin"
  for name in kicad-purifier kicad pcbnew kicad-cli kicad-python; do
    makeWrapper ${python3}/bin/python "$out/bin/$name" \
      --add-flags '-m kicad_purifier.main' \
      --set PYTHONPATH ${integration} \
      --set KICAD_PURIFIER_COMMAND "$name" \
      --set KICAD_PURIFIER_NATIVE ${integration}/native \
      --set KICAD_PURIFIER_ORIGINAL ${original}/bin \
      --set KICAD_PURIFIER_COMMANDS ${commands}/bin \
      --set KICAD_PURIFIER_HELPER ${helper}/bin/kicad-native-pcm \
      --set KICAD_PURIFIER_SCHEMA ${helper}/share/pcm.v2.schema.json \
      --set KICAD_PURIFIER_VERSION ${lib.versions.majorMinor original.version} \
      --set KICAD_PURIFIER_NATIVE_VERSION ${original.version} \
      --set KICAD_PURIFIER_ORIGINAL_PCBNEW ${original.base}/${python3.sitePackages}/pcbnew.py \
      --set KICAD_PURIFIER_BUILTIN_SCRIPTS ${original.base}/share/kicad/scripting \
      --set KICAD_PURIFIER_SDK ${sdk} \
      --set KICAD_PURIFIER_REALIZE ${realize} \
      --set-default KICAD_PURIFIER_GH ${gh}/bin/gh \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default NIX_SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --prefix PATH : ${
        lib.makeBinPath [
          nix
          gh
        ]
      }
  done
''
