import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "delivery/ddr5_vref_v1"


class Ddr5VrefDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads(
            (DELIVERY / "ddr5_vref_rules.json").read_text(encoding="utf-8")
        )
        self.package = (DELIVERY / "ddr5_vref_cov_pkg.sv").read_text(
            encoding="utf-8"
        )
        self.interface = (DELIVERY / "ddr5_vref_cov_if.sv").read_text(
            encoding="utf-8"
        )

    def test_rule_scope_has_38_legal_relations(self):
        self.assertEqual(self.rules["start_commands"], ["VrefCA", "VrefCS"])
        self.assertEqual(len(self.rules["end_commands"]), 19)
        self.assertEqual(len(set(self.rules["end_commands"])), 19)
        self.assertEqual(self.rules["legal_relation_count"], 38)
        self.assertEqual(
            self.rules["legal_relation_count"],
            len(self.rules["start_commands"]) * len(self.rules["end_commands"]),
        )

    def test_tmrd_and_source_contract_are_explicit(self):
        self.assertEqual(
            self.rules["bound"]["expression"], "max(14000000 fs, 16*tCK_fs)"
        )
        self.assertIn("Table 125", self.rules["source"]["vrefca_locator"])
        self.assertIn("Table 127", self.rules["source"]["vrefcs_locator"])
        self.assertEqual(self.rules["time_unit"], "fs")

    def test_all_rule_commands_exist_in_sv_types(self):
        enum_names = set(re.findall(r"DDR5_CMD_[A-Z0-9_]+", self.package))
        expected = {
            "ACT": "DDR5_CMD_ACT",
            "MPC_ZQCal_Start": "DDR5_CMD_MPC_ZQCAL_START",
            "PREab": "DDR5_CMD_PREAB",
            "PREpb": "DDR5_CMD_PREPB",
            "PREsb": "DDR5_CMD_PRESB",
            "MPC_Enter_CA_Training_Mode": "DDR5_CMD_MPC_ENTER_CA_TRAINING",
            "MPC_Enter_CS_Training_Mode": "DDR5_CMD_MPC_ENTER_CS_TRAINING",
            "MPC_Enter_PDA_Enumerate_Programming_Mode": "DDR5_CMD_MPC_ENTER_PDA_ENUM",
            "MPC_PDA_Select_ID": "DDR5_CMD_MPC_PDA_SELECT_ID",
            "MRR": "DDR5_CMD_MRR",
            "MRW": "DDR5_CMD_MRW",
            "PDE": "DDR5_CMD_PDE",
            "REFab": "DDR5_CMD_REFAB",
            "REFsb": "DDR5_CMD_REFSB",
            "RFMab": "DDR5_CMD_RFMAB",
            "RFMsb": "DDR5_CMD_RFMSB",
            "SRE": "DDR5_CMD_SRE",
            "VrefCA": "DDR5_CMD_VREFCA",
            "VrefCS": "DDR5_CMD_VREFCS",
        }
        self.assertEqual(set(expected), set(self.rules["end_commands"]))
        self.assertTrue(set(expected.values()).issubset(enum_names))

    def test_violation_is_not_a_legal_coverage_bin(self):
        self.assertEqual(self.interface.count("ignore_bins below_bound"), 2)
        self.assertNotIn("illegal_bins below_bound", self.interface)
        self.assertIn("vrefca_violation_count++", self.interface)
        self.assertIn("vrefcs_violation_count++", self.interface)


if __name__ == "__main__":
    unittest.main()
