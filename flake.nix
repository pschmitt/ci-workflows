{
  description = "Shared CI tooling: the release script";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # Repositories run the release tool from here instead of keeping a copy:
      #   nix run github:pschmitt/ci-workflows#release -- prepare X.Y.Z
      #   nix run github:pschmitt/ci-workflows#release -- tag
      # The caller's own git, gh and gpg come first on PATH (signing keys,
      # agents, gh auth); the packaged ones are only a fallback.
      packages = forAllSystems (pkgs: {
        release = pkgs.writeShellScriptBin "release" ''
          export PATH="$PATH:${
            pkgs.lib.makeBinPath [
              pkgs.coreutils
              pkgs.gnugrep
              pkgs.gnused
              pkgs.git
              pkgs.gh
              pkgs.gnupg
            ]
          }"
          exec ${pkgs.bash}/bin/bash ${./scripts/release.sh} "$@"
        '';
      });

      apps = forAllSystems (pkgs: {
        release = {
          type = "app";
          program = "${self.packages.${pkgs.stdenv.hostPlatform.system}.release}/bin/release";
        };
      });
    };
}
