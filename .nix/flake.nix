{
  description = "AST Merging Evaluation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
    nixpkgs-darwin.url = "github:NixOS/nixpkgs/nixpkgs-24.05-darwin";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    nixpkgs-darwin,
    flake-utils,
  }:
    flake-utils.lib.eachDefaultSystem (
      system: let
        pkgs =
          if builtins.match ".*-darwin" system != null
          then import nixpkgs-darwin {inherit system;}
          else import nixpkgs {inherit system;};
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Nix.
            alejandra
            deadnix
            statix
            nixd

            # Python.
            micromamba

            # macOS dependencies.
            jq
            gh
          ];

          # shellHook = ''
          #  micromamba --version
          #  eval "$(micromamba shell hook --shell zsh)"
          # '';
        };
      }
    );
}
