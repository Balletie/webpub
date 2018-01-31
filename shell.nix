{ pkgs ? (import <nixpkgs> {} ) }:

with (import ./python-env.nix { inherit pkgs; });

(python.withPackages (ps: [
  inxs
  ps.python_mimeparse
  ps.cssutils
  ps.flake8
  ps.pylint
  ps.jedi
  ps.epc
])).env
