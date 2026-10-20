#!/usr/bin/env python3
"""Kernel half of the MT8163 WEXT-over-cfg80211 contract.

The out-of-tree MT8163 WLAN driver exposes only private WEXT handlers on its
netdev, so wext-core must fall back to cfg80211 for the standard handlers.
The driver half is tested in LibreEcho-mt8163-connectivity.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEXT_CORE = ROOT / "net/wireless/wext-core.c"
DEFCONFIG = ROOT / "arch/arm/configs/mt8163_arm32_defconfig"


def get_handler_source() -> str:
    source = WEXT_CORE.read_text(encoding="utf-8")
    return source.split("static iw_handler get_handler", 1)[1].split(
        "static int ioctl_standard_iw_point", 1
    )[0]


class WextCfg80211FallbackTests(unittest.TestCase):
    def test_mt8163_enables_cfg80211_wext_compatibility(self) -> None:
        config = DEFCONFIG.read_text(encoding="utf-8")
        self.assertIn("CONFIG_CFG80211_WEXT=y", config)

    def test_standard_handlers_fall_back_to_cfg80211(self) -> None:
        get_handler = get_handler_source()
        self.assertIn("cfg_handlers", get_handler)
        self.assertIn("if (handler)", get_handler)
        self.assertIn("cfg_handlers->standard[index]", get_handler)

    def test_private_handlers_remain_device_owned(self) -> None:
        private_block = get_handler_source().split(
            "/* Private commands remain owned by the device handler table. */", 1
        )[1]
        self.assertIn("handlers->private[index]", private_block)
        self.assertNotIn("cfg_handlers->private[index]", private_block)


if __name__ == "__main__":
    unittest.main()
