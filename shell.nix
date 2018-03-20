{ pkgs ? (import <nixpkgs> {} ) }:

let pkg = import ./default.nix { inherit pkgs; };
    # pythonEnvPackages is defined in my nixpkgs config
    envPkgs = pkgs.pythonEnvPackages or (ps: []);
in

pkg.overrideAttrs(oldAttrs: {
  propagatedBuildInputs = oldAttrs.propagatedBuildInputs ++ (envPkgs pkg.python.pkgs);
})
