`timescale 1ps/1fs

// DDR5 VrefCA/VrefCS coverage command and outcome types.
// Scope: JESD79-5D Table 125 and Table 127 delay relations only.
package ddr5_vref_cov_pkg;

  typedef enum logic [5:0] {
    DDR5_CMD_UNKNOWN,
    DDR5_CMD_ACT,
    DDR5_CMD_MPC_ZQCAL_START,
    DDR5_CMD_PREAB,
    DDR5_CMD_PREPB,
    DDR5_CMD_PRESB,
    DDR5_CMD_MPC_ENTER_CA_TRAINING,
    DDR5_CMD_MPC_ENTER_CS_TRAINING,
    DDR5_CMD_MPC_ENTER_PDA_ENUM,
    DDR5_CMD_MPC_PDA_SELECT_ID,
    DDR5_CMD_MRR,
    DDR5_CMD_MRW,
    DDR5_CMD_PDE,
    DDR5_CMD_REFAB,
    DDR5_CMD_REFSB,
    DDR5_CMD_RFMAB,
    DDR5_CMD_RFMSB,
    DDR5_CMD_SRE,
    DDR5_CMD_VREFCA,
    DDR5_CMD_VREFCS,
    DDR5_CMD_NOP,
    DDR5_CMD_DES
  } ddr5_vref_cmd_e;

  typedef enum int unsigned {
    DDR5_VREF_BELOW_BOUND = 0,
    DDR5_VREF_AT_BOUND    = 1,
    DDR5_VREF_ABOVE_BOUND = 2
  } ddr5_vref_outcome_e;

  function automatic bit ddr5_vref_is_valid_end(ddr5_vref_cmd_e command);
    case (command)
      DDR5_CMD_ACT,
      DDR5_CMD_MPC_ZQCAL_START,
      DDR5_CMD_PREAB,
      DDR5_CMD_PREPB,
      DDR5_CMD_PRESB,
      DDR5_CMD_MPC_ENTER_CA_TRAINING,
      DDR5_CMD_MPC_ENTER_CS_TRAINING,
      DDR5_CMD_MPC_ENTER_PDA_ENUM,
      DDR5_CMD_MPC_PDA_SELECT_ID,
      DDR5_CMD_MRR,
      DDR5_CMD_MRW,
      DDR5_CMD_PDE,
      DDR5_CMD_REFAB,
      DDR5_CMD_REFSB,
      DDR5_CMD_RFMAB,
      DDR5_CMD_RFMSB,
      DDR5_CMD_SRE,
      DDR5_CMD_VREFCA,
      DDR5_CMD_VREFCS: ddr5_vref_is_valid_end = 1'b1;
      default:         ddr5_vref_is_valid_end = 1'b0;
    endcase
  endfunction

endpackage
