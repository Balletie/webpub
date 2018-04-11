{ pkgs ? (import <nixpkgs> {} ) }:

let pkg = import ./default.nix { inherit pkgs; };
    localEnv = import ./python-env.nix { inherit pkgs; };
    # pythonEnvPackages is defined in my nixpkgs config
    envPkgs = pkgs.pythonEnvPackages or (ps: []);
in

pkg.overrideAttrs(oldAttrs: {
  propagatedBuildInputs = oldAttrs.propagatedBuildInputs ++ (envPkgs pkg.python.pkgs) ++ [
    pkg.python.pkgs.sphinx
    localEnv.sphinx_click
  ];
})
