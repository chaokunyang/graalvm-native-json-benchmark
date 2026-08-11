/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.fory;

import org.apache.fory.json.ForyJson;
import org.apache.fory.json.annotation.ForyJsonProvider;

/** Supplies the exact runtime configuration to Fory's Native Image build-time feature. */
@ForyJsonProvider
public final class BenchmarkJsonProvider {
  private final ForyJson json;

  public BenchmarkJsonProvider() {
    json =
        ForyJson.builder()
            .withFieldMode(true)
            .withConcurrencyLevel(1)
            .withAsyncCompilation(false)
            .registerMixin(BenchmarkJsonMixins.CustomerMixin.class)
            .registerMixin(BenchmarkJsonMixins.PersonMixin.class)
            .registerMixin(BenchmarkJsonMixins.AddressMixin.class)
            .registerMixin(BenchmarkJsonMixins.CreditCardMixin.class)
            .build();
  }

  public ForyJson json() {
    return json;
  }
}
