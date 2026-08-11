/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import org.apache.fory.benchmark.model.Customer;

/** Minimal common surface measured for each JSON implementation. */
public interface JsonAdapter {
  String name();

  String toJson(Customer value);

  byte[] toJsonBytes(Customer value);

  Customer fromJson(String json);

  Customer fromJsonBytes(byte[] json);
}
