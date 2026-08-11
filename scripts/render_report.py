#!/usr/bin/env python3
# Licensed under the Apache License, Version 2.0. See LICENSE for details.
"""Aggregate raw benchmark records and render a repository-native report."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


OPERATION_LABELS = {
    "string-serialize": "String serialize",
    "string-deserialize": "String deserialize",
    "utf8-serialize": "UTF-8 serialize",
    "utf8-deserialize": "UTF-8 deserialize",
}
OPERATION_DESCRIPTIONS = {
    "string-serialize": "Java object to a newly allocated JSON `String`.",
    "string-deserialize": "JSON `String` to a new `Customer` graph.",
    "utf8-serialize": "Java object to a newly allocated UTF-8 `byte[]`.",
    "utf8-deserialize": "UTF-8 `byte[]` to a new `Customer` graph.",
}
LIBRARIES = ["fory-json", "jackson"]
LIBRARY_LABELS = {"fory-json": "Fory JSON", "jackson": "Jackson"}
FORY_COLOR = "#f97316"
JACKSON_COLOR = "#2563eb"
INK = "#172033"
MUTED = "#667085"
GRID = "#d9dee8"
BACKGROUND = "#ffffff"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON on {path}:{line_number}") from error
    return records


def median_optional(values: list[int | float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return statistics.median(present) if present else None


def summarize(
    records: list[dict[str, Any]], environment: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples = [record for record in records if record.get("kind") == "sample"]
    operations = environment["benchmark"]["operations"]
    expected_forks = int(environment["benchmark"]["forks"])
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        groups[(sample["operation"], sample["library"])].append(sample)

    aggregates: list[dict[str, Any]] = []
    for operation in operations:
        for library in LIBRARIES:
            group = sorted(groups[(operation, library)], key=lambda item: int(item["fork"]))
            if len(group) != expected_forks:
                raise ValueError(
                    f"expected {expected_forks} samples for {operation}/{library}, got {len(group)}"
                )
            throughputs = [float(item["result"]["ops_per_second"]) for item in group]
            nanos = [float(item["result"]["ns_per_operation"]) for item in group]
            payloads = [float(item["result"]["average_payload_bytes"]) for item in group]
            rss_values = [item.get("peak_rss_bytes") for item in group]
            mean = statistics.fmean(throughputs)
            standard_deviation = statistics.stdev(throughputs) if len(throughputs) > 1 else 0.0
            aggregates.append(
                {
                    "operation": operation,
                    "library": library,
                    "samples": len(group),
                    "median_ops_per_second": statistics.median(throughputs),
                    "mean_ops_per_second": mean,
                    "stdev_ops_per_second": standard_deviation,
                    "coefficient_of_variation_pct": standard_deviation / mean * 100 if mean else 0.0,
                    "min_ops_per_second": min(throughputs),
                    "max_ops_per_second": max(throughputs),
                    "median_ns_per_operation": statistics.median(nanos),
                    "median_peak_rss_bytes": median_optional(rss_values),
                    "average_payload_bytes": statistics.fmean(payloads),
                    "binary_size_bytes": environment["binaries"][library]["size_bytes"],
                }
            )

    aggregate_lookup = {
        (row["operation"], row["library"]): row for row in aggregates
    }
    sample_lookup = {
        (sample["operation"], sample["library"], int(sample["fork"])): sample
        for sample in samples
    }
    comparisons: list[dict[str, Any]] = []
    for operation in operations:
        fory = aggregate_lookup[(operation, "fory-json")]
        jackson = aggregate_lookup[(operation, "jackson")]
        paired_ratios = []
        for fork in range(1, expected_forks + 1):
            fory_sample = sample_lookup[(operation, "fory-json", fork)]
            jackson_sample = sample_lookup[(operation, "jackson", fork)]
            paired_ratios.append(
                float(fory_sample["result"]["ops_per_second"])
                / float(jackson_sample["result"]["ops_per_second"])
            )
        comparisons.append(
            {
                "operation": operation,
                "fory_to_jackson_median_throughput_ratio": (
                    fory["median_ops_per_second"] / jackson["median_ops_per_second"]
                ),
                "median_paired_ratio": statistics.median(paired_ratios),
                "min_paired_ratio": min(paired_ratios),
                "max_paired_ratio": max(paired_ratios),
            }
        )
    return aggregates, comparisons


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty summary")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def nice_axis(maximum: float, target_ticks: int = 5) -> tuple[float, list[float]]:
    if maximum <= 0:
        return 1.0, [0.0, 1.0]
    raw_step = maximum / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw_step))
    fraction = raw_step / magnitude
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    step = nice_fraction * magnitude
    axis_max = math.ceil(maximum / step) * step
    tick_count = int(round(axis_max / step))
    return axis_max, [step * index for index in range(tick_count + 1)]


def compact_number(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def throughput_unit(maximum: float) -> tuple[float, str]:
    if maximum >= 1_000_000:
        return 1_000_000, "million operations/s"
    if maximum >= 1_000:
        return 1_000, "thousand operations/s"
    return 1, "operations/s"


def svg_text(
    x: float,
    y: float,
    value: str,
    *,
    size: int = 18,
    weight: int = 400,
    anchor: str = "start",
    fill: str = INK,
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Inter, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'fill="{fill}">{html.escape(value)}</text>'
    )


def render_throughput_svg(
    path: Path,
    aggregates: list[dict[str, Any]],
    operations: list[str],
    forks: int,
) -> None:
    lookup = {(row["operation"], row["library"]): row for row in aggregates}
    maximum = max(row["max_ops_per_second"] for row in aggregates) * 1.08
    axis_max, ticks = nice_axis(maximum)
    scale, unit = throughput_unit(axis_max)
    width = 1200
    left = 245
    right = 135
    top = 145
    bottom = 82
    group_height = 118
    bar_height = 29
    bar_gap = 14
    height = top + bottom + group_height * len(operations)
    plot_width = width - left - right
    plot_bottom = top + group_height * len(operations) - 12

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Native Image JSON throughput</title>',
        (
            f'<desc id="desc">Median operations per second across {forks} fresh native processes. '
            "Whiskers show the minimum and maximum sample.</desc>"
        ),
        "<defs>",
        '<pattern id="jackson-pattern" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">',
        f'<rect width="8" height="8" fill="{JACKSON_COLOR}"/>',
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#ffffff" stroke-opacity="0.36" stroke-width="3"/>',
        "</pattern>",
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        svg_text(48, 52, "Native Image JSON throughput", size=30, weight=700),
        svg_text(
            48,
            84,
            f"Median across {forks} fresh processes; whiskers show min–max; higher is better",
            size=17,
            fill=MUTED,
        ),
    ]

    legend_y = 115
    parts.extend(
        [
            f'<rect x="760" y="{legend_y - 16}" width="24" height="16" rx="2" fill="{FORY_COLOR}"/>',
            svg_text(795, legend_y - 2, "Fory JSON", size=15),
            f'<rect x="925" y="{legend_y - 16}" width="24" height="16" rx="2" fill="url(#jackson-pattern)"/>',
            svg_text(960, legend_y - 2, "Jackson", size=15),
        ]
    )

    for tick in ticks:
        x = left + tick / axis_max * plot_width
        parts.append(
            f'<line x1="{x:.1f}" y1="{top - 12}" x2="{x:.1f}" y2="{plot_bottom:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(svg_text(x, plot_bottom + 30, f"{tick / scale:g}", size=14, anchor="middle", fill=MUTED))
    parts.append(svg_text(left + plot_width / 2, height - 20, unit, size=15, anchor="middle", fill=MUTED))

    for operation_index, operation in enumerate(operations):
        group_top = top + operation_index * group_height
        parts.append(
            svg_text(
                left - 22,
                group_top + bar_height + bar_gap / 2,
                OPERATION_LABELS.get(operation, operation),
                size=16,
                weight=600,
                anchor="end",
            )
        )
        for library_index, library in enumerate(LIBRARIES):
            row = lookup[(operation, library)]
            y = group_top + library_index * (bar_height + bar_gap)
            median = row["median_ops_per_second"]
            minimum = row["min_ops_per_second"]
            maximum_value = row["max_ops_per_second"]
            bar_width = median / axis_max * plot_width
            min_x = left + minimum / axis_max * plot_width
            max_x = left + maximum_value / axis_max * plot_width
            center_y = y + bar_height / 2
            fill = FORY_COLOR if library == "fory-json" else "url(#jackson-pattern)"
            parts.append(
                f'<rect x="{left}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height}" '
                f'rx="3" fill="{fill}"/>'
            )
            parts.extend(
                [
                    f'<line x1="{min_x:.1f}" y1="{center_y:.1f}" x2="{max_x:.1f}" y2="{center_y:.1f}" '
                    f'stroke="{INK}" stroke-width="2"/>',
                    f'<line x1="{min_x:.1f}" y1="{center_y - 6:.1f}" x2="{min_x:.1f}" y2="{center_y + 6:.1f}" '
                    f'stroke="{INK}" stroke-width="2"/>',
                    f'<line x1="{max_x:.1f}" y1="{center_y - 6:.1f}" x2="{max_x:.1f}" y2="{center_y + 6:.1f}" '
                    f'stroke="{INK}" stroke-width="2"/>',
                    svg_text(
                        left + bar_width + 9,
                        center_y + 5,
                        compact_number(median),
                        size=14,
                        weight=600,
                    ),
                ]
            )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def render_speedup_svg(
    path: Path,
    comparisons: list[dict[str, Any]],
    operations: list[str],
) -> None:
    lookup = {row["operation"]: row for row in comparisons}
    maximum = max(
        1.0,
        max(row["fory_to_jackson_median_throughput_ratio"] for row in comparisons),
    )
    axis_max, ticks = nice_axis(maximum * 1.13)
    width = 1200
    left = 245
    right = 125
    top = 135
    bottom = 80
    row_height = 82
    bar_height = 35
    height = top + bottom + row_height * len(operations)
    plot_width = width - left - right
    plot_bottom = top + row_height * len(operations) - 20
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Fory JSON throughput relative to Jackson</title>',
        '<desc id="desc">Ratio of median Fory JSON operations per second to median Jackson operations per second.</desc>',
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        svg_text(48, 52, "Fory JSON throughput relative to Jackson", size=30, weight=700),
        svg_text(48, 84, "Ratio of medians; 1.0× means equal throughput", size=17, fill=MUTED),
    ]
    for tick in ticks:
        x = left + tick / axis_max * plot_width
        parts.append(
            f'<line x1="{x:.1f}" y1="{top - 14}" x2="{x:.1f}" y2="{plot_bottom:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(svg_text(x, plot_bottom + 30, f"{tick:g}×", size=14, anchor="middle", fill=MUTED))
    equal_x = left + 1.0 / axis_max * plot_width
    parts.append(
        f'<line x1="{equal_x:.1f}" y1="{top - 14}" x2="{equal_x:.1f}" y2="{plot_bottom:.1f}" '
        f'stroke="{INK}" stroke-width="2" stroke-dasharray="7 6"/>'
    )
    parts.append(svg_text(equal_x + 7, top - 21, "equal", size=13, fill=MUTED))

    for index, operation in enumerate(operations):
        row = lookup[operation]
        ratio = row["fory_to_jackson_median_throughput_ratio"]
        y = top + index * row_height
        bar_width = ratio / axis_max * plot_width
        parts.extend(
            [
                svg_text(
                    left - 22,
                    y + bar_height / 2 + 6,
                    OPERATION_LABELS.get(operation, operation),
                    size=16,
                    weight=600,
                    anchor="end",
                ),
                f'<rect x="{left}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height}" '
                f'rx="3" fill="{FORY_COLOR}"/>',
                svg_text(
                    left + bar_width + 10,
                    y + bar_height / 2 + 6,
                    f"{ratio:.2f}×",
                    size=16,
                    weight=700,
                ),
            ]
        )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def format_ops(value: float) -> str:
    return f"{compact_number(value)} ops/s"


def format_range(minimum: float, maximum: float) -> str:
    return f"{compact_number(minimum)}–{compact_number(maximum)}"


def format_bytes(value: float | int | None) -> str:
    if value is None:
        return "not available"
    return f"{float(value) / 1024 / 1024:.1f} MiB"


def format_memory_capacity(value: float | int | None) -> str:
    if value is None:
        return "not available"
    return f"{float(value) / 1024 / 1024 / 1024:.1f} GiB"


def first_line(value: str) -> str:
    return value.strip().splitlines()[0] if value.strip() else "unknown"


def report_markdown(
    environment: dict[str, Any],
    aggregates: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> str:
    operations = environment["benchmark"]["operations"]
    lookup = {(row["operation"], row["library"]): row for row in aggregates}
    comparison_lookup = {row["operation"]: row for row in comparisons}
    ratios = [row["fory_to_jackson_median_throughput_ratio"] for row in comparisons]
    wins = sum(ratio > 1 for ratio in ratios)
    strongest = max(comparisons, key=lambda row: row["fory_to_jackson_median_throughput_ratio"])
    weakest = min(comparisons, key=lambda row: row["fory_to_jackson_median_throughput_ratio"])
    max_cv = max(row["coefficient_of_variation_pct"] for row in aggregates)
    payload = statistics.fmean(row["average_payload_bytes"] for row in aggregates)
    benchmark = environment["benchmark"]
    system = environment["system"]
    dependencies = environment["dependencies"]
    repository = environment["repository"]
    commit_suffix = " (dirty)" if repository["dirty"] else ""
    fork_count = int(benchmark["forks"])
    process_phrase = "1 fresh native process" if fork_count == 1 else f"{fork_count} fresh native processes"
    warmup_phrase = (
        "1-second warmup"
        if benchmark["warmup_seconds"] == 1
        else f"{benchmark['warmup_seconds']}-second warmup"
    )
    measure_phrase = (
        "1-second measurement window"
        if benchmark["measure_seconds"] == 1
        else f"{benchmark['measure_seconds']}-second measurement window"
    )
    if fork_count == 1:
        variation_sentence = "A single-fork smoke run cannot estimate sample variation."
        measurement_summary = (
            f"Each headline is the result from {process_phrase} after a {warmup_phrase} and a "
            f"{measure_phrase}. Both libraries processed the same 256 rotating object graphs and "
            f"emitted identical JSON bytes (average payload {payload:.1f} bytes). "
            f"{variation_sentence}"
        )
    else:
        variation_sentence = (
            f"The largest sample coefficient of variation was {max_cv:.2f}%."
        )
        measurement_summary = (
            f"Each headline is the median of {process_phrase} after a {warmup_phrase} and a "
            f"{measure_phrase}. Both libraries processed the same 256 rotating object graphs and "
            f"emitted identical JSON bytes (average payload {payload:.1f} bytes). "
            f"{variation_sentence}"
        )
    if wins == len(operations):
        throughput_heading = (
            "Fory JSON records higher native throughput in the selected operation"
            if len(operations) == 1
            else f"Fory JSON records higher native throughput in all {len(operations)} operations"
        )
        relative_heading = "Fory JSON leads each relative throughput comparison in this run"
    elif wins == 0:
        throughput_heading = (
            "Jackson records at least as much native throughput in the selected operation"
            if len(operations) == 1
            else "Jackson records at least as much native throughput in every operation"
        )
        relative_heading = "Jackson leads each relative throughput comparison in this run"
    else:
        throughput_heading = "Native throughput leadership varies by operation"
        relative_heading = "Relative throughput varies by operation"

    if wins == len(operations):
        if len(operations) == 1:
            result_sentence = (
                f"Fory JSON recorded {ratios[0]:.2f}× Jackson's median throughput in the "
                "selected operation."
            )
        else:
            result_sentence = (
                f"Fory JSON recorded higher median throughput in all {len(operations)} operations, "
                f"from {min(ratios):.2f}× to {max(ratios):.2f}× Jackson."
            )
    elif wins == 0:
        if len(operations) == 1:
            result_sentence = (
                f"The Fory/Jackson median throughput ratio was {ratios[0]:.2f}× in the "
                "selected operation."
            )
        else:
            result_sentence = (
                f"Jackson recorded at least as much median throughput in all {len(operations)} operations; "
                f"the Fory/Jackson ratios ranged from {min(ratios):.2f}× to {max(ratios):.2f}×."
            )
    else:
        result_sentence = (
            f"Fory JSON recorded higher median throughput in {wins} of {len(operations)} operations; "
            f"the Fory/Jackson ratios ranged from {min(ratios):.2f}× to {max(ratios):.2f}×."
        )

    if len(operations) == 1:
        result_detail = ""
    else:
        result_detail = (
            f" The strongest relative result was {OPERATION_LABELS[strongest['operation']]} at "
            f"{strongest['fory_to_jackson_median_throughput_ratio']:.2f}×; the narrowest was "
            f"{OPERATION_LABELS[weakest['operation']]} at "
            f"{weakest['fory_to_jackson_median_throughput_ratio']:.2f}×."
        )
    measurement_bullets = [
        f"- **{OPERATION_LABELS.get(operation, operation)}:** "
        f"{OPERATION_DESCRIPTIONS[operation]}"
        for operation in operations
    ]

    lines = [
        "# GraalVM Native Image JSON performance: Fory JSON vs. Jackson",
        "",
        "## Technical summary",
        "",
        f"On this machine and benchmark harness, {result_sentence}{result_detail}",
        "",
        measurement_summary,
        "",
        "This is a codec-layer comparison. Jackson uses conventional Databind with explicit Native Image "
        "reflection metadata; it does **not** use the experimental reflection-free Jackson serializer "
        "generator described in the Quarkus metaprogramming article.",
        "",
        f"## {throughput_heading}",
        "",
        "The chart compares completed operations per second; longer bars are faster. Bars show each "
        "library's median, while the whiskers expose the full min–max spread across independent process "
        "forks. The exact values are in the table immediately below.",
        "",
        "![Native Image JSON throughput](throughput.svg)",
        "",
        "| Operation | Fory JSON median | Jackson median | Fory / Jackson | Fory min–max | Jackson min–max |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for operation in operations:
        fory = lookup[(operation, "fory-json")]
        jackson = lookup[(operation, "jackson")]
        comparison = comparison_lookup[operation]
        lines.append(
            f"| {OPERATION_LABELS.get(operation, operation)} "
            f"| {format_ops(fory['median_ops_per_second'])} "
            f"| {format_ops(jackson['median_ops_per_second'])} "
            f"| {comparison['fory_to_jackson_median_throughput_ratio']:.2f}× "
            f"| {format_range(fory['min_ops_per_second'], fory['max_ops_per_second'])} "
            f"| {format_range(jackson['min_ops_per_second'], jackson['max_ops_per_second'])} |"
        )

    lines.extend(
        [
            "",
            f"## {relative_heading}",
            "",
            "The relative chart divides the two median throughputs for each operation. As a sensitivity "
            "check, the table also pairs Fory and Jackson samples from the same fork and reports the full "
            "range of paired ratios.",
            "",
            "![Fory JSON throughput relative to Jackson](relative-throughput.svg)",
            "",
            "| Operation | Ratio of medians | Median paired ratio | Paired min–max |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for operation in operations:
        comparison = comparison_lookup[operation]
        lines.append(
            f"| {OPERATION_LABELS.get(operation, operation)} "
            f"| {comparison['fory_to_jackson_median_throughput_ratio']:.2f}× "
            f"| {comparison['median_paired_ratio']:.2f}× "
            f"| {comparison['min_paired_ratio']:.2f}×–{comparison['max_paired_ratio']:.2f}× |"
        )

    lines.extend(
        [
            "",
            "## What was measured",
            "",
            "The payload follows the `Customer` shape from the "
            "[Quarkus metaprogramming article](https://quarkus.io/blog/quarkus-metaprogramming/): "
            "inherited person fields, an address, two children, two credit cards, and income. The harness "
            "rotates through 256 deterministic variations so one constant object cannot define the entire "
            "workload.",
            "",
            *measurement_bullets,
            "",
            "Throughput is completed operations divided by the measured nanoseconds inside the native "
            "process. Serialization consumes output length and a byte or character; deserialization "
            "computes a fingerprint over the decoded graph. These checksum paths prevent dead-code "
            "elimination and are identical across libraries.",
            "",
            "## Build-time integration and benchmark method",
            "",
            f"Fory JSON {dependencies['fory_json']} and Jackson Databind "
            f"{dependencies['jackson_databind']} were compiled into separate executables with the same "
            "GraalVM Native Image toolchain, `-O3`, and `--no-fallback`. Keeping separate images prevents "
            "one library or its metadata from becoming reachable in the other's executable.",
            "",
            "Fory registers four mix-ins and exposes the benchmark configuration through a reachable "
            "`@ForyJsonProvider`, allowing its Native Image Feature to generate object codecs at image build "
            "time. The single-threaded configuration uses field mode with a concurrency level of one and "
            "disables asynchronous compilation. Jackson uses a field-only `ObjectMapper`, alphabetic property "
            "ordering, and explicit reflection metadata for the same four model classes.",
            "",
            f"For every operation, the runner launched {process_phrase} and alternated "
            "which library ran first. Each process prepared and verified its fixtures outside the timed "
            f"region, used a {warmup_phrase}, then used a {measure_phrase} in batches of "
            f"{benchmark['batch_size']}. The JVM "
            "test suite separately checks all 256 round trips, semantic JSON equality, and exact String and "
            "UTF-8 output equality. Before native timing, the runner also requires both native executables "
            "to report the same hash over all 256 serialized payloads.",
            "",
            "## Executable size and peak process memory",
            "",
            "Executable size is the final file size. Peak resident set size (RSS) is the high-water mark "
            "reported by the operating-system `time` utility for each complete benchmark process, including "
            "fixture preparation and the timed phase; it is not an allocation-rate measurement.",
            "",
            "| Library | Native executable |",
            "| --- | ---: |",
            f"| Fory JSON | {format_bytes(environment['binaries']['fory-json']['size_bytes'])} |",
            f"| Jackson | {format_bytes(environment['binaries']['jackson']['size_bytes'])} |",
            "",
            "| Operation | Fory JSON median peak RSS | Jackson median peak RSS |",
            "| --- | ---: | ---: |",
        ]
    )
    for operation in operations:
        fory = lookup[(operation, "fory-json")]
        jackson = lookup[(operation, "jackson")]
        lines.append(
            f"| {OPERATION_LABELS.get(operation, operation)} "
            f"| {format_bytes(fory['median_peak_rss_bytes'])} "
            f"| {format_bytes(jackson['median_peak_rss_bytes'])} |"
        )

    lines.extend(
        [
            "",
            "## Test environment",
            "",
            "| Item | Value |",
            "| --- | --- |",
            f"| CPU | {system['cpu_model']} ({system['logical_cpu_count']} logical CPUs) |",
            f"| Memory | {format_memory_capacity(system['memory_bytes'])} |",
            f"| OS | {system['platform']} |",
            f"| Native Image | {first_line(environment['toolchain']['native_image'])} |",
            f"| Fory JSON | {dependencies['fory_json']} |",
            f"| Jackson Databind | {dependencies['jackson_databind']} |",
            f"| Repository commit | `{repository['commit']}`{commit_suffix} |",
            "",
            "## Limits and robustness",
            "",
            "- These results describe one model, payload size, machine, Native Image version, and library "
            "configuration. They do not establish a universal multiplier.",
            "- The harness measures steady-state codec throughput after warmup. It does not measure cold "
            "startup, first-request latency, HTTP routing, sockets, concurrency, garbage-collection pauses, "
            "or allocation rate.",
            "- The Jackson baseline is conventional Databind under Native Image. Comparing Fory against "
            "Quarkus's generated Jackson serializers would require a different adapter and is outside this run.",
            "- Min–max ranges, sample standard deviation, paired ratios, every command, stdout, stderr, and "
            "peak RSS reading are retained in the saved artifacts so variation is auditable.",
            "",
            "## Recommended next steps",
            "",
            "1. Repeat the same committed harness on the deployment CPU and GraalVM release used in production.",
            "2. Add representative application models and payload distributions before making a framework decision.",
            "3. Use an end-to-end service benchmark if the decision depends on request throughput rather than "
            "JSON codec cost alone.",
            "",
            "## Further questions",
            "",
            "- How do the relative results change with larger payloads, escaped Unicode, null-heavy objects, "
            "or deeply nested collections?",
            "- What do allocation profiles and latency percentiles show for each operation?",
            "- How do profile-guided Native Image builds and Quarkus-generated Jackson serializers change the comparison?",
            "",
            "## Reproduce the run",
            "",
            "Build and verify both native executables:",
            "",
            "```bash",
            "GRAALVM_HOME=/path/to/graalvm ./scripts/build_native.sh",
            "```",
            "",
            "Run the full default benchmark:",
            "",
            "```bash",
            "python3 scripts/run_benchmarks.py --output results/my-run",
            "```",
            "",
            "Regenerate this report from saved raw records:",
            "",
            "```bash",
            "python3 scripts/render_report.py results/my-run",
            "```",
            "",
            "The saved evidence is in [`raw.jsonl`](raw.jsonl), [`summary.csv`](summary.csv), "
            "[`summary.json`](summary.json), [`environment.json`](environment.json), and "
            "[`report-notes.json`](report-notes.json).",
            "",
        ]
    )
    return "\n".join(lines)


def render_report(output: Path) -> None:
    environment = load_json(output / "environment.json")
    records = load_records(output / "raw.jsonl")
    aggregates, comparisons = summarize(records, environment)
    operations = environment["benchmark"]["operations"]
    write_csv(output / "summary.csv", aggregates)
    (output / "summary.json").write_text(
        json.dumps(
            {"aggregates": aggregates, "comparisons": comparisons},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    render_throughput_svg(
        output / "throughput.svg",
        aggregates,
        operations,
        int(environment["benchmark"]["forks"]),
    )
    render_speedup_svg(output / "relative-throughput.svg", comparisons, operations)
    notes = {
        "audience": "technical",
        "primary_surface": "repository-native Markdown",
        "chart_map": [
            {
                "section": "Native throughput across four JSON operations",
                "question": "How does median native throughput compare by operation and library?",
                "family": "comparison and ranking",
                "type": "grouped horizontal bar with min-max whiskers",
                "fields": [
                    "operation",
                    "library",
                    "median_ops_per_second",
                    "min_ops_per_second",
                    "max_ops_per_second",
                ],
                "palette": "hard two-root cap: orange and blue, with a hatch for Jackson",
                "artifact": "throughput.svg",
            },
            {
                "section": "Fory JSON throughput relative to Jackson",
                "question": "What is Fory JSON throughput relative to Jackson for each operation?",
                "family": "comparison and benchmark",
                "type": "horizontal ratio bar with a 1.0x reference",
                "fields": ["operation", "fory_to_jackson_median_throughput_ratio"],
                "palette": "single orange root plus a neutral reference line",
                "artifact": "relative-throughput.svg",
            },
        ],
        "omitted_visuals": [
            {
                "topic": "native executable size and peak RSS",
                "reason": "Only two libraries are compared and exact lookup is more useful; report tables are clearer than additional charts.",
            }
        ],
        "ratio_definition": "Fory median operations/s divided by Jackson median operations/s",
        "primary_metric": "median operations per second across independent native processes",
    }
    (output / "report-notes.json").write_text(
        json.dumps(notes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(
        report_markdown(environment, aggregates, comparisons), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="benchmark result directory")
    args = parser.parse_args()
    output = args.output.resolve()
    render_report(output)
    print(output / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
