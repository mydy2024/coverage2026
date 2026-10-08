`timescale 1ps/1fs

// Provisional bridge from a decoded monitor event stream to the collector.
// Replace only this adapter when the real TB/monitor interface is available.
module ddr5_vref_adapter_template (
  input logic monitor_clock,
  input logic event_strobe,
  input longint unsigned event_timestamp_fs,
  input int unsigned event_channel,
  input int unsigned event_subchannel,
  input int unsigned event_rank,
  input longint unsigned event_config_epoch,
  input longint unsigned event_reset_epoch,
  input longint unsigned event_tck_fs,
  input logic event_is_reset,
  input logic event_command_valid,
  input ddr5_vref_cov_pkg::ddr5_vref_cmd_e event_command,
  ddr5_vref_cov_if coverage
);

  // The monitor must emit at most one event per strobe. If multiple semantic
  // events can occur on one clock, serialize them in the real adapter.
  always @(posedge monitor_clock) begin
    if (event_strobe) begin
      coverage.observe(
        event_timestamp_fs,
        event_channel,
        event_subchannel,
        event_rank,
        event_config_epoch,
        event_reset_epoch,
        event_tck_fs,
        event_is_reset,
        event_command_valid,
        event_command
      );
    end
  end

endmodule
