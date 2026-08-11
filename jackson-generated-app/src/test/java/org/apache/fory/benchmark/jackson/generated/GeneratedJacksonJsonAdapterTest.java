/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson.generated;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import org.apache.fory.benchmark.core.FixtureSet;
import org.apache.fory.benchmark.fory.ForyJsonAdapter;
import org.apache.fory.benchmark.jackson.JacksonJsonAdapter;
import org.apache.fory.benchmark.model.Customer;
import org.junit.jupiter.api.Test;

@QuarkusTest
class GeneratedJacksonJsonAdapterTest {
  @Inject ObjectMapper mapper;

  @Test
  void usesGeneratedCodeAndMatchesBothBaselines() {
    GeneratedJacksonJsonAdapter generated = new GeneratedJacksonJsonAdapter(mapper);
    ForyJsonAdapter fory = new ForyJsonAdapter();
    JacksonJsonAdapter jackson = new JacksonJsonAdapter();
    FixtureSet fixtures = FixtureSet.createDefault();

    assertTrue(
        generated.serializationImplementation().endsWith("$quarkusjacksonserializer"));
    assertTrue(
        generated.deserializationImplementation().endsWith("$quarkusjacksondeserializer"));
    for (int i = 0; i < fixtures.size(); i++) {
      Customer expected = fixtures.get(i);
      String json = generated.toJson(expected);
      byte[] utf8 = generated.toJsonBytes(expected);
      assertEquals(expected, generated.fromJson(json));
      assertEquals(expected, generated.fromJsonBytes(utf8));
      assertEquals(jackson.toJson(expected), json, "Jackson output differs at fixture " + i);
      assertEquals(fory.toJson(expected), json, "Fory output differs at fixture " + i);
      assertArrayEquals(
          jackson.toJsonBytes(expected), utf8, "UTF-8 output differs at fixture " + i);
      assertArrayEquals(fory.toJsonBytes(expected), utf8, "Fory UTF-8 differs at fixture " + i);
    }
  }
}
