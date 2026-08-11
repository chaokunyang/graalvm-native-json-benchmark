/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.model;

import java.util.Objects;

public final class CreditCard {
  public int limit;
  public String name;

  public CreditCard() {}

  public CreditCard(int limit, String name) {
    this.limit = limit;
    this.name = name;
  }

  public long fingerprint() {
    return 31L * limit + Objects.hashCode(name);
  }

  @Override
  public boolean equals(Object other) {
    if (this == other) {
      return true;
    }
    if (!(other instanceof CreditCard card)) {
      return false;
    }
    return limit == card.limit && Objects.equals(name, card.name);
  }

  @Override
  public int hashCode() {
    return Objects.hash(limit, name);
  }
}
