/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.model;

import java.util.Objects;

public final class Address {
  public String street;
  public String town;

  public Address() {}

  public Address(String street, String town) {
    this.street = street;
    this.town = town;
  }

  public long fingerprint() {
    return 31L * Objects.hashCode(street) + Objects.hashCode(town);
  }

  @Override
  public boolean equals(Object other) {
    if (this == other) {
      return true;
    }
    if (!(other instanceof Address address)) {
      return false;
    }
    return Objects.equals(street, address.street) && Objects.equals(town, address.town);
  }

  @Override
  public int hashCode() {
    return Objects.hash(street, town);
  }
}
