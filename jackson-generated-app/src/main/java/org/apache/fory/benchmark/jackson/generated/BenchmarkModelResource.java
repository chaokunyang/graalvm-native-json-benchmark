/* Licensed under the Apache License, Version 2.0. See LICENSE for details. */
package org.apache.fory.benchmark.jackson.generated;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import org.apache.fory.benchmark.core.FixtureSet;
import org.apache.fory.benchmark.model.Customer;

/** Gives the Quarkus build step concrete serialization and deserialization roots. */
@Path("/benchmark-model")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public final class BenchmarkModelResource {
  @GET
  public Customer get() {
    return FixtureSet.createDefault().get(0);
  }

  @POST
  public Customer echo(Customer value) {
    return value;
  }
}
