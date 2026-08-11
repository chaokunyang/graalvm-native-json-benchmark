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
DISPLAY_ORDER = ["fory-json", "jackson-generated", "jackson"]
LIBRARY_LABELS = {
    "fory-json": "Fory JSON",
    "jackson-generated": "Jackson (build-time generated)",
    "jackson": "Jackson (ordinary Databind)",
}
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


def selected_libraries(environment: dict[str, Any]) -> list[str]:
    configured = list(environment["benchmark"].get("libraries", ["fory-json", "jackson"]))
    return [library for library in DISPLAY_ORDER if library in configured] + [
        library for library in configured if library not in DISPLAY_ORDER
    ]


def summarize(
    records: list[dict[str, Any]], environment: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples = [record for record in records if record.get("kind") == "sample"]
    operations = environment["benchmark"]["operations"]
    expected_forks = int(environment["benchmark"]["forks"])
    libraries = selected_libraries(environment)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        groups[(sample["operation"], sample["library"])].append(sample)

    aggregates: list[dict[str, Any]] = []
    for operation in operations:
        for library in libraries:
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
    if "fory-json" not in libraries:
        raise ValueError("the report requires the fory-json configuration")
    for operation in operations:
        fory = aggregate_lookup[(operation, "fory-json")]
        for baseline in (library for library in libraries if library != "fory-json"):
            baseline_aggregate = aggregate_lookup[(operation, baseline)]
            paired_ratios = []
            for fork in range(1, expected_forks + 1):
                fory_sample = sample_lookup[(operation, "fory-json", fork)]
                baseline_sample = sample_lookup[(operation, baseline, fork)]
                paired_ratios.append(
                    float(fory_sample["result"]["ops_per_second"])
                    / float(baseline_sample["result"]["ops_per_second"])
                )
            comparisons.append(
                {
                    "operation": operation,
                    "baseline": baseline,
                    "fory_to_baseline_median_throughput_ratio": (
                        fory["median_ops_per_second"]
                        / baseline_aggregate["median_ops_per_second"]
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


def library_fill(library: str) -> str:
    if library == "fory-json":
        return FORY_COLOR
    if library == "jackson-generated":
        return JACKSON_COLOR
    if library == "jackson":
        return "url(#ordinary-jackson-pattern)"
    raise ValueError(f"no chart style for library {library}")


def render_throughput_svg(
    path: Path,
    aggregates: list[dict[str, Any]],
    operations: list[str],
    libraries: list[str],
    forks: int,
) -> None:
    lookup = {(row["operation"], row["library"]): row for row in aggregates}
    maximum = max(row["max_ops_per_second"] for row in aggregates) * 1.08
    axis_max, ticks = nice_axis(maximum)
    scale, unit = throughput_unit(axis_max)
    width = 1300
    left = 270
    right = 155
    top = 155
    bottom = 82
    bar_height = 27
    bar_gap = 10
    group_height = len(libraries) * (bar_height + bar_gap) + 30
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
        '<pattern id="ordinary-jackson-pattern" width="8" height="8" patternUnits="userSpaceOnUse" '
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

    legend_y = 119
    legend_start = 430 if len(libraries) == 3 else 650
    legend_gap = 290
    for index, library in enumerate(libraries):
        legend_x = legend_start + index * legend_gap
        parts.extend(
            [
                f'<rect x="{legend_x}" y="{legend_y - 16}" width="24" height="16" '
                f'rx="2" fill="{library_fill(library)}"/>',
                svg_text(legend_x + 34, legend_y - 2, LIBRARY_LABELS[library], size=15),
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
                group_top + (len(libraries) * (bar_height + bar_gap) - bar_gap) / 2 + 6,
                OPERATION_LABELS.get(operation, operation),
                size=16,
                weight=600,
                anchor="end",
            )
        )
        for library_index, library in enumerate(libraries):
            row = lookup[(operation, library)]
            y = group_top + library_index * (bar_height + bar_gap)
            median = row["median_ops_per_second"]
            minimum = row["min_ops_per_second"]
            maximum_value = row["max_ops_per_second"]
            bar_width = median / axis_max * plot_width
            min_x = left + minimum / axis_max * plot_width
            max_x = left + maximum_value / axis_max * plot_width
            center_y = y + bar_height / 2
            fill = library_fill(library)
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
    baselines: list[str],
) -> None:
    title = (
        "Fory JSON throughput relative to both Jackson configurations"
        if len(baselines) > 1
        else "Fory JSON throughput relative to Jackson"
    )
    configuration_word = "configurations" if len(baselines) > 1 else "configuration"
    description = (
        f"Ratios of median Fory JSON operations per second to the Jackson {configuration_word}. "
        "Whiskers show paired min–max ratios."
    )
    lookup = {(row["operation"], row["baseline"]): row for row in comparisons}
    maximum = max(
        1.0,
        max(
            max(
                row["fory_to_baseline_median_throughput_ratio"],
                row["max_paired_ratio"],
            )
            for row in comparisons
        ),
    )
    axis_max, ticks = nice_axis(maximum * 1.10)
    width = 1300
    left = 270
    right = 145
    top = 155
    bottom = 80
    bar_height = 30
    bar_gap = 11
    group_height = len(baselines) * (bar_height + bar_gap) + 28
    height = top + bottom + group_height * len(operations)
    plot_width = width - left - right
    plot_bottom = top + group_height * len(operations) - 16
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{html.escape(description)}</desc>',
        "<defs>",
        '<pattern id="ordinary-ratio-pattern" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">',
        f'<rect width="8" height="8" fill="{FORY_COLOR}"/>',
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#ffffff" stroke-opacity="0.42" stroke-width="3"/>',
        "</pattern>",
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        svg_text(48, 52, title, size=30, weight=700),
        svg_text(
            48,
            84,
            "Bars show ratios of medians; whiskers show paired min–max; 1.0× means equal throughput",
            size=17,
            fill=MUTED,
        ),
    ]
    legend_y = 119
    for index, baseline in enumerate(baselines):
        legend_x = 650 + index * 305
        fill = FORY_COLOR if baseline == "jackson-generated" else "url(#ordinary-ratio-pattern)"
        parts.extend(
            [
                f'<rect x="{legend_x}" y="{legend_y - 16}" width="24" height="16" '
                f'rx="2" fill="{fill}"/>',
                svg_text(legend_x + 34, legend_y - 2, f"vs. {LIBRARY_LABELS[baseline]}", size=15),
            ]
        )
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

    for operation_index, operation in enumerate(operations):
        group_top = top + operation_index * group_height
        parts.append(
            svg_text(
                left - 22,
                group_top + (len(baselines) * (bar_height + bar_gap) - bar_gap) / 2 + 6,
                OPERATION_LABELS.get(operation, operation),
                size=16,
                weight=600,
                anchor="end",
            )
        )
        for baseline_index, baseline in enumerate(baselines):
            row = lookup[(operation, baseline)]
            ratio = row["fory_to_baseline_median_throughput_ratio"]
            y = group_top + baseline_index * (bar_height + bar_gap)
            bar_width = ratio / axis_max * plot_width
            min_x = left + row["min_paired_ratio"] / axis_max * plot_width
            max_x = left + row["max_paired_ratio"] / axis_max * plot_width
            center_y = y + bar_height / 2
            fill = FORY_COLOR if baseline == "jackson-generated" else "url(#ordinary-ratio-pattern)"
            parts.extend(
                [
                    f'<rect x="{left}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height}" '
                    f'rx="3" fill="{fill}"/>',
                    f'<line x1="{min_x:.1f}" y1="{center_y:.1f}" x2="{max_x:.1f}" y2="{center_y:.1f}" '
                    f'stroke="{INK}" stroke-width="2"/>',
                    f'<line x1="{min_x:.1f}" y1="{center_y - 6:.1f}" x2="{min_x:.1f}" y2="{center_y + 6:.1f}" '
                    f'stroke="{INK}" stroke-width="2"/>',
                    f'<line x1="{max_x:.1f}" y1="{center_y - 6:.1f}" x2="{max_x:.1f}" y2="{center_y + 6:.1f}" '
                    f'stroke="{INK}" stroke-width="2"/>',
                    svg_text(
                        left + bar_width + 10,
                        center_y + 6,
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


def format_variation(row: dict[str, Any], forks: int) -> str:
    value_range = format_range(row["min_ops_per_second"], row["max_ops_per_second"])
    if forks == 1:
        return f"{value_range} (CV n/a)"
    return f"{value_range} ({row['coefficient_of_variation_pct']:.2f}% CV)"


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


def verification_result(
    records: list[dict[str, Any]], library: str
) -> dict[str, Any] | None:
    for record in records:
        result = record.get("result") or {}
        if record.get("kind") == "verification" and result.get("library") == library:
            return result
    return None


def baseline_summary(label: str, ratios: list[float]) -> str:
    wins = sum(ratio > 1.0 for ratio in ratios)
    ratio_range = f"{min(ratios):.2f}×–{max(ratios):.2f}×"
    if wins == len(ratios):
        return f"Fory JSON had higher median throughput than {label} in every operation ({ratio_range})."
    if wins == 0:
        return f"Fory JSON did not exceed {label} in these operations ({ratio_range})."
    return f"Fory JSON had higher median throughput than {label} in {wins} of {len(ratios)} operations ({ratio_range})."


def report_markdown(
    environment: dict[str, Any],
    records: list[dict[str, Any]],
    aggregates: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> str:
    benchmark = environment["benchmark"]
    operations = benchmark["operations"]
    libraries = selected_libraries(environment)
    baselines = [library for library in libraries if library != "fory-json"]
    lookup = {(row["operation"], row["library"]): row for row in aggregates}
    comparison_lookup = {
        (row["operation"], row["baseline"]): row for row in comparisons
    }
    max_cv = max(row["coefficient_of_variation_pct"] for row in aggregates)
    payload = statistics.fmean(row["average_payload_bytes"] for row in aggregates)
    system = environment["system"]
    dependencies = environment["dependencies"]
    repository = environment["repository"]
    commit_suffix = " (dirty)" if repository["dirty"] else ""
    fork_count = int(benchmark["forks"])
    process_phrase = (
        "1 fresh native process" if fork_count == 1 else f"{fork_count} fresh native processes"
    )
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
        headline_source = "the result"
    else:
        variation_sentence = f"The largest sample coefficient of variation was {max_cv:.2f}%."
        headline_source = "the median"
    measurement_summary = (
        f"Each headline is {headline_source} from {process_phrase} after a {warmup_phrase} and a "
        f"{measure_phrase}. All {len(libraries)} configurations processed the same 256 rotating "
        f"object graphs and emitted identical JSON bytes (average payload {payload:.1f} bytes). "
        f"{variation_sentence}"
    )

    baseline_names = {
        "jackson-generated": "build-time-generated Jackson",
        "jackson": "ordinary Jackson Databind",
    }
    result_sentences = []
    for baseline in baselines:
        ratios = [
            comparison_lookup[(operation, baseline)][
                "fory_to_baseline_median_throughput_ratio"
            ]
            for operation in operations
        ]
        result_sentences.append(baseline_summary(baseline_names[baseline], ratios))
    if "jackson-generated" in libraries and "jackson" in libraries:
        generated_to_ordinary = [
            lookup[(operation, "jackson-generated")]["median_ops_per_second"]
            / lookup[(operation, "jackson")]["median_ops_per_second"]
            for operation in operations
        ]
        result_sentences.append(
            "Build-time-generated Jackson ranged from "
            f"{min(generated_to_ordinary):.2f}× to {max(generated_to_ordinary):.2f}× ordinary "
            "Jackson Databind."
        )

    if "jackson-generated" in libraries and "jackson" in libraries:
        title = (
            "# GraalVM Native Image JSON performance: Fory JSON vs. ordinary and "
            "build-time-generated Jackson"
        )
    else:
        title = f"# GraalVM Native Image JSON performance: Fory JSON vs. {LIBRARY_LABELS[baselines[0]]}"

    measurement_bullets = [
        f"- **{OPERATION_LABELS.get(operation, operation)}:** "
        f"{OPERATION_DESCRIPTIONS[operation]}"
        for operation in operations
    ]
    lines = [
        title,
        "",
        "## Technical summary",
        "",
        " ".join(result_sentences),
        "",
        measurement_summary,
        "",
        "This is a direct JSON codec comparison, not an HTTP benchmark. The Jackson cases are "
        "reported separately: ordinary Databind with Native Image reflection metadata, and the "
        "serializer/deserializer classes generated by Quarkus at build time.",
        "",
        "## Median native throughput",
        "",
        "Longer bars are faster. Bars show median completed operations per second, and whiskers "
        "show the full min–max spread across independent native processes.",
        "",
        "![Native Image JSON throughput](throughput.svg)",
        "",
    ]

    if "jackson-generated" in libraries and "jackson" in libraries:
        lines.extend(
            [
                "| Operation | Fory JSON | Jackson generated | Jackson ordinary | Fory / generated | Fory / ordinary | Generated / ordinary |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for operation in operations:
            fory = lookup[(operation, "fory-json")]
            generated = lookup[(operation, "jackson-generated")]
            ordinary = lookup[(operation, "jackson")]
            lines.append(
                f"| {OPERATION_LABELS.get(operation, operation)} "
                f"| {format_ops(fory['median_ops_per_second'])} "
                f"| {format_ops(generated['median_ops_per_second'])} "
                f"| {format_ops(ordinary['median_ops_per_second'])} "
                f"| {comparison_lookup[(operation, 'jackson-generated')]['fory_to_baseline_median_throughput_ratio']:.2f}× "
                f"| {comparison_lookup[(operation, 'jackson')]['fory_to_baseline_median_throughput_ratio']:.2f}× "
                f"| {generated['median_ops_per_second'] / ordinary['median_ops_per_second']:.2f}× |"
            )
    else:
        baseline = baselines[0]
        lines.extend(
            [
                f"| Operation | Fory JSON | {LIBRARY_LABELS[baseline]} | Fory / baseline |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for operation in operations:
            lines.append(
                f"| {OPERATION_LABELS.get(operation, operation)} "
                f"| {format_ops(lookup[(operation, 'fory-json')]['median_ops_per_second'])} "
                f"| {format_ops(lookup[(operation, baseline)]['median_ops_per_second'])} "
                f"| {comparison_lookup[(operation, baseline)]['fory_to_baseline_median_throughput_ratio']:.2f}× |"
            )

    range_headers = [
        f"{LIBRARY_LABELS[library]} min–max (CV)" for library in libraries
    ]
    lines.extend(
        [
            "",
            "| Operation | " + " | ".join(range_headers) + " |",
            "| --- | " + " | ".join("---:" for _ in libraries) + " |",
        ]
    )
    for operation in operations:
        ranges = [
            format_variation(lookup[(operation, library)], fork_count)
            for library in libraries
        ]
        lines.append(
            f"| {OPERATION_LABELS.get(operation, operation)} | " + " | ".join(ranges) + " |"
        )

    lines.extend(
        [
            "",
            "## Relative throughput",
            "",
            "Each bar divides Fory JSON's median throughput by the named Jackson baseline. The "
            "whiskers and table pair samples with the same fork number to expose the full paired "
            "ratio range; 1.0× means equal throughput.",
            "",
            "![Fory JSON throughput relative to Jackson](relative-throughput.svg)",
            "",
            "| Operation | Baseline | Ratio of medians | Median paired ratio | Paired min–max |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for operation in operations:
        for baseline in baselines:
            comparison = comparison_lookup[(operation, baseline)]
            lines.append(
                f"| {OPERATION_LABELS.get(operation, operation)} "
                f"| {LIBRARY_LABELS[baseline]} "
                f"| {comparison['fory_to_baseline_median_throughput_ratio']:.2f}× "
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
            "inherited person fields, an address, two children, two credit cards, and income. The "
            "harness rotates through 256 deterministic variations.",
            "",
            *measurement_bullets,
            "",
            "Throughput is completed operations divided by measured nanoseconds inside each native "
            "process. Serialization consumes output length and a byte or character; deserialization "
            "computes a fingerprint over the decoded graph. The same checksum paths prevent dead-code "
            "elimination in every configuration.",
            "",
            "## Build-time integration and benchmark method",
            "",
            f"Fory JSON {dependencies['fory_json']} and both Jackson configurations using Jackson "
            f"Databind {dependencies['jackson_databind']} were compiled into separate native "
            "executables with the same GraalVM toolchain, `-O3`, and fallback disabled. Separate "
            "images keep each configuration's code and metadata isolated.",
            "",
            "Fory registers mapping mix-ins and exposes its field-based configuration through a "
            "reachable `@ForyJsonProvider`, allowing its Native Image feature to generate object "
            "codecs at image build time. The single-threaded configuration uses a concurrency level "
            "of one and disables asynchronous compilation.",
        ]
    )
    if "jackson" in libraries:
        lines.extend(
            [
                "",
                "Ordinary Jackson uses a field-only `ObjectMapper`, explicit property-order mix-ins, "
                "and Native Image reflection metadata for the four model classes.",
            ]
        )
    if "jackson-generated" in libraries:
        generated_verification = verification_result(records, "jackson-generated")
        if generated_verification is None:
            raise ValueError("missing generated Jackson verification record")
        serializer = generated_verification.get("serialization_implementation")
        deserializer = generated_verification.get("deserialization_implementation")
        lines.extend(
            [
                "",
                f"The generated case uses Quarkus {dependencies.get('quarkus')} and its current "
                "[reflection-free Jackson integration](https://quarkus.io/guides/rest#reflection-free-jackson-serialization-and-deserialization). "
                "A REST resource exposes `Customer` as both a response and request type so Quarkus "
                "discovers the model during augmentation. The timed path then calls the injected "
                "`ObjectMapper` directly; it does not send HTTP requests.",
                "",
                "Native verification proved that Jackson selected "
                f"`{serializer}` for serialization and `{deserializer}` for deserialization. These "
                "are Quarkus-generated implementations, not handwritten benchmark serializers.",
            ]
        )
    lines.extend(
        [
            "",
            f"For each operation, the runner launched {process_phrase} and rotated all configurations "
            "through deterministic process-order permutations. Each process initialized its mapper, "
            "prepared and verified fixtures, and—where applicable—started Quarkus before the timed "
            f"region. It then used a {warmup_phrase} and a {measure_phrase} in batches of "
            f"{benchmark['batch_size']}. JVM tests check all 256 round trips and exact String and UTF-8 "
            "output equality. Native verification requires the same serialized-payload hash from every "
            "executable before timing begins.",
            "",
            "## Executable size and peak process memory",
            "",
            "Executable size is the final file size. Peak resident set size (RSS) is the operating "
            "system's high-water mark for each complete process, including initialization, fixture "
            "preparation, and measurement; it is not an allocation-rate measurement.",
            "",
            "| Configuration | Native executable |",
            "| --- | ---: |",
        ]
    )
    for library in libraries:
        lines.append(
            f"| {LIBRARY_LABELS[library]} | {format_bytes(environment['binaries'][library]['size_bytes'])} |"
        )
    rss_headers = [f"{LIBRARY_LABELS[library]} median peak RSS" for library in libraries]
    lines.extend(
        [
            "",
            "| Operation | " + " | ".join(rss_headers) + " |",
            "| --- | " + " | ".join("---:" for _ in libraries) + " |",
        ]
    )
    for operation in operations:
        rss_values = [
            format_bytes(lookup[(operation, library)]["median_peak_rss_bytes"])
            for library in libraries
        ]
        lines.append(
            f"| {OPERATION_LABELS.get(operation, operation)} | "
            + " | ".join(rss_values)
            + " |"
        )
    if "jackson-generated" in libraries:
        lines.extend(
            [
                "",
                "The generated Jackson executable and its whole-process RSS include the Quarkus "
                "runtime. Those two deployment-container measurements are therefore not codec-only "
                "size or memory comparisons with the standalone executables.",
            ]
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
            f"| Maven | {first_line(environment['toolchain']['maven'])} |",
            f"| Fory JSON | {dependencies['fory_json']} |",
            f"| Jackson Databind | {dependencies['jackson_databind']} |",
        ]
    )
    if "jackson-generated" in libraries:
        lines.append(f"| Quarkus | {dependencies.get('quarkus')} |")
    lines.extend(
        [
            f"| Repository commit | `{repository['commit']}`{commit_suffix} |",
            "",
            "## Limits and robustness",
            "",
            "- These results describe one model, payload size, machine, Native Image version, and "
            "configuration. They do not establish a universal multiplier.",
            "- The harness measures single-threaded, steady-state codec throughput after warmup. It "
            "does not measure cold startup, first-request latency, HTTP routing, sockets, concurrent "
            "requests, garbage-collection pauses, or allocation rate.",
            *(
                [
                    "- The generated Jackson timing includes direct codec calls only; its binary size and RSS "
                    "include the surrounding Quarkus runtime."
                ]
                if "jackson-generated" in libraries
                else []
            ),
            "- Min–max ranges, sample standard deviation, paired ratios, commands, stdout, stderr, and "
            "peak RSS readings are retained in the saved artifacts.",
            "",
            "## Recommended next steps",
            "",
            "1. Repeat the committed harness on the deployment CPU and GraalVM release used in production.",
            "2. Add representative application models and payload distributions before choosing a framework.",
            "3. Use an end-to-end service benchmark when the decision depends on request throughput rather "
            "than JSON codec cost alone.",
            "",
            "## Reproduce the run",
            "",
            "Build and verify all native executables:",
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
    libraries = selected_libraries(environment)
    baselines = [library for library in libraries if library != "fory-json"]
    generated_present = "jackson-generated" in libraries
    relative_scope = (
        "both Jackson configurations" if len(baselines) > 1 else "Jackson"
    )
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
        libraries,
        int(environment["benchmark"]["forks"]),
    )
    render_speedup_svg(
        output / "relative-throughput.svg", comparisons, operations, baselines
    )
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
                "palette": "orange for Fory; blue for Jackson, with a hatch distinguishing ordinary Databind",
                "artifact": "throughput.svg",
            },
            {
                "section": f"Fory JSON throughput relative to {relative_scope}",
                "question": "What is Fory JSON throughput relative to each Jackson configuration by operation?",
                "family": "comparison and benchmark",
                "type": "grouped horizontal ratio bars with paired min-max whiskers and a 1.0x reference",
                "fields": [
                    "operation",
                    "baseline",
                    "fory_to_baseline_median_throughput_ratio",
                    "min_paired_ratio",
                    "max_paired_ratio",
                ],
                "palette": "single orange root with a hatch distinguishing the denominator",
                "artifact": "relative-throughput.svg",
            },
        ],
        "omitted_visuals": [
            {
                "topic": "native executable size and peak RSS",
                "reason": (
                    "Exact lookup is more useful, and the Quarkus application container makes size and RSS structurally different from codec-only throughput."
                    if generated_present
                    else "Exact lookup is more useful than an additional chart for two configurations."
                ),
            }
        ],
        "ratio_definition": "Fory median operations/s divided by the named Jackson configuration's median operations/s",
        "primary_metric": "median operations per second across independent native processes",
    }
    (output / "report-notes.json").write_text(
        json.dumps(notes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "report.md").write_text(
        report_markdown(environment, records, aggregates, comparisons), encoding="utf-8"
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
