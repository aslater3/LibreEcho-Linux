#!/usr/bin/env python3
"""Source contract: the Radar-Puffin tick must be able to leave periodic mode.

Without "always-on" the arm,armv8-timer driver marks the per-CPU timer
CLOCK_EVT_FEAT_C3STOP, and tick_is_oneshot_available() then needs a oneshot
broadcast device.  This board registers none, so the kernel stayed in periodic
low-res mode for its whole uptime (Tick Device mode 0, hrtimer resolution
10 ms, 100 arch_timer IRQ/s on every idle CPU) despite CONFIG_HIGH_RES_TIMERS
and CONFIG_NO_HZ_IDLE.  Every hrtimer wakeup then lands on the tick just
before calc_global_load_tick() samples, inflating loadavg to ~4.5 on an
idle device.

always-on is only true while nothing powers the core timer down in idle, i.e.
while no cpuidle driver is built (CPUs only execute WFI).  Enabling
CONFIG_CPU_IDLE must revisit this, so the contract pins both together.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DTS = ROOT / "arch/arm/boot/dts/libreecho-radar-puffin.dts"
DEFCONFIG = ROOT / "arch/arm/configs/mt8163_arm32_defconfig"


def node_of(source: str, opening: str) -> str:
    start = source.index(opening)
    return source[start:source.index("\n\t};\n", start) + 1]


class ArchTimerOneshotContractTests(unittest.TestCase):
    def test_arch_timer_is_always_on(self) -> None:
        timer = node_of(DTS.read_text(), "\ttimer {\n")
        self.assertIn('compatible = "arm,armv8-timer";', timer)
        self.assertIn("\t\talways-on;\n", timer)

    def test_always_on_holds_only_without_cpuidle(self) -> None:
        defconfig = DEFCONFIG.read_text().splitlines()
        self.assertNotIn("CONFIG_CPU_IDLE=y", defconfig)
        self.assertIn("CONFIG_HIGH_RES_TIMERS=y", defconfig)
        self.assertIn("CONFIG_NO_HZ_IDLE=y", defconfig)


if __name__ == "__main__":
    unittest.main()
