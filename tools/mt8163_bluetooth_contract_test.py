#!/usr/bin/env python3
"""Kernel half of the MT8163 Linux HCI bridge contract.

The STP Bluetooth bridge itself is built out of tree in
LibreEcho-mt8163-connectivity, which tests the driver half.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HCI_HEADER = ROOT / "include/net/bluetooth/hci.h"
HCI_SOCK = ROOT / "net/bluetooth/hci_sock.c"
DEFCONFIG = ROOT / "arch/arm/configs/mt8163_arm32_defconfig"


class Mt8163BluetoothContractTests(unittest.TestCase):
    def test_defconfig_declares_complete_bluetooth_bridge(self) -> None:
        config = DEFCONFIG.read_text()
        required = (
            "CONFIG_BT=y",
            "CONFIG_BT_BREDR=y",
            "CONFIG_BT_LE=y",
            "CONFIG_RFKILL=y",
            "CONFIG_MTK_MT8163_CONSYS_HOST=y",
        )
        for symbol in required:
            with self.subTest(symbol=symbol):
                self.assertIn(f"{symbol}\n", config)

    def test_kernel_allows_only_power_on_during_deferred_setup(self) -> None:
        header = HCI_HEADER.read_text()
        sock = HCI_SOCK.read_text()
        self.assertIn("HCI_QUIRK_DEFERRED_SETUP,", header)
        self.assertIn("opcode == MGMT_OP_SET_POWERED", sock)
        self.assertIn("test_bit(HCI_QUIRK_DEFERRED_SETUP, &hdev->quirks)", sock)


if __name__ == "__main__":
    unittest.main()
