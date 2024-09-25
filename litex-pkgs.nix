{ pkgs ? (import <nixpkgs> {})
, # Given we inject a custom nix-litex pkgMetas TOML file, we'll want
  # to -- by default -- make sure the result is properly tested
  skipLitexPkgChecks ? false
, ... }:

let
  # Use builtins.fromTOML if available, otherwise use remarshal to
  # generate JSON which can be read. Code taken from
  # nixpkgs/pkgs/development/tools/poetry2nix/poetry2nix/lib.nix.
  fromTOML = pkgs: builtins.fromTOML or (
    toml: builtins.fromJSON (
      builtins.readFile (
        pkgs.runCommand "from-toml"
          {
            inherit toml;
            allowSubstitutes = false;
            preferLocalBuild = true;
          }
          ''
            ${pkgs.remarshal}/bin/remarshal \
              -if toml \
              -i <(echo "$toml") \
              -of json \
              -o $out
          ''
      )
    )
  );

  # Alternative URLs (mirrors) for the nix-litex repository are
  #
  # - https://github.com/lschuermann/nix-litex.git
  # - https://git.currently.online/leons/nix-litex.git
  #
  # nixLitexSrc = builtins.fetchGit {
  #   # Temporary downtime of git.sr.ht, see
  #   # https://status.sr.ht/issues/2023-01-10-network-outage/
  #   #url = "https://git.sr.ht/~lschuermann/nix-litex";
  #   url = "https://git.currently.online/leons/nix-litex.git";
  #   ref = "main";
  #   rev = "75fb0a2b9be43f43b8b14a2f0fd437ebdd8ba76f";
  # };
  nixLitexSrc = ../../litex/nix-litex;

  litexPackages = import "${nixLitexSrc}/pkgs" {
    inherit pkgs;
    skipChecks = skipLitexPkgChecks;
  };

  lschuermannNurPkgs = import (builtins.fetchGit {
    url = "https://github.com/lschuermann/nur-packages.git";
    ref = "master";
    rev = "dfc0d0e5f22f6dcc5bfc843193f6390c5e8d079b";
  }) { inherit pkgs; };

  vivado = lschuermannNurPkgs.vivado-2022_2;

  # There are some packages which need to be customized here. However
  # we still want to benefit from all the testing infrastructure of
  # the nix-litex repository. Thus we override the pythonOverlay and
  # inject our own package definitions.
  customizedPythonOverlay = self: super:
    let
      # First, call the original overlay
      upstream = litexPackages.pythonOverlay self super;
    in
      # Now, inject our custom packages in the resulting attribute set
      upstream // {
        # # Override the CPU to add the TockSecureIMC variant patch:
        pythondata-cpu-vexriscv = (upstream.pythondata-cpu-vexriscv.override ({
          generated = upstream.pythondata-cpu-vexriscv.generated.overrideAttrs (prev: {
            # This patched revision is based on the upstream pythondata-cpu-vexriscv
            # revision `3b8d17ee104b07113ff0889e72d5a6d5a5610c2d`, which is targete
            # by the referenced nix-litex upstream. Thus the scala packages should
            # be compatible, and we can simply override the source attribute.
            src = builtins.fetchGit {
              url = "https://github.com/lschuermann/litex-vexriscv-custom";
              ref = "refs/heads/cibranch0";
              rev = "38883a2be5587bf8556d71503386d8afe970a54b";
              submodules = true;
            };
          });
        }));

        # Override the VexRiscv SMP CPU
        pythondata-cpu-vexriscv_smp = (upstream.pythondata-cpu-vexriscv_smp.override (_: {
          generated = upstream.pythondata-cpu-vexriscv_smp.generated.overrideAttrs (prev: {

            src = ./../pythondata-cpu-vexriscv_smp;

            # buildInputs = [ pkgs.scala_2_12 ];

            # src = builtins.fetchGit {
            #   url = "https://github.com/cherrypiejam/pythondata-cpu-vexriscv_smp";
            #   ref = "refs/heads/master";
            #   rev = "9da054f1d3aa73e20dfa570619e84e858fcb8687";
            #   submodules = true;
            # };

            # prePatch = ''
            #   pushd pythondata_cpu_vexriscv_smp/verilog/ext/VexRiscv/
            #   patch -p1 --merge < ${pkgs.writeText "vexriscv-DBusCachedPlugin-formal.patch" (
            #     builtins.readFile ./patches/vexriscv-DBusCachedPlugin-0001-Add-formal-support.patch
            #   )}
            #   patch -p1 --merge < ${pkgs.writeText "vexriscv-VexRiscvSmpLitexCluster-formal.patch" (
            #     builtins.readFile ./patches/vexriscv-VexRiscvSmpLitexCluster-0002-Add-formal-support-in-SMP-cluster.patch
            #   )}
            #   patch -p1 --merge < ${pkgs.writeText "vexriscv-VexRiscvSmpLitexCluster-RVFI.patch" (
            #     builtins.readFile ./patches/vexriscv-VexRiscvSmpLitexCluster-0003-Aggregate-RVFI-signals-across-cores-in-SMP.patch
            #   )}
            #   patch -p1 --merge < ${pkgs.writeText "vexriscv-VexRiscvSmpLitexCluster-PMP.patch" (
            #     builtins.readFile ./patches/vexriscv-VexRiscvSmpLitexCluster-0004-Add-PMP-support-in-Vexriscv-SMP-cluster-generator.patch
            #   )}
            #   popd
            # '';
          });
        }));

        # Override LiteX to include support for the TockSecureIMC
        # CPU variant:
        litex-unchecked = upstream.litex-unchecked.overrideAttrs (prev: {
          src = ../../litex/litex;
          # patches = (prev.patches or [ ]) ++ [
          #   ./litex_add_TockSecureIMC_CPU.patch
          #   ./litex_disable_TFTP_block_size_negotiation.patch
          #   ./patches/litex-0001-Add-formal-support-in-vexriscv-smp.patch
          #   ./patches/litex-0002-Add-default-build-with-formal-enabled-and-wishbone-memory.patch
          #   ./patches/litex-0004-Add-default-build-with-pmp-support.patch
          #   ./patches/litex-0005-Build-with-rvc-by-default.patch
          # ];
        });

        pythondata-cpu-ibex = super.buildPythonPackage rec {
          pname = "pythondata-cpu-ibex";
          version = "2bccf45b93770cd9e839c65276d1117123c77a34";

          src = builtins.fetchGit {
            url = "https://github.com/litex-hub/pythondata-cpu-ibex";
            rev = version;
            submodules = true;
          };

          patch = [
            # Patch the ibex_tracer.sv module to statically enable trace logging:
            ./patches/pythondata-cpu-ibex-0001-rtl-ibex_tracer.sv-statically-enable-trace-logging.patch
          ];

          # Tests are broken currently.
          doCheck = false;
        };

        # litex-boards-unchecked = upstream.litex-boards-unchecked.overrideAttrs (prev: {
        #   # Unfortunately, the upstream nix-litex overrides the
        #   # patchPhase for litex-boards, which prevents us from
        #   # specifying patches here. In the meantime, apply the patch
        #   # manually:
        #   patchPhase = ''
        #     patch -p1 <${./litex-boards_targets-arty-add-option-to-set-with_buttons.patch}
        #   '' + (prev.patchPhase or "");
        # });
      };

  applyOverlay = python: python.override {
    packageOverrides = customizedPythonOverlay;
  };

  overlay = self: super: {
    mkSbtDerivation = litexPackages.mkSbtDerivation;
  } // (litexPackages.applyPythonOverlays super applyOverlay);

  extended = pkgs.extend overlay;

  pkgSet =
    (builtins.foldl'
      (acc: elem: acc // {
        ${elem} = extended.python3Packages.${elem};
      })
      { }
      ((builtins.attrNames litexPackages.packages) ++ [ "pythondata-cpu-ibex" ])
    ) // {
      # Maintenance scripts for working with the TOML files in this repo
      maintenance = litexPackages.maintenance;

      # Vivado derivation, useful for builting the bitstreams for some
      # of the boards defined in this repo.
      inherit vivado;
    };


in
  pkgSet
