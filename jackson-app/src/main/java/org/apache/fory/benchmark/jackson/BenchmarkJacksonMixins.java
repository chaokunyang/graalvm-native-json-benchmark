/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson;

import com.fasterxml.jackson.annotation.JsonPropertyOrder;

/** Keeps the conventional Jackson output identical to the generated Jackson output. */
public final class BenchmarkJacksonMixins {
  private BenchmarkJacksonMixins() {}

  @JsonPropertyOrder({
    "address", "children", "creditCards", "income", "age", "firstName", "lastName"
  })
  public abstract static class CustomerMixin {}

  @JsonPropertyOrder({"age", "firstName", "lastName"})
  public abstract static class PersonMixin {}

  @JsonPropertyOrder({"street", "town"})
  public abstract static class AddressMixin {}

  @JsonPropertyOrder({"limit", "name"})
  public abstract static class CreditCardMixin {}
}
