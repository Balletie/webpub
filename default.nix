{ pkgs ? (import <nixpkgs> {}) }:

with (import ./python-env.nix { inherit pkgs; });

with python.pkgs; buildPythonPackage rec {
  name = "webpub-${version}";
  version = "0.1";

  src = ./.;

  propagatedBuildInputs = [ inxs dependency_injection lxml python_mimeparse cssutils ];

  passthru = {
    inherit python;
  };
}
