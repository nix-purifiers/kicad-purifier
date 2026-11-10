{
  description = "KiCad with locked, Nix-resolved add-ons";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        kicad-purifier = import ./nix/scope.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (
        system:
        let
          p = (pkgsFor system).kicad-purifier;
        in
        {
          default = p.cli;
          kicad = p.original;
          native-helper = p.helper;
          gui-test-cli = p.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
            commands = (pkgsFor system).callPackage ./tests/commands.nix {
              inherit (p) commands;
              native = ./native;
            };
          };
          xvfb = (pkgsFor system).xvfb-run;
          gui-test-env =
            let
              pkgs = pkgsFor system;
            in
            pkgs.runCommand "purifier-gui-test-environment" { } ''
              mkdir -p "$out/bin"
              ln -s ${pkgs.lib.getBin pkgs.dbus}/bin/dbus-run-session "$out/bin/dbus-run-session"
              ln -s ${pkgs.lib.getBin pkgs.dbus}/bin/dbus-daemon "$out/bin/dbus-daemon"
              ln -s ${
                pkgs.makeFontsConf {
                  fontDirectories = [
                    pkgs.dejavu_fonts
                    pkgs.noto-fonts
                  ];
                }
              } "$out/fonts.conf"
            '';
        }
      );
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/kicad-purifier";
        };
      });
      lib.kicad-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          p = (pkgsFor system).kicad-purifier;
          build = p.buildKicadProject { src = ./examples/minimal; };
        in
        {
          resource-projections = import ./tests/resource-projections.nix {
            pkgs = pkgsFor system;
            build = p.buildKicadProject;
          };
          cli = p.cli;
          inherit (build.packages) environment project;
          release = build.release;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
