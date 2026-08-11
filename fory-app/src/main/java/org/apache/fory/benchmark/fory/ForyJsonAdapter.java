/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.fory;

import org.apache.fory.benchmark.core.JsonAdapter;
import org.apache.fory.benchmark.model.Customer;
import org.apache.fory.json.ForyJson;

public final class ForyJsonAdapter implements JsonAdapter {
  private final ForyJson json;

  public ForyJsonAdapter() {
    json = new BenchmarkJsonProvider().json();
  }

  @Override
  public String name() {
    return "fory-json";
  }

  @Override
  public String toJson(Customer value) {
    return json.toJson(value);
  }

  @Override
  public byte[] toJsonBytes(Customer value) {
    return json.toJsonBytes(value);
  }

  @Override
  public Customer fromJson(String text) {
    return json.fromJson(text, Customer.class);
  }

  @Override
  public Customer fromJsonBytes(byte[] bytes) {
    return json.fromJson(bytes, Customer.class);
  }
}
