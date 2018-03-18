{ pkgs ? (import <nixpkgs> {} ) }:

with (import ./python-env.nix { inherit pkgs; });

(python.withPackages (ps: [
  #inxs
  dependency_injection
  ps.lxml
  ps.python_mimeparse
  ps.cssutils
  ps.flake8
  ps.pylint
  ps.jedi
  ps.epc
  ps.pip
])).env
