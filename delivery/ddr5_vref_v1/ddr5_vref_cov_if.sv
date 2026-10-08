`timescale 1ps/1fs

// Standalone event-level DDR5 Vref timing coverage collector.
//
// The future TB adapter must call observe() once for each decoded semantic
// command. timestamp_fs is the reviewed command anchor, not driver intent.
// For a multi-cycle Vref command the adapter owns raw-edge consolidation and
// supplies the Table 125/127 measurement anchor.
interface ddr5_vref_cov_if #(
  parameter int unsigned NUM_CHANNELS    = 1,
  parameter int unsigned NUM_SUBCHANNELS = 2,
  parameter int unsigned NUM_RANKS       = 2,
  parameter bit TRACE_ENABLE             = 1'b0
);
  import ddr5_vref_cov_pkg::*;

  localparam int unsigned NUM_SCOPES =
      NUM_CHANNELS * NUM_SUBCHANNELS * NUM_RANKS;
  localparam longint unsigned TMRD_ABSOLUTE_MIN_FS = 14_000_000;

  bit epoch_valid[0:NUM_SCOPES-1];
  bit timestamp_valid[0:NUM_SCOPES-1];
  bit vrefca_history_valid[0:NUM_SCOPES-1];
  bit vrefcs_history_valid[0:NUM_SCOPES-1];

  longint unsigned scope_config_epoch[0:NUM_SCOPES-1];
  longint unsigned scope_reset_epoch[0:NUM_SCOPES-1];
  longint unsigned scope_tck_fs[0:NUM_SCOPES-1];
  longint unsigned last_timestamp_fs[0:NUM_SCOPES-1];
  longint unsigned vrefca_timestamp_fs[0:NUM_SCOPES-1];
  longint unsigned vrefcs_timestamp_fs[0:NUM_SCOPES-1];
  longint unsigned vrefca_bound_fs[0:NUM_SCOPES-1];
  longint unsigned vrefcs_bound_fs[0:NUM_SCOPES-1];

  longint unsigned invalid_observation_count;
  longint unsigned vrefca_opportunity_count;
  longint unsigned vrefca_suppressed_count;
  longint unsigned vrefca_violation_count;
  longint unsigned vrefca_at_bound_count;
  longint unsigned vrefca_above_bound_count;
  longint unsigned vrefcs_opportunity_count;
  longint unsigned vrefcs_suppressed_count;
  longint unsigned vrefcs_violation_count;
  longint unsigned vrefcs_at_bound_count;
  longint unsigned vrefcs_above_bound_count;

  covergroup cg_vrefca_delay with function sample(
      ddr5_vref_cmd_e end_command,
      ddr5_vref_outcome_e outcome
  );
    option.per_instance = 1;
    cp_end_command: coverpoint end_command {
      bins act                   = {DDR5_CMD_ACT};
      bins mpc_zqcal_start       = {DDR5_CMD_MPC_ZQCAL_START};
      bins preab                 = {DDR5_CMD_PREAB};
      bins prepb                 = {DDR5_CMD_PREPB};
      bins presb                 = {DDR5_CMD_PRESB};
      bins mpc_enter_ca_training = {DDR5_CMD_MPC_ENTER_CA_TRAINING};
      bins mpc_enter_cs_training = {DDR5_CMD_MPC_ENTER_CS_TRAINING};
      bins mpc_enter_pda_enum    = {DDR5_CMD_MPC_ENTER_PDA_ENUM};
      bins mpc_pda_select_id     = {DDR5_CMD_MPC_PDA_SELECT_ID};
      bins mrr                   = {DDR5_CMD_MRR};
      bins mrw                   = {DDR5_CMD_MRW};
      bins pde                   = {DDR5_CMD_PDE};
      bins refab                 = {DDR5_CMD_REFAB};
      bins refsb                 = {DDR5_CMD_REFSB};
      bins rfmab                 = {DDR5_CMD_RFMAB};
      bins rfmsb                 = {DDR5_CMD_RFMSB};
      bins sre                   = {DDR5_CMD_SRE};
      bins vrefca               = {DDR5_CMD_VREFCA};
      bins vrefcs               = {DDR5_CMD_VREFCS};
    }
    cp_outcome: coverpoint outcome {
      ignore_bins below_bound = {DDR5_VREF_BELOW_BOUND};
      bins at_bound            = {DDR5_VREF_AT_BOUND};
      bins above_bound         = {DDR5_VREF_ABOVE_BOUND};
    }
    end_command_x_outcome: cross cp_end_command, cp_outcome;
  endgroup

  covergroup cg_vrefcs_delay with function sample(
      ddr5_vref_cmd_e end_command,
      ddr5_vref_outcome_e outcome
  );
    option.per_instance = 1;
    cp_end_command: coverpoint end_command {
      bins act                   = {DDR5_CMD_ACT};
      bins mpc_zqcal_start       = {DDR5_CMD_MPC_ZQCAL_START};
      bins preab                 = {DDR5_CMD_PREAB};
      bins prepb                 = {DDR5_CMD_PREPB};
      bins presb                 = {DDR5_CMD_PRESB};
      bins mpc_enter_ca_training = {DDR5_CMD_MPC_ENTER_CA_TRAINING};
      bins mpc_enter_cs_training = {DDR5_CMD_MPC_ENTER_CS_TRAINING};
      bins mpc_enter_pda_enum    = {DDR5_CMD_MPC_ENTER_PDA_ENUM};
      bins mpc_pda_select_id     = {DDR5_CMD_MPC_PDA_SELECT_ID};
      bins mrr                   = {DDR5_CMD_MRR};
      bins mrw                   = {DDR5_CMD_MRW};
      bins pde                   = {DDR5_CMD_PDE};
      bins refab                 = {DDR5_CMD_REFAB};
      bins refsb                 = {DDR5_CMD_REFSB};
      bins rfmab                 = {DDR5_CMD_RFMAB};
      bins rfmsb                 = {DDR5_CMD_RFMSB};
      bins sre                   = {DDR5_CMD_SRE};
      bins vrefca               = {DDR5_CMD_VREFCA};
      bins vrefcs               = {DDR5_CMD_VREFCS};
    }
    cp_outcome: coverpoint outcome {
      ignore_bins below_bound = {DDR5_VREF_BELOW_BOUND};
      bins at_bound            = {DDR5_VREF_AT_BOUND};
      bins above_bound         = {DDR5_VREF_ABOVE_BOUND};
    }
    end_command_x_outcome: cross cp_end_command, cp_outcome;
  endgroup

  cg_vrefca_delay vrefca_delay_cov;
  cg_vrefcs_delay vrefcs_delay_cov;

  function automatic int unsigned scope_index(
      input int unsigned channel,
      input int unsigned subchannel,
      input int unsigned rank
  );
    scope_index = ((channel * NUM_SUBCHANNELS) + subchannel) * NUM_RANKS + rank;
  endfunction

  function automatic longint unsigned resolve_tmrd_fs(
      input longint unsigned tck_fs
  );
    longint unsigned sixteen_tck_fs;
    sixteen_tck_fs = 16 * tck_fs;
    resolve_tmrd_fs = (sixteen_tck_fs > TMRD_ABSOLUTE_MIN_FS)
                    ? sixteen_tck_fs : TMRD_ABSOLUTE_MIN_FS;
  endfunction

  task automatic clear_histories(input int unsigned scope);
    vrefca_history_valid[scope] = 1'b0;
    vrefcs_history_valid[scope] = 1'b0;
  endtask

  task automatic sample_vrefca(
      input int unsigned scope,
      input longint unsigned timestamp_fs,
      input ddr5_vref_cmd_e end_command
  );
    longint unsigned delta_fs;
    ddr5_vref_outcome_e outcome;
    vrefca_opportunity_count++;
    if (!vrefca_history_valid[scope]) begin
      vrefca_suppressed_count++;
    end else begin
      delta_fs = timestamp_fs - vrefca_timestamp_fs[scope];
      if (delta_fs < vrefca_bound_fs[scope]) begin
        outcome = DDR5_VREF_BELOW_BOUND;
        vrefca_violation_count++;
      end else if (delta_fs == vrefca_bound_fs[scope]) begin
        outcome = DDR5_VREF_AT_BOUND;
        vrefca_at_bound_count++;
      end else begin
        outcome = DDR5_VREF_ABOVE_BOUND;
        vrefca_above_bound_count++;
      end
      vrefca_delay_cov.sample(end_command, outcome);
      if (TRACE_ENABLE) begin
        $display("DDR5_VREFCA_SAMPLE scope=%0d end=%s delta_fs=%0d bound_fs=%0d outcome=%0d",
                 scope, end_command.name(), delta_fs,
                 vrefca_bound_fs[scope], outcome);
      end
    end
  endtask

  task automatic sample_vrefcs(
      input int unsigned scope,
      input longint unsigned timestamp_fs,
      input ddr5_vref_cmd_e end_command
  );
    longint unsigned delta_fs;
    ddr5_vref_outcome_e outcome;
    vrefcs_opportunity_count++;
    if (!vrefcs_history_valid[scope]) begin
      vrefcs_suppressed_count++;
    end else begin
      delta_fs = timestamp_fs - vrefcs_timestamp_fs[scope];
      if (delta_fs < vrefcs_bound_fs[scope]) begin
        outcome = DDR5_VREF_BELOW_BOUND;
        vrefcs_violation_count++;
      end else if (delta_fs == vrefcs_bound_fs[scope]) begin
        outcome = DDR5_VREF_AT_BOUND;
        vrefcs_at_bound_count++;
      end else begin
        outcome = DDR5_VREF_ABOVE_BOUND;
        vrefcs_above_bound_count++;
      end
      vrefcs_delay_cov.sample(end_command, outcome);
      if (TRACE_ENABLE) begin
        $display("DDR5_VREFCS_SAMPLE scope=%0d end=%s delta_fs=%0d bound_fs=%0d outcome=%0d",
                 scope, end_command.name(), delta_fs,
                 vrefcs_bound_fs[scope], outcome);
      end
    end
  endtask

  // Calls must be serialized. command_valid=false means the decoded
  // observation is untrusted; both Vref histories in that scope are cleared.
  task automatic observe(
      input longint unsigned timestamp_fs,
      input int unsigned channel,
      input int unsigned subchannel,
      input int unsigned rank,
      input longint unsigned config_epoch,
      input longint unsigned reset_epoch,
      input longint unsigned tck_fs,
      input bit is_reset,
      input bit command_valid,
      input ddr5_vref_cmd_e command
  );
    int unsigned scope;
    bit epoch_changed;

    if (channel >= NUM_CHANNELS ||
        subchannel >= NUM_SUBCHANNELS ||
        rank >= NUM_RANKS) begin
      $fatal(1, "DDR5 Vref coverage scope out of range: ch=%0d sc=%0d rank=%0d",
             channel, subchannel, rank);
    end
    if (tck_fs == 0) begin
      $fatal(1, "DDR5 Vref coverage requires tck_fs > 0");
    end

    scope = scope_index(channel, subchannel, rank);
    if (timestamp_valid[scope] && timestamp_fs <= last_timestamp_fs[scope]) begin
      $fatal(1, "DDR5 Vref coverage timestamps must increase within a scope");
    end
    timestamp_valid[scope] = 1'b1;
    last_timestamp_fs[scope] = timestamp_fs;

    if (epoch_valid[scope] &&
        (config_epoch < scope_config_epoch[scope] ||
         reset_epoch < scope_reset_epoch[scope])) begin
      $fatal(1, "DDR5 Vref coverage epoch regression");
    end

    epoch_changed = !epoch_valid[scope] ||
                    config_epoch != scope_config_epoch[scope] ||
                    reset_epoch != scope_reset_epoch[scope];
    if (epoch_changed || is_reset) begin
      clear_histories(scope);
    end else if (tck_fs != scope_tck_fs[scope]) begin
      $fatal(1, "tCK changed without a config_epoch change");
    end

    epoch_valid[scope] = 1'b1;
    scope_config_epoch[scope] = config_epoch;
    scope_reset_epoch[scope] = reset_epoch;
    scope_tck_fs[scope] = tck_fs;

    if (is_reset) begin
      return;
    end
    if (!command_valid) begin
      invalid_observation_count++;
      clear_histories(scope);
      return;
    end

    // Measure against old history before latching this event. This preserves
    // correct self-overlap behavior for VrefCA->VrefCA and VrefCS->VrefCS.
    if (ddr5_vref_is_valid_end(command)) begin
      sample_vrefca(scope, timestamp_fs, command);
      sample_vrefcs(scope, timestamp_fs, command);
    end

    if (command == DDR5_CMD_VREFCA) begin
      vrefca_timestamp_fs[scope] = timestamp_fs;
      vrefca_bound_fs[scope] = resolve_tmrd_fs(tck_fs);
      vrefca_history_valid[scope] = 1'b1;
    end
    if (command == DDR5_CMD_VREFCS) begin
      vrefcs_timestamp_fs[scope] = timestamp_fs;
      vrefcs_bound_fs[scope] = resolve_tmrd_fs(tck_fs);
      vrefcs_history_valid[scope] = 1'b1;
    end
  endtask

  initial begin : initialize_coverage
    int unsigned scope;
    vrefca_delay_cov = new();
    vrefcs_delay_cov = new();
    invalid_observation_count = 0;
    vrefca_opportunity_count = 0;
    vrefca_suppressed_count = 0;
    vrefca_violation_count = 0;
    vrefca_at_bound_count = 0;
    vrefca_above_bound_count = 0;
    vrefcs_opportunity_count = 0;
    vrefcs_suppressed_count = 0;
    vrefcs_violation_count = 0;
    vrefcs_at_bound_count = 0;
    vrefcs_above_bound_count = 0;
    for (scope = 0; scope < NUM_SCOPES; scope++) begin
      epoch_valid[scope] = 1'b0;
      timestamp_valid[scope] = 1'b0;
      clear_histories(scope);
    end
  end

endinterface
