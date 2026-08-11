#!/usr/bin/env python3
# Licensed under the Apache License, Version 2.0. See LICENSE for details.
"""Run isolated native benchmark forks and preserve every process result."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from render_report import render_report


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPERATIONS = [
    "string-serialize",
    "string-deserialize",
    "utf8-serialize",
    "utf8-deserialize",
]
TIME_BINARY = Path("/usr/bin/time")


def sanitize_text(value: str) -> str:
    sanitized = value.replace(str(ROOT), "$REPO")
    sanitized = sanitized.replace(str(Path.home()), "$HOME")
    return re.sub(r"\x1b\[[0-9;]*m", "", sanitized)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args() -> argparse.Namespace:
    timestamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results") / f"run-{timestamp}",
        help="new output directory (default: results/run-<timestamp>)",
    )
    parser.add_argument(
        "--fory-bin",
        type=Path,
        default=Path("fory-app/target/fory-json-benchmark"),
    )
    parser.add_argument(
        "--jackson-bin",
        type=Path,
        default=Path("jackson-app/target/jackson-benchmark"),
    )
    parser.add_argument("--forks", type=positive_int, default=7)
    parser.add_argument("--warmup-seconds", type=positive_int, default=3)
    parser.add_argument("--measure-seconds", type=positive_int, default=5)
    parser.add_argument("--batch-size", type=positive_int, default=64)
    parser.add_argument("--cooldown-seconds", type=nonnegative_float, default=0.5)
    parser.add_argument(
        "--operations",
        nargs="+",
        choices=DEFAULT_OPERATIONS,
        default=DEFAULT_OPERATIONS,
    )
    return parser.parse_args()


def resolve_from_root(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def run_capture(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {error}"
    output = sanitize_text((result.stdout + result.stderr).strip())
    return output if output else f"exit code {result.returncode}"


def git_state() -> dict[str, Any]:
    commit = run_capture(["git", "rev-parse", "HEAD"]).splitlines()[0]
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    status = completed.stdout.strip()
    return {
        "commit": commit,
        "dirty": bool(status),
        "status_porcelain": status,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def memory_bytes() -> int | None:
    if sys.platform == "darwin":
        value = run_capture(["sysctl", "-n", "hw.memsize"])
        return int(value) if value.isdigit() else None
    memory = Path("/proc/meminfo")
    if memory.exists():
        match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", memory.read_text(), re.MULTILINE)
        return int(match.group(1)) * 1024 if match else None
    return None


def cpu_model() -> str:
    if sys.platform == "darwin":
        arm = run_capture(["sysctl", "-n", "machdep.cpu.brand_string"])
        if not arm.startswith("unavailable") and not arm.startswith("exit code"):
            return arm
        return run_capture(["sysctl", "-n", "hw.model"])
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        match = re.search(r"^(?:model name|Hardware)\s*:\s*(.+)$", cpuinfo.read_text(), re.MULTILINE)
        if match:
            return match.group(1).strip()
    return platform.processor() or "unknown"


def pom_versions() -> dict[str, str]:
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
    root = ET.parse(ROOT / "pom.xml").getroot()
    properties = root.find("m:properties", namespace)
    if properties is None:
        return {}
    return {child.tag.split("}")[-1]: child.text or "" for child in properties}


def configured_graalvm_home() -> Path | None:
    java_home = os.environ.get("GRAALVM_HOME") or os.environ.get("JAVA_HOME")
    if java_home:
        return Path(java_home)
    return None


def native_image_command() -> list[str] | None:
    graalvm_home = configured_graalvm_home()
    if graalvm_home:
        candidate = graalvm_home / "bin" / "native-image"
        if candidate.is_file():
            return [str(candidate), "--version"]
    candidate = shutil.which("native-image")
    return [candidate, "--version"] if candidate else None


def java_command() -> list[str]:
    graalvm_home = configured_graalvm_home()
    if graalvm_home and (graalvm_home / "bin" / "java").is_file():
        return [str(graalvm_home / "bin" / "java"), "-version"]
    return ["java", "-version"]


def maven_command() -> list[str]:
    graalvm_home = configured_graalvm_home()
    if graalvm_home:
        return [
            "env",
            f"JAVA_HOME={graalvm_home}",
            f"PATH={graalvm_home / 'bin'}:{os.environ.get('PATH', '')}",
            "mvn",
            "-version",
        ]
    return ["mvn", "-version"]


def time_mode() -> str | None:
    if not TIME_BINARY.is_file():
        return None
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def timed_command(command: list[str], mode: str | None) -> list[str]:
    if mode == "darwin":
        return [str(TIME_BINARY), "-l", *command]
    if mode == "linux":
        return [str(TIME_BINARY), "-v", *command]
    return command


def parse_peak_rss(stderr: str, mode: str | None) -> int | None:
    if mode == "darwin":
        match = re.search(r"^\s*(\d+)\s+maximum resident set size\s*$", stderr, re.MULTILINE)
        return int(match.group(1)) if match else None
    if mode == "linux":
        match = re.search(
            r"^\s*Maximum resident set size \(kbytes\):\s*(\d+)\s*$",
            stderr,
            re.MULTILINE,
        )
        return int(match.group(1)) * 1024 if match else None
    return None


def extract_json(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "status" in value:
            return value
    raise RuntimeError(f"process produced no result JSON: {stdout!r}")


def run_process(
    binary: Path,
    arguments: list[str],
    expected_library: str,
    expected_operation: str | None,
    mode: str | None,
) -> dict[str, Any]:
    base_command = [str(binary), *arguments]
    command = timed_command(base_command, mode)
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C", "LANG": "C"})
    timeout = 60
    if "--warmup-seconds" in arguments and "--measure-seconds" in arguments:
        warmup = int(arguments[arguments.index("--warmup-seconds") + 1])
        measure = int(arguments[arguments.index("--measure-seconds") + 1])
        timeout += warmup + measure
    started_at = dt.datetime.now(dt.timezone.utc).isoformat()
    wall_start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        timeout=timeout,
    )
    wall_seconds = time.perf_counter() - wall_start
    result = extract_json(completed.stdout) if completed.returncode == 0 else None
    display_binary = (
        str(binary.relative_to(ROOT)) if binary.is_relative_to(ROOT) else str(binary)
    )
    record: dict[str, Any] = {
        "recorded_at": started_at,
        "command": [display_binary, *arguments],
        "return_code": completed.returncode,
        "wall_seconds": wall_seconds,
        "peak_rss_bytes": parse_peak_rss(completed.stderr, mode),
        "stdout": sanitize_text(completed.stdout),
        "stderr": sanitize_text(completed.stderr),
        "result": result,
    }
    if completed.returncode != 0:
        raise ProcessError("benchmark process failed", record)
    if result is None or result.get("status") != "ok":
        raise ProcessError("benchmark process returned an invalid result", record)
    if result.get("library") != expected_library or result.get("runtime") != "native":
        raise ProcessError("benchmark process identity did not match", record)
    if expected_operation is not None and result.get("operation") != expected_operation:
        raise ProcessError("benchmark process operation did not match", record)
    if expected_library == "fory-json" and "using interpreted codecs" in (
        completed.stdout + completed.stderr
    ):
        raise ProcessError("Fory JSON did not use its generated native codecs", record)
    return record


class ProcessError(RuntimeError):
    def __init__(self, message: str, record: dict[str, Any]):
        super().__init__(message)
        self.record = record


def environment_metadata(
    args: argparse.Namespace,
    binaries: dict[str, Path],
    repository: dict[str, Any],
    mode: str | None,
) -> dict[str, Any]:
    native_command = native_image_command()
    versions = pom_versions()
    return {
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository": repository,
        "system": {
            "platform": platform.platform(),
            "uname": {
                key: value
                for key, value in platform.uname()._asdict().items()
                if key != "node"
            },
            "os_version": run_capture(["sw_vers"]) if sys.platform == "darwin" else run_capture(["uname", "-a"]),
            "cpu_model": cpu_model(),
            "logical_cpu_count": os.cpu_count(),
            "memory_bytes": memory_bytes(),
        },
        "toolchain": {
            "java": run_capture(java_command()),
            "native_image": run_capture(native_command) if native_command else "unavailable",
            "maven": run_capture(maven_command()),
            "python": sys.version,
        },
        "dependencies": {
            "fory_json": versions.get("fory.version"),
            "jackson_databind": versions.get("jackson.version"),
            "native_maven_plugin": versions.get("native.maven.plugin.version"),
        },
        "native_build": {
            "optimization": "-O3",
            "fallback": False,
            "reachability_metadata_repository": False,
        },
        "benchmark": {
            "forks": args.forks,
            "warmup_seconds": args.warmup_seconds,
            "measure_seconds": args.measure_seconds,
            "batch_size": args.batch_size,
            "cooldown_seconds": args.cooldown_seconds,
            "operations": args.operations,
            "fixture_count": 256,
            "time_tool_mode": mode,
        },
        "binaries": {
            library: {
                "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for library, path in binaries.items()
        },
        "source_context": {
            "quarkus_article": "https://quarkus.io/blog/quarkus-metaprogramming/",
            "scope": "JSON codec layer; not HTTP endpoint throughput",
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    binaries = {
        "fory-json": resolve_from_root(args.fory_bin),
        "jackson": resolve_from_root(args.jackson_bin),
    }
    for library, binary in binaries.items():
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise SystemExit(f"{library} executable is missing or not executable: {binary}")

    output = resolve_from_root(args.output)
    repository = git_state()
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise SystemExit(f"output directory already exists: {output}") from error

    mode = time_mode()
    metadata = environment_metadata(args, binaries, repository, mode)
    write_json(output / "environment.json", metadata)
    write_json(output / "status.json", {"status": "running", "started_at": metadata["started_at"]})

    raw_path = output / "raw.jsonl"
    total_samples = args.forks * len(args.operations) * len(binaries)
    completed_samples = 0
    verification_payloads: dict[str, float] = {}
    verification_hashes: dict[str, str] = {}
    try:
        with raw_path.open("x", encoding="utf-8") as raw:
            for library, binary in binaries.items():
                print(f"[verify] {library}", flush=True)
                try:
                    record = run_process(binary, ["--verify"], library, None, mode)
                except ProcessError as error:
                    record = error.record
                    record["kind"] = "verification"
                    raw.write(json.dumps(record, sort_keys=True) + "\n")
                    raw.flush()
                    raise
                record["kind"] = "verification"
                raw.write(json.dumps(record, sort_keys=True) + "\n")
                raw.flush()
                verification_payloads[library] = float(record["result"]["average_payload_bytes"])
                verification_hashes[library] = str(record["result"]["payload_hash"])

            if len(set(verification_payloads.values())) != 1:
                raise RuntimeError(f"native payload sizes differ: {verification_payloads}")
            if len(set(verification_hashes.values())) != 1:
                raise RuntimeError(f"native payload hashes differ: {verification_hashes}")

            libraries = list(binaries)
            for fork in range(1, args.forks + 1):
                for operation_index, operation in enumerate(args.operations):
                    order = libraries if (fork + operation_index) % 2 else list(reversed(libraries))
                    for order_index, library in enumerate(order, start=1):
                        completed_samples += 1
                        print(
                            f"[{completed_samples}/{total_samples}] fork={fork} "
                            f"operation={operation} library={library}",
                            flush=True,
                        )
                        arguments = [
                            "--operation",
                            operation,
                            "--warmup-seconds",
                            str(args.warmup_seconds),
                            "--measure-seconds",
                            str(args.measure_seconds),
                            "--batch-size",
                            str(args.batch_size),
                        ]
                        try:
                            record = run_process(
                                binaries[library], arguments, library, operation, mode
                            )
                        except ProcessError as error:
                            record = error.record
                            record.update(
                                {
                                    "kind": "sample",
                                    "fork": fork,
                                    "order_in_pair": order_index,
                                    "library": library,
                                    "operation": operation,
                                }
                            )
                            raw.write(json.dumps(record, sort_keys=True) + "\n")
                            raw.flush()
                            raise
                        record.update(
                            {
                                "kind": "sample",
                                "fork": fork,
                                "order_in_pair": order_index,
                                "library": library,
                                "operation": operation,
                            }
                        )
                        raw.write(json.dumps(record, sort_keys=True) + "\n")
                        raw.flush()
                        throughput = float(record["result"]["ops_per_second"])
                        rss = record["peak_rss_bytes"]
                        rss_text = f", peak RSS {rss / 1024 / 1024:.1f} MiB" if rss else ""
                        print(f"  {throughput:,.0f} ops/s{rss_text}", flush=True)
                        if args.cooldown_seconds:
                            time.sleep(args.cooldown_seconds)

        render_report(output)
        finished_at = dt.datetime.now(dt.timezone.utc).isoformat()
        write_json(
            output / "status.json",
            {
                "status": "complete",
                "started_at": metadata["started_at"],
                "finished_at": finished_at,
                "samples": total_samples,
            },
        )
        print(f"Report: {output / 'report.md'}", flush=True)
        return 0
    except Exception as error:
        write_json(
            output / "status.json",
            {
                "status": "failed",
                "started_at": metadata["started_at"],
                "failed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "error": f"{type(error).__name__}: {error}",
                "completed_samples": completed_samples,
            },
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
