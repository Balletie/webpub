{ pkgs ? (import <nixpkgs> {} ) }:

with (import ./python-env.nix { inherit pkgs; });

(python.withPackages (ps: [
  inxs
  ps.python_mimeparse
  ps.cssutils
])).env
