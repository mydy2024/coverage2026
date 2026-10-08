`timescale 1ps/1fs

module ddr5_vref_smoke_tb;
  import ddr5_vref_cov_pkg::*;

  localparam longint unsigned TCK_FS = 1_000_000;
  localparam longint unsigned TMRD_FS = 16_000_000;

  ddr5_vref_cov_if #(
    .NUM_CHANNELS(1),
    .NUM_SUBCHANNELS(1),
    .NUM_RANKS(2),
    .TRACE_ENABLE(1'b0)
  ) coverage();

  task automatic reset_scope(
      input longint unsigned timestamp_fs,
      input int unsigned rank,
      input longint unsigned reset_epoch
  );
    coverage.observe(timestamp_fs, 0, 0, rank, 0, reset_epoch,
                     TCK_FS, 1'b1, 1'b0, DDR5_CMD_UNKNOWN);
  endtask

  initial begin
    // VrefCA -> ACT exactly at tMRD.
    reset_scope(1_000_000, 0, 1);
    coverage.observe(2_000_000, 0, 0, 0, 0, 1, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_VREFCA);
    coverage.observe(2_000_000 + TMRD_FS, 0, 0, 0, 0, 1, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_ACT);

    // VrefCA -> MRR above tMRD.
    reset_scope(20_000_000, 0, 2);
    coverage.observe(21_000_000, 0, 0, 0, 0, 2, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_VREFCA);
    coverage.observe(21_000_000 + TMRD_FS + 1, 0, 0, 0, 0, 2, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_MRR);

    // VrefCS -> ACT one femtosecond below tMRD: illegal.
    reset_scope(40_000_000, 0, 3);
    coverage.observe(41_000_000, 0, 0, 0, 0, 3, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_VREFCS);
    coverage.observe(41_000_000 + TMRD_FS - 1, 0, 0, 0, 0, 3, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_ACT);

    // Rank histories are independent.
    reset_scope(60_000_000, 0, 4);
    reset_scope(60_000_000, 1, 4);
    coverage.observe(61_000_000, 0, 0, 0, 0, 4, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_VREFCA);
    coverage.observe(61_000_000 + TMRD_FS, 0, 0, 1, 0, 4, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_ACT);
    coverage.observe(61_000_000 + TMRD_FS, 0, 0, 0, 0, 4, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_ACT);

    // A config epoch change invalidates old history.
    reset_scope(80_000_000, 0, 5);
    coverage.observe(81_000_000, 0, 0, 0, 0, 5, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_VREFCS);
    coverage.observe(81_000_000 + TMRD_FS, 0, 0, 0, 1, 5, TCK_FS,
                     1'b0, 1'b1, DDR5_CMD_ACT);

    if (coverage.vrefca_at_bound_count != 2)
      $fatal(1, "expected two VrefCA at-bound samples");
    if (coverage.vrefca_above_bound_count != 1)
      $fatal(1, "expected one VrefCA above-bound sample");
    if (coverage.vrefca_violation_count != 0)
      $fatal(1, "unexpected VrefCA violation");
    if (coverage.vrefcs_violation_count != 1)
      $fatal(1, "expected one VrefCS violation");
    if (coverage.vrefcs_at_bound_count != 0 ||
        coverage.vrefcs_above_bound_count != 0)
      $fatal(1, "unexpected legal VrefCS sample");

    $display("DDR5 Vref coverage smoke test PASS");
    $finish;
  end

endmodule
