#!/usr/bin/env python3
"""Regression contract: the capture loop hands its kworker back as it found it.

amzn_spi_data_read() runs on a shared per-CPU WQ_HIGHPRI pool worker
(kworker/N:xH) and calls sched_set_fifo(current) for the capture loop.  Without
a restore, that pool worker stays SCHED_FIFO after capture stops and runs every
later high-priority work item from unrelated drivers (block, mmc, ...) as RT.

This contract asserts the function records the worker's nice level before
switching to FIFO and restores SCHED_NORMAL at that nice level on the shared
exit path, after the loop and before returning.

Run from the kernel source root:

    python3 sound/soc/mediatek/mt8163-amzn-spi/test_amzn_spi_worker_policy_contract.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DRIVER = ROOT / "sound/soc/mediatek/mt8163-amzn-spi/amzn-mt-spi-pcm.c"


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
    saved = re.search(r"\bconst int pool_nice = task_nice\(current\);", body)
    fifo = body.find("sched_set_fifo(current);")
    out = body.find("\nout:\n")
    restore = body.find("sched_set_normal(current, pool_nice);")
    if not saved or fifo < 0 or saved.start() > fifo:
        failures.append("the worker's nice level must be saved (const int pool_nice = task_nice(current);) before sched_set_fifo()")
    if out < 0 or restore < out:
        failures.append("sched_set_normal(current, pool_nice) must run on the shared out: exit path")
    if body.count("return") and re.search(r"\breturn\b", body[:out if out >= 0 else len(body)]):
        failures.append("no early return may bypass the policy restore")
    for failure in failures:
        print(f"FAIL: {failure}")
    if not failures:
        print("PASS: capture loop restores the pool worker's scheduling policy")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
