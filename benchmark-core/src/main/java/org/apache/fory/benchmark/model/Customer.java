/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.model;

import java.util.Arrays;
import java.util.List;
import java.util.Objects;

public final class Customer extends Person {
  public Address address;
  public List<Person> children;
  public CreditCard[] creditCards;
  public double income;

  public Customer() {}

  public Customer(
      int age,
      String firstName,
      String lastName,
      Address address,
      List<Person> children,
      CreditCard[] creditCards,
      double income) {
    super(age, firstName, lastName);
    this.address = address;
    this.children = children;
    this.creditCards = creditCards;
    this.income = income;
  }

  @Override
  public long fingerprint() {
    long value = super.fingerprint();
    value = value * 31 + (address == null ? 0 : address.fingerprint());
    if (children != null) {
      for (Person child : children) {
        value = value * 31 + child.fingerprint();
      }
    }
    if (creditCards != null) {
      for (CreditCard card : creditCards) {
        value = value * 31 + card.fingerprint();
      }
    }
    return value * 31 + Double.doubleToLongBits(income);
  }

  @Override
  public boolean equals(Object other) {
    if (this == other) {
      return true;
    }
    if (!(other instanceof Customer customer) || !super.equals(other)) {
      return false;
    }
    return Double.compare(income, customer.income) == 0
        && Objects.equals(address, customer.address)
        && Objects.equals(children, customer.children)
        && Arrays.equals(creditCards, customer.creditCards);
  }

  @Override
  public int hashCode() {
    int result = Objects.hash(super.hashCode(), address, children, income);
    return 31 * result + Arrays.hashCode(creditCards);
  }
}
