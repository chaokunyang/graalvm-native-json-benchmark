/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson.generated;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.deser.DefaultDeserializationContext;
import java.io.IOException;
import org.apache.fory.benchmark.core.JsonAdapter;
import org.apache.fory.benchmark.model.Customer;

public final class GeneratedJacksonJsonAdapter implements JsonAdapter {
  private static final String SERIALIZER_SUFFIX = "$quarkusjacksonserializer";
  private static final String DESERIALIZER_SUFFIX = "$quarkusjacksondeserializer";

  private final ObjectMapper mapper;
  private final String serializerImplementation;
  private final String deserializerImplementation;

  public GeneratedJacksonJsonAdapter(ObjectMapper mapper) {
    this.mapper = mapper;
    serializerImplementation = resolveSerializer(mapper);
    deserializerImplementation = resolveDeserializer(mapper);
    requireGenerated(serializerImplementation, SERIALIZER_SUFFIX);
    requireGenerated(deserializerImplementation, DESERIALIZER_SUFFIX);
  }

  private static String resolveSerializer(ObjectMapper mapper) {
    try {
      JsonSerializer<Object> serializer =
          mapper.getSerializerProviderInstance().findValueSerializer(Customer.class);
      return serializer.getClass().getName();
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Cannot resolve the Customer serializer", error);
    }
  }

  private static String resolveDeserializer(ObjectMapper mapper) {
    try {
      DefaultDeserializationContext context =
          ((DefaultDeserializationContext) mapper.getDeserializationContext())
              .createInstance(mapper.getDeserializationConfig(), null, null);
      JsonDeserializer<Object> deserializer =
          context.findRootValueDeserializer(mapper.constructType(Customer.class));
      return deserializer.getClass().getName();
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Cannot resolve the Customer deserializer", error);
    }
  }

  private static void requireGenerated(String implementation, String suffix) {
    if (!implementation.endsWith(suffix)) {
      throw new IllegalStateException(
          "Expected generated Jackson implementation, got " + implementation);
    }
  }

  @Override
  public String name() {
    return "jackson-generated";
  }

  @Override
  public String toJson(Customer value) {
    try {
      return mapper.writeValueAsString(value);
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Generated Jackson String serialization failed", error);
    }
  }

  @Override
  public byte[] toJsonBytes(Customer value) {
    try {
      return mapper.writeValueAsBytes(value);
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Generated Jackson UTF-8 serialization failed", error);
    }
  }

  @Override
  public Customer fromJson(String text) {
    try {
      return mapper.readValue(text, Customer.class);
    } catch (JsonProcessingException error) {
      throw new IllegalStateException("Generated Jackson String deserialization failed", error);
    }
  }

  @Override
  public Customer fromJsonBytes(byte[] bytes) {
    try {
      return mapper.readValue(bytes, Customer.class);
    } catch (IOException error) {
      throw new IllegalStateException("Generated Jackson UTF-8 deserialization failed", error);
    }
  }

  @Override
  public String serializationImplementation() {
    return serializerImplementation;
  }

  @Override
  public String deserializationImplementation() {
    return deserializerImplementation;
  }
}
