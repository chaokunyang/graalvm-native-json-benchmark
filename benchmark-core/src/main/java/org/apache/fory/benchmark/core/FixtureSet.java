/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.core;

import java.util.ArrayList;
import java.util.List;
import org.apache.fory.benchmark.model.Address;
import org.apache.fory.benchmark.model.CreditCard;
import org.apache.fory.benchmark.model.Customer;
import org.apache.fory.benchmark.model.Person;

/** Deterministic rotating inputs that prevent one constant object from defining the workload. */
public final class FixtureSet {
  public static final int DEFAULT_COUNT = 256;

  private final Customer[] customers;

  private FixtureSet(Customer[] customers) {
    this.customers = customers;
  }

  public static FixtureSet createDefault() {
    Customer[] customers = new Customer[DEFAULT_COUNT];
    for (int i = 0; i < customers.length; i++) {
      List<Person> children = new ArrayList<>(2);
      children.add(new Person(9 + i % 5, "Sofia-" + i, "Fusco-" + i % 17));
      children.add(new Person(6 + i % 7, "Marilena-" + i, "Fusco-" + i % 17));
      customers[i] =
          new Customer(
              35 + i % 40,
              "Mario-" + i,
              "Fusco-" + i % 17,
              new Address("viale Michelangelo " + (10 + i), "Mondragone-" + i % 11),
              children,
              new CreditCard[] {
                new CreditCard(100 + i % 50, "Visa-" + i % 7),
                new CreditCard(150 + i % 70, "Amex-" + i % 5)
              },
              42_000.5 + i * 17.25);
    }
    return new FixtureSet(customers);
  }

  public int size() {
    return customers.length;
  }

  public Customer get(int index) {
    return customers[index];
  }
}
