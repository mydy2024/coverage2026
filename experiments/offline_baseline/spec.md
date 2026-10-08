# Offline baseline protocol (not a DDR5 specification)

This specification defines the semantics of the offline baseline experiment
package. It is a testing protocol, not a hardware specification. Its numeric
thresholds are not DDR5 JEDEC values.

## Single-rule protocol

For each (channel, subchannel, rank), a valid START command records a timestamp
in integer nanosecond ticks. A valid END command with existing START history
must occur at least 4 ticks after the latest valid START. Measure before
updating history when a command is configured as both a start and end. An END
does not consume the history. Classify a distance of 4 as at_bound, greater as
above_bound, and less as a violation. No history means no sample.

## Dual-rule protocol

Two rules operate on the same scope dimensions:

- Rule A: START to END, minimum 4 ticks.
- Rule B: END to DONE, minimum 5 ticks.

An END event is both the end command for rule A and the start command for rule B.
Each rule evaluates independently using its own history. The "measure before
update" rule applies per rule: when END arrives, rule A measures START-to-END
using old history, then rule B latches END as its start.

## Self-overlap protocol

A single rule where START is configured as both start_command and an
end_command. When a START event arrives, it is first evaluated as an end
(against prior START history), then latched as a new start. The first START
in a scope has no prior history and is suppressed; subsequent STARTs measure
against the most recent prior START.

## Scope and epoch isolation

A reset event or a change in config_epoch/reset_epoch clears that scope's
history. An invalid observation also clears it conservatively because the
actual command is unknown. Timestamps must increase strictly within a scope;
epochs must not regress. Independent scopes can share a timestamp. Identical
repeated event IDs are ignored; conflicting repeated IDs are rejected.

## No sign-off

These fixtures have no DUT, simulator, native coverage database or independent
checker. Replay counts demonstrate the software plumbing, never verified
coverage.
