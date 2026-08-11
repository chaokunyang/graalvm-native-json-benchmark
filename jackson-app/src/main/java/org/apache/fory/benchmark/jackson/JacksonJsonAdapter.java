/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;
import java.io.IOException;
import org.apache.fory.benchmark.core.JsonAdapter;
import org.apache.fory.benchmark.model.Customer;

public final class JacksonJsonAdapter implements JsonAdapter {
  private final ObjectMapper mapper;

  public JacksonJsonAdapter() {
    mapper =
        JsonMapper.builder()
            .visibility(PropertyAccessor.ALL, JsonAutoDetect.Visibility.NONE)
            .visibility(PropertyAccessor.FIELD, JsonAutoDetect.Visibility.ANY)
            .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
            .build();
  }

  @Override
  public String name() {
    return "jackson";
  }

  @Override
  public String toJson(Customer value) {
    try {
      return mapper.writeValueAsString(value);
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Jackson String serialization failed", error);
    }
  }

  @Override
  public byte[] toJsonBytes(Customer value) {
    try {
      return mapper.writeValueAsBytes(value);
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Jackson UTF-8 serialization failed", error);
    }
  }

  @Override
  public Customer fromJson(String text) {
    try {
      return mapper.readValue(text, Customer.class);
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Jackson String deserialization failed", error);
    }
  }

  @Override
  public Customer fromJsonBytes(byte[] bytes) {
    try {
      return mapper.readValue(bytes, Customer.class);
    } catch (IOException error) {
      throw new IllegalStateException("Jackson UTF-8 deserialization failed", error);
    }
  }
}
