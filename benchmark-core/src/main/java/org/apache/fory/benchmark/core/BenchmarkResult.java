/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import java.util.Locale;

public record BenchmarkResult(
    String library,
    String runtime,
    BenchmarkOperation operation,
    int warmupSeconds,
    int measureSeconds,
    int batchSize,
    int fixtureCount,
    long operations,
    long elapsedNanos,
    double averagePayloadBytes,
    long checksum) {

  public double operationsPerSecond() {
    return operations * 1_000_000_000.0 / elapsedNanos;
  }

  public double nanosPerOperation() {
    return (double) elapsedNanos / operations;
  }

  public String toJson() {
    return String.format(
        Locale.ROOT,
        "{\"status\":\"ok\",\"library\":\"%s\",\"runtime\":\"%s\","
            + "\"operation\":\"%s\",\"warmup_seconds\":%d,\"measure_seconds\":%d,"
            + "\"batch_size\":%d,\"fixture_count\":%d,\"operations\":%d,"
            + "\"elapsed_ns\":%d,\"ops_per_second\":%.6f,\"ns_per_operation\":%.6f,"
            + "\"average_payload_bytes\":%.3f,\"checksum\":%d}",
        library,
        runtime,
        operation.id(),
        warmupSeconds,
        measureSeconds,
        batchSize,
        fixtureCount,
        operations,
        elapsedNanos,
        operationsPerSecond(),
        nanosPerOperation(),
        averagePayloadBytes,
        checksum);
  }
}
