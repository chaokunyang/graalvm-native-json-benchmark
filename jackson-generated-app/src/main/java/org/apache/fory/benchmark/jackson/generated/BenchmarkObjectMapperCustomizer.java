/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson.generated;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.JsonPropertyOrder;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkus.jackson.ObjectMapperCustomizer;
import jakarta.inject.Singleton;
import org.apache.fory.benchmark.model.Address;
import org.apache.fory.benchmark.model.CreditCard;
import org.apache.fory.benchmark.model.Customer;
import org.apache.fory.benchmark.model.Person;

@Singleton
public final class BenchmarkObjectMapperCustomizer implements ObjectMapperCustomizer {
  @Override
  public void customize(ObjectMapper mapper) {
    mapper.setVisibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.NONE);
    mapper.setVisibility(PropertyAccessor.FIELD, JsonAutoDetect.Visibility.ANY);
    mapper.addMixIn(Customer.class, CustomerMixin.class);
    mapper.addMixIn(Person.class, PersonMixin.class);
    mapper.addMixIn(Address.class, AddressMixin.class);
    mapper.addMixIn(CreditCard.class, CreditCardMixin.class);
  }

  @JsonPropertyOrder({
    "address", "children", "creditCards", "income", "age", "firstName", "lastName"
  })
  abstract static class CustomerMixin {}

  @JsonPropertyOrder({"age", "firstName", "lastName"})
  abstract static class PersonMixin {}

  @JsonPropertyOrder({"street", "town"})
  abstract static class AddressMixin {}

  @JsonPropertyOrder({"limit", "name"})
  abstract static class CreditCardMixin {}
}
