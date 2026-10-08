# Synthetic min-interval fixture (not a DDR5 specification)

This deliberately small specification tests the event/evidence infrastructure.
Its numeric threshold MUST NOT be interpreted as DDR5 tMRD or another JEDEC value.

For each (channel, subchannel, rank), a valid START command records a timestamp
in integer nanosecond ticks. A valid END command with existing START history
must occur at least 4 ticks after the latest valid START. Measure before updating
history when a command is configured as both a start and end. An END does not
consume the history. Classify a distance of 4 as at_bound, greater as above_bound,
and less as a violation. No history means no sample.

A reset event or a change in config_epoch/reset_epoch clears that scope's history.
An invalid observation also clears it conservatively because the actual command
is unknown. Timestamps must increase strictly within a scope; epochs must not
regress. Independent scopes can share a timestamp. Identical repeated event IDs
are ignored; conflicting repeated IDs are rejected.

These fixtures have no DUT, simulator, native coverage database or independent
checker. Replay counts demonstrate the software plumbing, never verified coverage.
