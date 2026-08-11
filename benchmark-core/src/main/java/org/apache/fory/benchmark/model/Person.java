/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.model;

import java.util.Objects;

/** Person portion of the Customer payload used by the Quarkus article. */
public class Person {
  public int age;
  public String firstName;
  public String lastName;

  public Person() {}

  public Person(int age, String firstName, String lastName) {
    this.age = age;
    this.firstName = firstName;
    this.lastName = lastName;
  }

  public long fingerprint() {
    long value = age;
    value = value * 31 + Objects.hashCode(firstName);
    return value * 31 + Objects.hashCode(lastName);
  }

  @Override
  public boolean equals(Object other) {
    if (this == other) {
      return true;
    }
    if (other == null || getClass() != other.getClass()) {
      return false;
    }
    Person person = (Person) other;
    return age == person.age
        && Objects.equals(firstName, person.firstName)
        && Objects.equals(lastName, person.lastName);
  }

  @Override
  public int hashCode() {
    return Objects.hash(age, firstName, lastName);
  }
}
