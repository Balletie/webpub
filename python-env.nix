{ pkgs ? (import <nixpkgs> {} ) }:

with pkgs;
rec {
  python = python36.override {
    packageOverrides = self: super: {
      lxml = super.lxml.overridePythonAttrs (oldAttrs: rec {
        src = pkgs.fetchurl {
          name = "${oldAttrs.name}.tar.gz";
          url = "https://github.com/funkyfuture/lxml/tarball/smart_xpath#egg=lxml";
          sha256 = "1z3wmci4m28fb6zq1s8qcn2z4ia6ddbi4rp6wlf40p6xz7mhw8l7";
        };

	buildInputs = oldAttrs.buildInputs ++ [ super.cython ];
      });
    };
  };

  dependency_injection = with python.pkgs; buildPythonPackage rec {
    name = "dependency-injection-${version}";
    version = "1.1.0";

    doCheck = false;

    src = pkgs.fetchurl {
      url = "mirror://pypi/d/dependency-injection/dependency_injection-1.1.0.tar.gz";
      sha256 = "00m2f0rfh65sq2dy2bcy70wliw5bmpxbpknlcncrncrp3rfhsk2w";
    };
  };

  inxs = with python.pkgs; buildPythonPackage rec {
    name = "inxs-${version}";
    version = "0.1b1";

    doCheck = false;

    src = pkgs.fetchurl {
      url = "mirror://pypi/i/inxs/${name}.tar.gz";
      sha256 = "1fmvslf9s2qh1ji5qkrbpw3crh5raw4gzcmnhns3hnqxwsnhyl90";
    };

    patches = [ ./patches/0001-Specify-encoding-when-reading-README-and-HISTORY-fil.patch ];

    propagatedBuildInputs = [ lxml cssselect dependency_injection cython ];
  };
}
