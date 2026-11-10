{
  lib,
  purifier,
  runCommand,
  python3,
  original,
  commands,
  environment,
  readLock,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/kicad-purifier.lock.json",
  script ? "build.py",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
  resourceRoots ? { },
  resourceDependencies ? [ ],
}:
let
  lock = readLock { inherit src lockFile; };
  profile = environment { inherit lock fetchers; };
  projectSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".kicad-purifier"
        "__pycache__"
        "result"
      ]);
  };
  builtProject = runCommand "kicad-project" { } ''
    export KICAD_PURIFIER_ENVIRONMENT=${profile} KICAD_PURIFIER_COMMAND_BINARY=${commands}/bin/kicad-python
    export KICAD_PURIFIER_ORIGINAL_PCBNEW=${original.base}/${python3.sitePackages}/pcbnew.py
    export KICAD_PURIFIER_BUILTIN_SCRIPTS=${original.base}/share/kicad/scripting
    export KICAD_PURIFIER_VERSION=${lib.versions.majorMinor original.version}
    export KICAD_PURIFIER_OUTPUT="$out"
    mkdir -p "$out"
    cp -r ${projectSource} project
    chmod -R u+w project
    cd project
    export KICAD_PURIFIER_SCRIPT="$PWD/"${lib.escapeShellArg script}
    ${python3}/bin/python ${../native}/kicad_purifier_run_build.py
    ${lib.optionalString doCheck checkCommand}
  '';
  projections = lib.optionalAttrs (resourceRoots != { }) (
    purifier.resourceProjections {
      producer = builtProject;
      roots = resourceRoots;
      dependencies = resourceDependencies;
      inherit runCommand python3;
    }
  );
  project = builtProject // {
    inherit projections;
  };
  release =
    runCommand "kicad-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - -C ${project} . | gzip -n > "$out/kicad-project.tar.gz"
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = profile;
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
