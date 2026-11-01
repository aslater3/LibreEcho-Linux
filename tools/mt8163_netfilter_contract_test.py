#!/usr/bin/env python3
"""Source contract for the MT8163 nftables (default inbound firewall) kernel closure.

The LibreEcho inbound firewall is an nftables ruleset applied at boot by the
platform rootfs.  nft needs the netfilter, nf_tables, conntrack and reject
expressions built into the kernel, and the defconfig is the only kernel
configuration used by radar_puffin and biscuit (see libreecho/targets.json).
This check keeps that closure and its CI registration together.  It does not
claim the firewall works on hardware; that waits for the release-candidate OTA.
"""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFCONFIG = ROOT / "arch/arm/configs/mt8163_arm32_defconfig"
TARGETS = ROOT / "libreecho/targets.json"
WORKFLOW = ROOT / ".github/workflows/checks.yml"
RUNNER = ROOT / "libreecho/run_contract_tests.py"
DOC = ROOT / "Documentation/arm/libreecho-mt8163-defconfig.md"

# Symbols nft needs for `ct state established,related accept`, `meta l4proto`,
# `tcp/udp dport`, `iifname lo` and `reject` (inet family).
REQUIRED = (
    "CONFIG_IPV6=y",
    "CONFIG_NETFILTER=y",
    "CONFIG_NETFILTER_ADVANCED=y",
    "CONFIG_NETFILTER_NETLINK=y",
    "CONFIG_NF_CONNTRACK=y",
    "CONFIG_NF_TABLES=y",
    "CONFIG_NF_TABLES_INET=y",
    "CONFIG_NFT_CT=y",
    "CONFIG_NFT_REJECT=y",
    "CONFIG_NFT_REJECT_INET=y",
)


class Mt8163NetfilterContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.defconfig = DEFCONFIG.read_text(encoding="utf-8")
        self.targets = json.loads(TARGETS.read_text(encoding="utf-8"))
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_defconfig_enables_nftables_closure(self) -> None:
        for symbol in REQUIRED:
            with self.subTest(symbol=symbol):
                self.assertIn(f"{symbol}\n", self.defconfig)
        self.assertNotIn("# CONFIG_NETFILTER is not set", self.defconfig)

    def test_every_product_target_uses_this_defconfig(self) -> None:
        for name in ("radar_puffin", "biscuit"):
            with self.subTest(target=name):
                self.assertEqual(
                    self.targets[name]["defconfig"],
                    "mt8163_arm32_defconfig",
                )

    def test_contract_is_registered_in_the_pull_request_build(self) -> None:
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertEqual(
            runner.count('"tools/mt8163_netfilter_contract_test.py"'), 1
        )
        self.assertIn("python3 -B libreecho/run_contract_tests.py", self.workflow)


if __name__ == "__main__":
    unittest.main()
