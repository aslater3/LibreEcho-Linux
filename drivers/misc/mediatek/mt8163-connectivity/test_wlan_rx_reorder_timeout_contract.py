#!/usr/bin/env python3
"""Compiled contract for the RX block-ack reorder miss timeout.

qmPopOutDueToFallWithin() is compiled from que_mgt.c against the driver's own
queue and timeout macros. Once the miss timeout has expired, one call must
release every queued frame across every hole. Releasing one hole per call left
a burst loss waiting a new arrival plus a full timeout per hole, and RX stalled
for 10-30 s while the link stayed associated.
"""

from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest


HERE = Path(__file__).resolve().parent
WLAN = HERE / "conn_soc/drv_wlan/mt_wifi/wlan"
QUE_MGT = WLAN / "nic/que_mgt.c"


def macro(header: Path, name: str) -> str:
    """Return a #define from a driver header, continuation lines included."""
    text = header.read_text(encoding="utf-8")
    match = re.search(
        rf"^#define {name}\b(?:[^\n]*\\\n)*[^\n]*$", text, re.MULTILINE
    )
    if not match:
        raise AssertionError(f"{name} not found in {header}")
    return match.group(0)


def function(source: str) -> str:
    start = source.index("BOOLEAN\nqmPopOutDueToFallWithin(")
    end = source.index("VOID qmPopOutDueToFallAhead(", start)
    return source[start:end]


HARNESS = textwrap.dedent(
    r"""
    #include <stdio.h>
    #include <stdlib.h>

    typedef unsigned char UINT_8;
    typedef unsigned short UINT_16;
    typedef unsigned int UINT_32;
    typedef unsigned char BOOLEAN;
    typedef unsigned int OS_SYSTIME;
    #define TRUE 1
    #define FALSE 0
    #define IN
    #define OUT
    #define QUE_ASSERT(x)
    typedef struct _QUE_ENTRY_T {
        struct _QUE_ENTRY_T *prNext, *prPrev;
    } QUE_ENTRY_T, *P_QUE_ENTRY_T;
    typedef struct { P_QUE_ENTRY_T prHead, prTail; UINT_32 u4NumElem; } QUE_T, *P_QUE_T;
    typedef struct { QUE_ENTRY_T rQueEntry; UINT_16 u2SSN; } SW_RFB_T, *P_SW_RFB_T;
    typedef struct {
        QUE_T rReOrderQue;
        UINT_16 u2WinStart, u2WinEnd, u2WinSize;
        UINT_8 ucStaRecIdx, ucTid;
    } RX_BA_ENTRY_T, *P_RX_BA_ENTRY_T;

    static OS_SYSTIME now;
    static int logged;
    static OS_SYSTIME g_arMissTimeout[1][8];
    #define MSEC_TO_SYSTIME(ms) (ms)
    #define GET_CURRENT_SYSTIME(p) (*(p) = now)
    #define DBGLOG(...) do { } while (0)
    #define pr_info_ratelimited(...) (logged++)

    @MACROS@

    @FUNCTION@

    static SW_RFB_T frames[16];
    static int failures;

    static void check(int ok, const char *what)
    {
        if (!ok) {
            printf("FAIL: %s\n", what);
            failures++;
        }
    }

    /* Queue the given SSNs, call once, and compare what was released. */
    static void scenario(const char *name, UINT_16 win_start, const int *ssn, int n,
                         OS_SYSTIME miss, OS_SYSTIME at, const int *want, int want_n,
                         UINT_16 want_start, BOOLEAN want_empty, BOOLEAN want_timeout,
                         OS_SYSTIME want_miss)
    {
        RX_BA_ENTRY_T ba = { { NULL, NULL, 0 }, win_start, 0, 64, 0, 3 };
        QUE_T out = { NULL, NULL, 0 };
        BOOLEAN timeout = 2, empty;
        P_QUE_ENTRY_T e;
        int i = 0;

        for (int k = 0; k < n; k++) {
            frames[k].u2SSN = (UINT_16)ssn[k];
            frames[k].rQueEntry.prPrev = ba.rReOrderQue.prTail;
            QUEUE_INSERT_TAIL(&ba.rReOrderQue, &frames[k].rQueEntry);
        }
        g_arMissTimeout[0][3] = miss;
        now = at;
        logged = 0;
        empty = qmPopOutDueToFallWithin(&ba, &out, &timeout);
        for (e = out.prHead; e; e = e->prNext, i++)
            if (i >= want_n || ((P_SW_RFB_T)e)->u2SSN != want[i])
                break;
        printf("%s: released %u, win_start %u\n", name, out.u4NumElem, ba.u2WinStart);
        check(i == want_n && e == NULL && out.u4NumElem == (UINT_32)want_n, name);
        check(ba.u2WinStart == want_start, "window start");
        check(ba.u2WinEnd == (want_start + 63) % MAX_SEQ_NO_COUNT, "window end");
        check(empty == want_empty, "return value");
        check(timeout == want_timeout, "timeout flag");
        check(g_arMissTimeout[0][3] == want_miss, "miss timeout");
        check(logged == (want_timeout ? 1 : 0), "rate-limited log");
    }

    int main(void)
    {
        /* Burst loss: holes at 100, 103 and 106, miss timeout expired. */
        static const int burst[] = { 101, 102, 104, 105, 107 };
        scenario("expired timeout releases every hole", 100, burst, 5, 5,
                 5 + QM_RX_BA_ENTRY_MISS_TIMEOUT_MS, burst, 5, 108, TRUE, TRUE, 0);
        /* One tick before the timeout nothing moves and the timer keeps running. */
        scenario("pending timeout holds every frame", 100, burst, 5, 5,
                 5 + QM_RX_BA_ENTRY_MISS_TIMEOUT_MS - 1, NULL, 0, 100, FALSE, FALSE, 5);
        /* In-order frames go up, the next hole arms the timeout. */
        static const int order[] = { 100, 101, 103 }, up[] = { 100, 101 };
        scenario("in-order frames up to a hole", 100, order, 3, 0, 77, up, 2, 102,
                 FALSE, FALSE, 77);
        /* Holes at 4095 and 1 across the sequence wrap. */
        static const int wrap[] = { 0, 2 };
        scenario("expired timeout across the wrap", 4095, wrap, 2, 9,
                 9 + QM_RX_BA_ENTRY_MISS_TIMEOUT_MS, wrap, 2, 3, TRUE, TRUE, 0);
        if (failures)
            return 1;
        puts("compiled reorder timeout contract: PASS");
        return 0;
    }
    """
)


class RxReorderTimeoutContract(unittest.TestCase):
    def test_expired_miss_timeout_releases_every_hole(self) -> None:
        include = WLAN / "include"
        macros = "\n".join(
            [
                macro(include / "queue.h", "QUEUE_IS_EMPTY"),
                macro(include / "queue.h", "QUEUE_GET_HEAD"),
                macro(include / "queue.h", "QUEUE_INSERT_TAIL"),
                macro(include / "mgmt/cnm_timer.h", "CHECK_FOR_EXPIRATION"),
                macro(include / "mgmt/cnm_timer.h", "CHECK_FOR_TIMEOUT"),
                macro(include / "nic/nic_rx.h", "MAX_SEQ_NO_COUNT"),
                macro(include / "nic/que_mgt.h", "QM_RX_BA_ENTRY_MISS_TIMEOUT_MS"),
            ]
        )
        harness = HARNESS.replace("@MACROS@", macros).replace(
            "@FUNCTION@", function(QUE_MGT.read_text(encoding="utf-8"))
        )
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            source = temp / "reorder_timeout_contract.c"
            binary = temp / "reorder_timeout_contract"
            source.write_text(harness, encoding="utf-8")
            subprocess.run(
                ["gcc", "-std=c99", "-Wall", "-Werror", str(source), "-o", str(binary)],
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [str(binary)], check=False, capture_output=True, text=True
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("compiled reorder timeout contract: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
