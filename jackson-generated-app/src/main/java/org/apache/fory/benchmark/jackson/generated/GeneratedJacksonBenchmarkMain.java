/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson.generated;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkus.runtime.Quarkus;
import io.quarkus.runtime.QuarkusApplication;
import io.quarkus.runtime.annotations.QuarkusMain;
import jakarta.inject.Inject;
import org.apache.fory.benchmark.core.BenchmarkRunner;

@QuarkusMain
public final class GeneratedJacksonBenchmarkMain {
  public static void main(String[] args) {
    Quarkus.run(BenchmarkApplication.class, args);
  }

  public static final class BenchmarkApplication implements QuarkusApplication {
    @Inject ObjectMapper mapper;

    @Override
    public int run(String... args) {
      BenchmarkRunner.run(new GeneratedJacksonJsonAdapter(mapper), args);
      return 0;
    }
  }
}
