/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import java.util.Locale;
import java.util.function.LongUnaryOperator;

/** Time-based single-thread benchmark runner shared by all native executables. */
public final class BenchmarkRunner {
  private static volatile long blackhole;

  private BenchmarkRunner() {}

  public static void run(JsonAdapter adapter, String[] args) {
    BenchmarkOptions options;
    try {
      options = BenchmarkOptions.parse(args);
    } catch (BenchmarkOptions.HelpRequested ignored) {
      System.out.println(BenchmarkOptions.usage());
      return;
    }

    FixtureSet fixtures = FixtureSet.createDefault();
    PreparedWorkload workload = new PreparedWorkload(adapter, fixtures);
    if (options.verifyOnly()) {
      System.out.printf(
          Locale.ROOT,
          "{\"status\":\"ok\",\"library\":\"%s\",\"runtime\":\"%s\","
              + "\"verified_fixtures\":%d,\"average_payload_bytes\":%.3f,"
              + "\"payload_hash\":\"%s\","
              + "\"serialization_implementation\":\"%s\","
              + "\"deserialization_implementation\":\"%s\"}%n",
          adapter.name(),
          runtime(),
          fixtures.size(),
          workload.averagePayloadBytes(),
          workload.payloadHash(),
          adapter.serializationImplementation(),
          adapter.deserializationImplementation());
      return;
    }

    LongUnaryOperator task = workload.task(options.operation());
    runWindow(task, options.warmupSeconds(), options.batchSize(), 0);

    long start = System.nanoTime();
    WindowResult measured =
        runWindow(task, options.measureSeconds(), options.batchSize(), start);
    BenchmarkResult result =
        new BenchmarkResult(
            adapter.name(),
            runtime(),
            options.operation(),
            options.warmupSeconds(),
            options.measureSeconds(),
            options.batchSize(),
            fixtures.size(),
            measured.operations(),
            measured.elapsedNanos(),
            workload.averagePayloadBytes(),
            measured.checksum());
    System.out.println(result.toJson());
  }

  private static WindowResult runWindow(
      LongUnaryOperator task, int durationSeconds, int batchSize, long suppliedStart) {
    long start = suppliedStart == 0 ? System.nanoTime() : suppliedStart;
    long deadline = start + durationSeconds * 1_000_000_000L;
    long operations = 0;
    long checksum = blackhole;
    do {
      for (int i = 0; i < batchSize; i++) {
        checksum = Long.rotateLeft(checksum, 7) ^ task.applyAsLong(operations + i);
      }
      operations += batchSize;
    } while (System.nanoTime() < deadline);
    long elapsed = System.nanoTime() - start;
    blackhole = checksum;
    return new WindowResult(operations, elapsed, checksum);
  }

  private static String runtime() {
    return System.getProperty("org.graalvm.nativeimage.imagecode") == null ? "jvm" : "native";
  }

  private record WindowResult(long operations, long elapsedNanos, long checksum) {}
}
