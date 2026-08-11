/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import java.util.Locale;

public enum BenchmarkOperation {
  STRING_SERIALIZE("string-serialize"),
  STRING_DESERIALIZE("string-deserialize"),
  UTF8_SERIALIZE("utf8-serialize"),
  UTF8_DESERIALIZE("utf8-deserialize");

  private final String id;

  BenchmarkOperation(String id) {
    this.id = id;
  }

  public String id() {
    return id;
  }

  public static BenchmarkOperation parse(String value) {
    String normalized = value.toLowerCase(Locale.ROOT).replace('_', '-');
    for (BenchmarkOperation operation : values()) {
      if (operation.id.equals(normalized)) {
        return operation;
      }
    }
    throw new IllegalArgumentException("Unknown operation: " + value);
  }
}
