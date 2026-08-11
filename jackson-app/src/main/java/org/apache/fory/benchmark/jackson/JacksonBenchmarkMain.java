/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson;

import org.apache.fory.benchmark.core.BenchmarkRunner;

public final class JacksonBenchmarkMain {
  private JacksonBenchmarkMain() {}

  public static void main(String[] args) {
    BenchmarkRunner.run(new JacksonJsonAdapter(), args);
  }
}
