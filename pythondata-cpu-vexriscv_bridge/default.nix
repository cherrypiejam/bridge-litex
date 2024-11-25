pkgMeta:
{ callPackage
, buildPythonPackage
, generated ? callPackage (import ./generated.nix pkgMeta) { }
}:
buildPythonPackage rec {
  pname = "pythondata-cpu-vexriscv_bridge";
  version = pkgMeta.version;

  src = generated;

  doCheck = false;

  passthru = { inherit generated; };
}
