#!/usr/bin/env bash
# Licensed under the Apache License, Version 2.0. See LICENSE for details.
set -euo pipefail

benchmark_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
graalvm_java_home="${GRAALVM_HOME:-${JAVA_HOME:-}}"

if [[ -z "${graalvm_java_home}" ]]; then
  echo "Set GRAALVM_HOME or JAVA_HOME to a GraalVM installation with native-image." >&2
  exit 1
fi
if [[ ! -x "${graalvm_java_home}/bin/native-image" ]]; then
  echo "native-image was not found under ${graalvm_java_home}/bin." >&2
  exit 1
fi

run_maven() {
  env JAVA_HOME="${graalvm_java_home}" PATH="${graalvm_java_home}/bin:${PATH}" mvn "$@"
}

cd "${benchmark_root}"
run_maven clean test
run_maven -pl fory-app -am -Pnative -DskipTests package
run_maven -pl jackson-app -am -Pnative -DskipTests package
run_maven -pl jackson-generated-app -am -Pgenerated-native -DskipTests package

./fory-app/target/fory-json-benchmark --verify
./jackson-app/target/jackson-benchmark --verify
./jackson-generated-app/target/jackson-generated-benchmark-runner --verify
