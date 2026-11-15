#!/usr/bin/env python3
"""Regression contract for the Radar-Puffin FPGA capture loop's pacing sleep.

amzn_spi_data_read() is the body of an always-on capture loop: while the
wakeword pipeline holds the SPI PCM open it never returns, and between FPGA
frame reads it sleeps for a few milliseconds.  A plain usleep_range() sleeps
TASK_UNINTERRUPTIBLE, so the healthy loop showed up as a permanently D-state
kworker (kworker/0:xH+amznspi, wchan=amzn_spi_data_read) and added a constant
1.0 to the load average, which reads as a wedged driver.

This contract asserts:

1. The pacing sleep uses usleep_idle_range() (TASK_IDLE: uninterruptible, but
   neither counted toward loadavg nor reported as D).
2. The capture loop has no other TASK_UNINTERRUPTIBLE timed sleep.

Run from the kernel source root:

    python3 sound/soc/mediatek/mt8163-amzn-spi/test_amzn_spi_capture_pacing_contract.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DRIVER = ROOT / "sound/soc/mediatek/mt8163-amzn-spi/amzn-mt-spi-pcm.c"

# Timed sleeps that put the task in TASK_UNINTERRUPTIBLE and so count as load.
UNINTERRUPTIBLE_SLEEPS = ("usleep_range", "fsleep", "msleep", "ssleep", "schedule_timeout_uninterruptible")


def function_body(text, signature):
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[brace:i + 1]
    raise AssertionError(f"unterminated body for {signature}")


def main():
    body = function_body(DRIVER.read_text(), "static void amzn_spi_data_read(struct work_struct *work)")
    failures = []
    if not re.search(r"\busleep_idle_range\(\s*SPI_READ_WAIT_MIN_US - elapsed_us,\s*SPI_READ_WAIT_MAX_US - elapsed_us\)", body):
        failures.append("capture pacing sleep must be usleep_idle_range(SPI_READ_WAIT_MIN_US - elapsed_us, SPI_READ_WAIT_MAX_US - elapsed_us)")
    for call in UNINTERRUPTIBLE_SLEEPS:
        if re.search(rf"\b{call}\s*\(", body):
            failures.append(f"amzn_spi_data_read() must not use TASK_UNINTERRUPTIBLE sleep {call}()")
    for failure in failures:
        print(f"FAIL: {failure}")
    if not failures:
        print("PASS: capture loop paces in TASK_IDLE")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
