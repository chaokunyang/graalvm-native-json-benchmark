/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.function.LongUnaryOperator;
import org.apache.fory.benchmark.model.Customer;

/** Prepares library-specific JSON inputs outside the timed region. */
public final class PreparedWorkload {
  private final JsonAdapter adapter;
  private final FixtureSet fixtures;
  private final String[] strings;
  private final byte[][] utf8;
  private final int mask;
  private final double averagePayloadBytes;
  private final long payloadHash;

  public PreparedWorkload(JsonAdapter adapter, FixtureSet fixtures) {
    this.adapter = adapter;
    this.fixtures = fixtures;
    if (Integer.bitCount(fixtures.size()) != 1) {
      throw new IllegalArgumentException("Fixture count must be a power of two");
    }
    this.mask = fixtures.size() - 1;
    this.strings = new String[fixtures.size()];
    this.utf8 = new byte[fixtures.size()][];
    long totalBytes = 0;
    long hash = 0xcbf29ce484222325L;
    for (int i = 0; i < fixtures.size(); i++) {
      Customer customer = fixtures.get(i);
      strings[i] = adapter.toJson(customer);
      utf8[i] = adapter.toJsonBytes(customer);
      totalBytes += utf8[i].length;
      byte[] stringUtf8 = strings[i].getBytes(StandardCharsets.UTF_8);
      if (!Arrays.equals(stringUtf8, utf8[i])) {
        throw new IllegalStateException(adapter.name() + " emitted different String and UTF-8 JSON");
      }
      for (byte value : utf8[i]) {
        hash ^= value & 0xffL;
        hash *= 0x100000001b3L;
      }
      hash ^= utf8[i].length;
      hash *= 0x100000001b3L;
      String utf8Text = new String(stringUtf8, StandardCharsets.UTF_8);
      if (!adapter.fromJson(strings[i]).equals(customer)
          || !adapter.fromJsonBytes(utf8[i]).equals(customer)
          || !adapter.fromJson(utf8Text).equals(customer)) {
        throw new IllegalStateException(adapter.name() + " failed fixture round-trip at " + i);
      }
    }
    averagePayloadBytes = (double) totalBytes / fixtures.size();
    payloadHash = hash;
  }

  public LongUnaryOperator task(BenchmarkOperation operation) {
    return switch (operation) {
      case STRING_SERIALIZE -> this::serializeString;
      case STRING_DESERIALIZE -> this::deserializeString;
      case UTF8_SERIALIZE -> this::serializeUtf8;
      case UTF8_DESERIALIZE -> this::deserializeUtf8;
    };
  }

  private long serializeString(long sequence) {
    String json = adapter.toJson(fixtures.get((int) sequence & mask));
    return 31L * json.length() + json.charAt(json.length() - 1);
  }

  private long deserializeString(long sequence) {
    Customer value = adapter.fromJson(strings[(int) sequence & mask]);
    return value.fingerprint();
  }

  private long serializeUtf8(long sequence) {
    byte[] json = adapter.toJsonBytes(fixtures.get((int) sequence & mask));
    return 31L * json.length + (json[json.length - 1] & 0xffL);
  }

  private long deserializeUtf8(long sequence) {
    Customer value = adapter.fromJsonBytes(utf8[(int) sequence & mask]);
    return value.fingerprint();
  }

  public double averagePayloadBytes() {
    return averagePayloadBytes;
  }

  public String payloadHash() {
    return String.format("%016x", payloadHash);
  }

  public String stringAt(int index) {
    return strings[index];
  }

  public byte[] utf8At(int index) {
    return utf8[index];
  }
}
