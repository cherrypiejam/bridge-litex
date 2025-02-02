pkgMeta:
{ mkSbtDerivation, python3, litex-unchecked, migen }:
let
  # python environment with the litex used to generate the default CPU variants
  pythonEnv = python3.withPackages (_: [ litex-unchecked migen ]);
  localVersion = "0.1";
in
mkSbtDerivation rec {
  pname = "pythondata-cpu-vexriscv_bridge-generated";
  version = pkgMeta.version;

  src = pkgMeta.src;

  # sbt needs to compile at least one file in order to download all the
  # dependencies, but we don't want it to compile all of the project in order
  # to save time and resource hassles. so delete the source and compile a fake
  # file to get sbt to do its job properly.
  depsWarmupCommand = ''
    # find directories which contain source code and replace them with
    # one empty file (except for the idslplugin which needs to still exist
    # so the fake compilation will work)
    find . -wholename "*/src/main" -print0 | grep -z -v idslplugin | \
      xargs -0 -I{} bash -c 'rm -rf {}/../../src && mkdir -p {}/scala && touch {}/scala/dummy.scala'

    # ask sbt to compile the main project
    pushd pythondata_cpu_vexriscv_bridge/verilog/ext/VexRiscv
    sbt compile
    popd
  '';

  # if any sbt files or dependencies change, change this hash to cause nix to
  # regenerate them, then replace this with the hash it gives you and rebuild.
  # not doing this will break reproducibility and may cause sbt to report
  # errors that it can't download stuff during the build.
  depsSha256 = pkgMeta.depsSha256;
  depsArchivalStrategy = "copy";

  buildPhase = ''
    runHook preBuild

    # delete old CPU variant sources
    rm -f pythondata_cpu_vexriscv_bridge/verilog/VexRiscv*.v

    # rebuild all CPU variants
    ${pythonEnv}/bin/python generate.py

    runHook postBuild
  '';

  # default RAM allocation is not enough and causes compliation to take several
  # minutes longer than necessary due to GC thrashing
  SBT_OPTS = ''-Xmx2G'';

  installPhase = ''
    runHook preInstall

    # remove build artifacts
    find . -wholename "*/src/main" -print0 | \
      xargs -0 -I{} bash -c 'rm -rf {}/../../{target,project/project,project/target}'
    rm -rf pythondata_cpu_vexriscv_bridge/verilog/ext/SpinalHDL/project/{project,target}

    # VexRiscv writes the current timestamp into the generated
    # output, which breaks reproducibility. Remove it.
    find . -iname '*.v' -execdir sed '/^\/\/ Date      :/d' -i {} \;

    # the build product is the python package with the updated verilog
    # modules. copy the updated python package as our output so we can then
    # install it as a normal python package.
    mkdir -p $out
    cp -r * $out

    runHook postInstall
  '';
}
