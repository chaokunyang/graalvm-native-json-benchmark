# GraalVM Native Image JSON benchmark

This repository compares [Apache Fory JSON](https://fory.apache.org/docs/json/)
and [Jackson Databind](https://github.com/FasterXML/jackson-databind) in separate
GraalVM Native Image executables. It measures String and UTF-8 serialization and
deserialization on the same Java object graph.

The model is based on the `Customer` payload in the
[Quarkus metaprogramming article](https://quarkus.io/blog/quarkus-metaprogramming/).
That article generates reflection-free Jackson serializers inside Quarkus. This
repository instead compares the JSON codec layer directly: Fory uses its
build-time Native Image codec generation, while Jackson uses conventional
Databind with explicit reflection metadata. It does not claim to reproduce the
article's HTTP benchmark or its experimental Jackson generator.

The benchmark is single-threaded. Fory uses field mode, a concurrency level of
one, asynchronous compilation disabled, four mix-ins, and a reachable
`@ForyJsonProvider`. Jackson uses a field-only `ObjectMapper`, alphabetic
property ordering, and reflection metadata for the same four model classes.

## Compared operations

- Java object to JSON `String`
- JSON `String` to Java object
- Java object to UTF-8 `byte[]`
- UTF-8 `byte[]` to Java object

The harness rotates through 256 deterministic `Customer` graphs. JVM tests
require both implementations to round-trip every graph and emit identical
String and UTF-8 JSON. Before timing, the runner also requires both native
executables to report the same hash over all 256 serialized payloads.

## Requirements

- GraalVM with `native-image` (the published run uses Oracle GraalVM 25.0.1)
- Maven
- Python 3.9 or newer
- `/usr/bin/time` for peak RSS collection on macOS or Linux

## Build the native executables

```bash
GRAALVM_HOME=/path/to/graalvm ./scripts/build_native.sh
```

The script runs the JVM correctness tests, builds both `-O3` images with
fallback disabled, and runs each native executable's verification mode.

## Run the benchmark

```bash
python3 scripts/run_benchmarks.py --output results/my-run
```

Defaults are seven fresh process forks per operation and library, three seconds
of warmup, five seconds of measurement, and a short cooldown between processes.
Library order alternates within each operation and fork.

For a quick pipeline smoke test:

```bash
python3 scripts/run_benchmarks.py \
  --output results/smoke \
  --forks 1 \
  --warmup-seconds 1 \
  --measure-seconds 1 \
  --cooldown-seconds 0
```

Every process command, return code, stdout, stderr, result, wall time, and peak
RSS is appended to `raw.jsonl` immediately. A completed run also contains:

- `report.md`: answer-first technical report
- `throughput.svg` and `relative-throughput.svg`: report figures
- `summary.csv` and `summary.json`: aggregate statistics
- `environment.json`: commit, toolchain, host, configuration, binary sizes, and hashes
- `report-notes.json`: metric and chart contracts

Regenerate derived files without rerunning the benchmark:

```bash
python3 scripts/render_report.py results/my-run
```

## Measurement boundary

Each sample is a fresh, single-threaded native process. Fixture construction,
input preparation, and round-trip verification happen before the timed region.
The measured loop includes only the selected JSON operation and a common
checksum path that consumes the result. The headline is median operations per
second across process forks; the report also preserves mean, sample standard
deviation, min, max, nanoseconds per operation, paired ratios, binary size, and
peak process RSS.

This is not an HTTP, concurrency, cold-start, latency-percentile, or allocation
benchmark. Results are specific to the recorded machine, model, payload,
toolchain, and configuration.
