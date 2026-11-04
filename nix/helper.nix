{
  lib,
  runCommand,
  stdenv,
  python3,
  wxwidgets_3_3,
  boost,
  glm,
  original,
}:
let
  base = original.base;
  headers = lib.fileset.toSource {
    root = ../native;
    fileset = ../native/headless.hpp;
  };
in
runCommand "kicad-native-pcm"
  {
    nativeBuildInputs = [
      stdenv.cc
      python3
    ];
    buildInputs = [
      wxwidgets_3_3
      boost
      glm
    ];
  }
  ''
    export source=${base.src}
    python ${../native}/kicad_purifier_extract_native.py "$source/kicad/pcm/pcm.cpp" "$source/kicad/pcm/pcm_task_manager.cpp" > prepare.cpp
    c++ -std=c++17 -DJSON_HAS_FILESYSTEM=0 -ffile-prefix-map=${base.src}=/kicad-src \
      ${
        lib.concatMapStringsSep " " (name: "-I${base.src}/libs/${name}/include") [
          "core"
          "kimath"
          "kinng"
          "kiplatform"
          "sexpr"
        ]
      } \
      -I"$source/include" -I"$source/libs/core/include" \
      -I${headers} -I"$source/kicad/pcm" -I"$source/thirdparty/nlohmann_json" \
      -I"$source/thirdparty/json_schema_validator" \
      $(wx-config --cxxflags) ${../native}/helper.cpp prepare.cpp \
      "$source/kicad/pcm/pcm_data.cpp" \
      "$source/thirdparty/json_schema_validator/"*.cpp \
      -L${base}/lib -Wl,-rpath,${base}/lib -lkicommon \
      $(wx-config --libs) -o helper
    mkdir -p "$out/bin" "$out/share"
    cp "$source/kicad/pcm/schemas/pcm.v2.schema.json" "$out/share/pcm.v2.schema.json"
    cp helper "$out/bin/kicad-native-pcm"
  ''
