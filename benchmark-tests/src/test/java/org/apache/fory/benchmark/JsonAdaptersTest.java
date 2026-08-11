/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import org.apache.fory.benchmark.core.FixtureSet;
import org.apache.fory.benchmark.core.JsonAdapter;
import org.apache.fory.benchmark.fory.ForyJsonAdapter;
import org.apache.fory.benchmark.jackson.JacksonJsonAdapter;
import org.apache.fory.benchmark.model.Customer;
import org.junit.jupiter.api.Test;

class JsonAdaptersTest {
  private final ObjectMapper treeMapper = new ObjectMapper();

  @Test
  void bothAdaptersRoundTripAndProduceEquivalentJson() throws IOException {
    FixtureSet fixtures = FixtureSet.createDefault();
    JsonAdapter fory = new ForyJsonAdapter();
    JsonAdapter jackson = new JacksonJsonAdapter();

    for (int i = 0; i < fixtures.size(); i++) {
      Customer expected = fixtures.get(i);
      assertRoundTrip(fory, expected, i);
      assertRoundTrip(jackson, expected, i);

      JsonNode foryString = treeMapper.readTree(fory.toJson(expected));
      JsonNode jacksonString = treeMapper.readTree(jackson.toJson(expected));
      JsonNode foryUtf8 = treeMapper.readTree(fory.toJsonBytes(expected));
      JsonNode jacksonUtf8 = treeMapper.readTree(jackson.toJsonBytes(expected));
      assertEquals(jacksonString, foryString, "String JSON differs at fixture " + i);
      assertEquals(foryString, foryUtf8, "Fory representations differ at fixture " + i);
      assertEquals(jacksonString, jacksonUtf8, "Jackson representations differ at fixture " + i);
      assertEquals(
          jackson.toJson(expected),
          fory.toJson(expected),
          "Serialized String bytes differ at fixture " + i);
      assertArrayEquals(
          jackson.toJsonBytes(expected),
          fory.toJsonBytes(expected),
          "Serialized UTF-8 bytes differ at fixture " + i);
    }
  }

  private static void assertRoundTrip(JsonAdapter adapter, Customer expected, int fixture) {
    assertEquals(
        expected,
        adapter.fromJson(adapter.toJson(expected)),
        adapter.name() + " String round-trip failed at fixture " + fixture);
    assertEquals(
        expected,
        adapter.fromJsonBytes(adapter.toJsonBytes(expected)),
        adapter.name() + " UTF-8 round-trip failed at fixture " + fixture);
  }
}
