#!/usr/bin/env python3
"""Run every LibreEcho source contract test in this tree.

The tests sit next to the code they check.  Each one is a standalone script
that exits non-zero on failure; this runner executes them all and reports
every failure instead of stopping at the first.
"""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent

TESTS = (
    "libreecho/test_targets.py",
    "libreecho/test_next_lts_canary.py",
    "drivers/usb/musb/test_mt8163_console_diag_contract.py",
    "drivers/usb/musb/test_mt8163_role_switch_contract.py",
    "drivers/misc/test_amz_privacy_atomic_context.py",
    "drivers/misc/test_libreecho_radar_puffin_keys.py",
    "drivers/leds/test_is31fl32xx_init_contract.py",
    "drivers/leds/test_is31fl3236_scaled_frame_contract.py",
    "drivers/thermal/test_amazon_thermistor_policy_contract.py",
    "sound/soc/mediatek/mt8163/test_mt8163_mclk_pinctrl_contract.py",
    "sound/soc/mediatek/mt8163/test_mt8163_afe_irq_atomic_contract.py",
    "sound/soc/mediatek/mt8163/test_radar_puffin_hp_outputs.py",
    "sound/soc/mediatek/mt8163/test_radar_puffin_volume_preservation.py",
    "sound/soc/mediatek/mt8163/test_radar_puffin_speaker_profile.py",
    "sound/soc/mediatek/mt8163/test_mt8163_wide_playback_contract.py",
    "fs/proc/test_proc_map_files_null_mm_contract.py",
    "tools/mt8163_pstore_contract_test.py",
    "tools/mt8163_pstore_ramoops_contract_test.py",
    "tools/mt8163_mute_lamp_contract_test.py",
    "tools/mt8163_bluetooth_contract_test.py",
    "drivers/misc/mediatek/mt8163-connectivity/test_idme_factory_mac_contract.py",
    "drivers/misc/mediatek/mt8163-connectivity/test_wext_cfg80211_fallback.py",
    "drivers/misc/mediatek/mt8163-connectivity/test_wifi_state_reporting_contract.py",
)


def main() -> int:
    failed = []
    for test in TESTS:
        print(f"::group::{test}", flush=True)
        result = subprocess.run([sys.executable, "-B", str(ROOT / test)], cwd=ROOT)
        print("::endgroup::", flush=True)
        status = "PASS" if result.returncode == 0 else "FAIL"
        print(f"{status} {test}", flush=True)
        if result.returncode != 0:
            failed.append(test)

    # Every test_*.py / *_contract_test.py we own must be listed above.
    owned = {
        str(p.relative_to(ROOT))
        for pattern in ("**/test_*.py", "tools/mt8163_*_test.py")
        for p in ROOT.glob(pattern)
        if not str(p.relative_to(ROOT)).startswith(
            # Upstream's own Python tests, not LibreEcho contracts.
            ("tools/testing/", "scripts/", "Documentation/",
             "tools/crypto/ccp/", "tools/power/cpupower/bindings/")
        )
    }
    unlisted = sorted(owned - set(TESTS))
    for test in unlisted:
        print(f"FAIL {test} is not listed in {Path(__file__).name}")

    print(f"{len(TESTS) - len(failed)}/{len(TESTS)} contract tests passed")
    return 1 if failed or unlisted else 0


if __name__ == "__main__":
    sys.exit(main())
