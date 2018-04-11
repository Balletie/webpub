{ pkgs ? (import <nixpkgs> {} ) }:

with pkgs;
rec {
  python = python36;

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
    version = "0.1-rev-c4219d6";

    doCheck = false;

    src = pkgs.fetchgit {
      url = "https://github.com/Balletie/inxs.git";
      rev = "c4219d6a55c90996030b8c77c74639c2030d9cfe";
      sha256 = "0s3m8ilxgimlxqkvx3ly7vkf8y8gjlc2pqp1gh7j2ll5ll1cd4rp";
    };

    patches = [ ./patches/0001-Specify-encoding-when-reading-README-and-HISTORY-fil.patch ];

    propagatedBuildInputs = [ lxml cssselect dependency_injection cython ];
  };

  sphinx_click = with python.pkgs; buildPythonPackage rec {
    name = "sphinx-click-${version}";
    version = "1.1.0";

    doCheck = false;

    src = pkgs.fetchurl {
      url = "mirror://pypi/s/shpinx-click/sphinx-click-1.1.0.tar.gz";
      sha256 = "1py42w94345hmdqpabc5wz95y25mhih2x9caim2bqpjbxrajvvqf";
    };

    propagatedBuildInputs = [ pbr sphinx ];
  };
}
