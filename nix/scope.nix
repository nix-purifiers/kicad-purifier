{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.kicad.override { with3d = false; };
  python = pkgs.python3.withPackages (ps: [
    ps.wxpython_4_3
    ps.six
    ps.requests
  ]);
  helper = scope.callPackage ./helper.nix { };
  commands = scope.callPackage ./commands.nix { };
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  readLock = import ./read-lock.nix { inherit (pkgs) lib; };
  environment = scope.callPackage ./environment.nix { };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildKicadProject = scope.callPackage ./build-project.nix { };
  sdk = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      native = builtins.mapAttrs (name: _: builtins.hashFile "sha256" (../native + ("/" + name))) (
        pkgs.lib.filterAttrs (_: type: type == "regular") (builtins.readDir ../native)
      );
      providers = pkgs.lib.genAttrs [ "scope.nix" "helper.nix" "commands.nix" "environment.nix" ] (
        name: builtins.hashFile "sha256" (./. + ("/" + name))
      );
    }
  );
})
