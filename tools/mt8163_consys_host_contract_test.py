#!/usr/bin/env python3
"""Contract for the kernel side of the out-of-tree MT8163 CONSYS stack.

The WMT/STP/BTIF, Wi-Fi and Bluetooth modules live in
LibreEcho-mt8163-connectivity.  This tree must keep loadable modules enabled
and build in the infrastructure those modules cannot select themselves.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEFCONFIG = ROOT / "arch/arm/configs/mt8163_arm32_defconfig"
KCONFIG = ROOT / "drivers/misc/Kconfig"


class Mt8163ConsysHostContractTests(unittest.TestCase):
    def test_defconfig_enables_modules_and_the_host_option(self) -> None:
        config = DEFCONFIG.read_text()
        for symbol in ("CONFIG_MODULES=y", "CONFIG_MTK_MT8163_CONSYS_HOST=y"):
            with self.subTest(symbol=symbol):
                self.assertIn(f"{symbol}\n", config)

    def test_in_tree_stack_is_gone(self) -> None:
        self.assertFalse((ROOT / "drivers/misc/mediatek").exists())
        config = DEFCONFIG.read_text()
        self.assertNotIn("CONFIG_MTK_MT8163_CONSYS=y", config)

    def test_host_option_selects_what_the_modules_need(self) -> None:
        kconfig = KCONFIG.read_text()
        block = kconfig.split("config MTK_MT8163_CONSYS_HOST", 1)[1].split(
            "\nconfig ", 1
        )[0]
        for symbol in (
            "CFG80211",
            "CRC32",
            "FW_LOADER",
            "ZLIB_DEFLATE",
            "WIRELESS_EXT",
            "WEXT_CORE",
            "WEXT_PROC",
            "WEXT_PRIV",
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(f"\tselect {symbol}\n", block)


if __name__ == "__main__":
    unittest.main()
