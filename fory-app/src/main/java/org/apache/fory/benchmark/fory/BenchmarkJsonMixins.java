/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.fory;

import org.apache.fory.benchmark.model.Address;
import org.apache.fory.benchmark.model.CreditCard;
import org.apache.fory.benchmark.model.Customer;
import org.apache.fory.benchmark.model.Person;
import org.apache.fory.json.annotation.JsonMixin;
import org.apache.fory.json.annotation.JsonPropertyOrder;

/** Selects the benchmark model for Fory JSON Native Image code generation. */
public final class BenchmarkJsonMixins {
  private BenchmarkJsonMixins() {}

  @JsonMixin(target = Customer.class)
  @JsonPropertyOrder({
    "address", "children", "creditCards", "income", "age", "firstName", "lastName"
  })
  public abstract static class CustomerMixin {}

  @JsonMixin(target = Person.class)
  @JsonPropertyOrder({"age", "firstName", "lastName"})
  public abstract static class PersonMixin {}

  @JsonMixin(target = Address.class)
  @JsonPropertyOrder({"street", "town"})
  public abstract static class AddressMixin {}

  @JsonMixin(target = CreditCard.class)
  @JsonPropertyOrder({"limit", "name"})
  public abstract static class CreditCardMixin {}
}
