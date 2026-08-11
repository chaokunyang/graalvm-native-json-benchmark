/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import java.util.LinkedHashMap;
import java.util.Map;

public final class BenchmarkOptions {
  private final BenchmarkOperation operation;
  private final int warmupSeconds;
  private final int measureSeconds;
  private final int batchSize;
  private final boolean verifyOnly;

  private BenchmarkOptions(
      BenchmarkOperation operation,
      int warmupSeconds,
      int measureSeconds,
      int batchSize,
      boolean verifyOnly) {
    this.operation = operation;
    this.warmupSeconds = warmupSeconds;
    this.measureSeconds = measureSeconds;
    this.batchSize = batchSize;
    this.verifyOnly = verifyOnly;
  }

  public static BenchmarkOptions parse(String[] args) {
    Map<String, String> values = new LinkedHashMap<>();
    boolean verify = false;
    for (int i = 0; i < args.length; i++) {
      String arg = args[i];
      if (arg.equals("--verify")) {
        verify = true;
        continue;
      }
      if (arg.equals("--help")) {
        throw new HelpRequested();
      }
      if (!arg.startsWith("--")) {
        throw new IllegalArgumentException("Expected an option, got: " + arg);
      }
      int equals = arg.indexOf('=');
      if (equals > 2) {
        values.put(arg.substring(2, equals), arg.substring(equals + 1));
      } else {
        if (i + 1 >= args.length || args[i + 1].startsWith("--")) {
          throw new IllegalArgumentException("Missing value for " + arg);
        }
        values.put(arg.substring(2), args[++i]);
      }
    }

    BenchmarkOperation operation =
        BenchmarkOperation.parse(values.getOrDefault("operation", "utf8-serialize"));
    int warmup = positive(values, "warmup-seconds", 3);
    int measure = positive(values, "measure-seconds", 5);
    int batch = positive(values, "batch-size", 64);
    for (String key : values.keySet()) {
      if (!key.equals("operation")
          && !key.equals("warmup-seconds")
          && !key.equals("measure-seconds")
          && !key.equals("batch-size")) {
        throw new IllegalArgumentException("Unknown option: --" + key);
      }
    }
    return new BenchmarkOptions(operation, warmup, measure, batch, verify);
  }

  private static int positive(Map<String, String> values, String key, int defaultValue) {
    int value = Integer.parseInt(values.getOrDefault(key, Integer.toString(defaultValue)));
    if (value <= 0) {
      throw new IllegalArgumentException("--" + key + " must be positive");
    }
    return value;
  }

  public BenchmarkOperation operation() {
    return operation;
  }

  public int warmupSeconds() {
    return warmupSeconds;
  }

  public int measureSeconds() {
    return measureSeconds;
  }

  public int batchSize() {
    return batchSize;
  }

  public boolean verifyOnly() {
    return verifyOnly;
  }

  public static String usage() {
    return "Usage: --operation <string-serialize|string-deserialize|utf8-serialize|utf8-deserialize> "
        + "[--warmup-seconds N] [--measure-seconds N] [--batch-size N] [--verify]";
  }

  public static final class HelpRequested extends RuntimeException {}
}
