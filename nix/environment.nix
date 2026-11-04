{
  lib,
  runCommand,
  writeText,
  fetchurl,
  fetchgit,
  python3,
  original,
  helper,
  purifier,
  sdk,
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  tree = purifier.tree (
    {
      name = "kicad-plugin-archives";
      entries = checked.entries;
      inherit
        runCommand
        writeText
        fetchurl
        fetchgit
        python3
        ;
    }
    // fetchers
  );
  context = writeText "kicad-lock.json" (builtins.toJSON checked.data);
in
assert lib.assertMsg (checked.data.sdk == sdk) "KiCad SDK changed; update the purifier lock";
runCommand "kicad-locked-environment" { passthru = { inherit tree; }; } ''
  export HOME="$TMPDIR/home" XDG_CONFIG_HOME="$TMPDIR/config" XDG_CACHE_HOME="$TMPDIR/cache" XDG_DATA_HOME="$TMPDIR/data"
  mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$out/plugins"
  ${lib.concatMapStringsSep "\n" (entry: ''
    ${helper}/bin/kicad-native-pcm install ${tree}/${entry.path} "$out" \
      ${lib.escapeShellArg entry.path} ${lib.escapeShellArg entry.kicad.version} \
      ${helper}/share/pcm.v2.schema.json
  '') checked.entries}
  ${helper}/bin/kicad-native-pcm register ${context} > "$out/installed_packages.json"
  ln -s ${context} "$out/lock.json"
''
