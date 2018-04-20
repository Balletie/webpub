{ pkgs ? (import <nixpkgs> {}) }:

with (import ./python-env.nix { inherit pkgs; });

with python.pkgs; buildPythonPackage rec {
  name = "webpub-${version}";
  version = "1.0";

  src = ./.;

  propagatedBuildInputs = [ inxs dependency_injection requests html5-parser lxml jinja2 click python_mimeparse cssutils ];

  passthru = {
    inherit python;
  };
}
