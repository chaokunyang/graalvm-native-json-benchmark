/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.fory;

import org.apache.fory.benchmark.core.BenchmarkRunner;

public final class ForyBenchmarkMain {
  private ForyBenchmarkMain() {}

  public static void main(String[] args) {
    BenchmarkRunner.run(new ForyJsonAdapter(), args);
  }
}
