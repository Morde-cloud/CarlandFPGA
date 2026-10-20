#!/usr/bin/env python3
"""Portable unit tests for the author-side deadline runner qualification."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
RUNNER_PATH = ROOT / "competition/deepeye/tools/control3d/run_first_capture_deadline.py"
SPEC = importlib.util.spec_from_file_location("first_capture_runner", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

REAL_NORMAL_LOG = r'''
Reading D:/modelsim1/tcl/vsim/pref.tcl

# 10.7

# vsim -c -quiet -wlf D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\evidence\control3d\first-capture-deadline-20261021\author\preflight-09\standalone-w01\sim.wlf tb_first_capture_deadline -do "run -all; quit -f" -gBUDGET_W=1 
# Start time: 01:42:04 on Oct 21,2026
# ** Note: (vsim-3812) Design is being optimized...
# //  ModelSim SE-64 10.7 Dec  7 2017
# //
# //  Copyright 1991-2017 Mentor Graphics Corporation
# //  All Rights Reserved.
# //
# //  ModelSim SE-64 and its associated documentation contain trade
# //  secrets and commercial or financial information that are the property of
# //  Mentor Graphics Corporation and are privileged, confidential,
# //  and exempt from disclosure under the Freedom of Information Act,
# //  5 U.S.C. Section 552. Furthermore, this information
# //  is prohibited from disclosure under the Trade Secrets Act,
# //  18 U.S.C. Section 1905.
# //
# run -all
# DEEPEYE_FC_RUN width=1 kind=standalone
# DEEPEYE_FC_SCENARIO id=w1b1o0 width=1 group=obs budget=1 obs=0 checks=45 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1o1 width=1 group=obs budget=1 obs=1 checks=45 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1o2 width=1 group=obs budget=1 obs=2 checks=45 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1c0 width=1 group=cancel budget=1 obs=0 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1r0 width=1 group=reset budget=1 obs=0 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1c1 width=1 group=cancel budget=1 obs=1 checks=54 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1r1 width=1 group=reset budget=1 obs=1 checks=54 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1c2 width=1 group=cancel budget=1 obs=2 checks=54 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1r2 width=1 group=reset budget=1 obs=2 checks=54 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1st1 width=1 group=restart budget=1 obs=1 checks=63 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1st2 width=1 group=restart budget=1 obs=2 checks=63 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio0 width=1 group=priority budget=1 obs=0 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio1 width=1 group=priority budget=1 obs=1 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio2 width=1 group=priority budget=1 obs=2 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio3 width=1 group=priority budget=1 obs=3 checks=45 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio4 width=1 group=priority budget=1 obs=4 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio5 width=1 group=priority budget=1 obs=5 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio6 width=1 group=priority budget=1 obs=6 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1prio7 width=1 group=priority budget=1 obs=7 checks=27 status=pass
# DEEPEYE_FC_SCENARIO id=w1held0 width=1 group=held budget=1 obs=0 checks=72 status=pass
# DEEPEYE_FC_SCENARIO id=w1held1 width=1 group=held budget=0 obs=0 checks=72 status=pass
# DEEPEYE_FC_SCENARIO id=w1termzero width=1 group=terminal budget=1 obs=0 checks=72 status=pass
# DEEPEYE_FC_SCENARIO id=w1termrestart width=1 group=terminal budget=1 obs=0 checks=63 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1latch1 width=1 group=latch budget=1 obs=1 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1b1latch0 width=1 group=latch budget=1 obs=0 checks=36 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188736 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188735 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188734 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188733 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188732 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188731 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188730 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188729 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188728 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188727 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188726 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188725 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188724 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188723 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188722 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188721 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188720 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188719 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188718 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188717 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188716 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188715 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188714 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188713 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188712 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188711 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188710 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188709 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188708 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188707 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188706 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188705 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188704 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188703 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188702 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188701 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188700 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188699 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188698 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188697 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188696 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188695 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188694 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188693 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188692 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188691 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188690 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188689 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188688 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188687 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188686 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188685 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188684 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188683 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188682 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188681 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188680 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188679 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188678 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188677 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188676 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188675 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188674 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188673 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188672 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188671 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188670 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188669 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188668 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188667 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188666 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188665 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188664 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188663 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188662 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188661 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188660 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188659 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188658 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188657 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188656 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188655 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188654 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188653 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188652 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188651 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188650 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188649 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188648 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188647 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188646 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188645 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188644 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188643 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188642 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188641 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188640 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188639 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188638 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SCENARIO id=w1rnd-1059188637 width=1 group=random budget=0 obs=0 checks=585 status=pass
# DEEPEYE_FC_SUMMARY width=1 kind=standalone scenarios=125 checks=59688 failures=0 groups=obs:3,cancel:3,reset:3,restart:2,priority:8,held:2,terminal:2,latch:2,random:100
# DEEPEYE_FC_FINISH width=1 status=PASS
# ** Note: $finish    : D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/tests/control/tb_first_capture_deadline.sv(1126)
#    Time: 66326 ns  Iteration: 0  Instance: /tb_first_capture_deadline
# End time: 01:42:05 on Oct 21,2026, Elapsed time: 0:00:01
# Errors: 0, Warnings: 0

'''
REAL_GUARD0_LOG = r'''
Reading D:/modelsim1/tcl/vsim/pref.tcl

# 10.7

# vsim -c -quiet -wlf D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\evidence\control3d\first-capture-deadline-20261021\author\preflight-09\guard-w00\sim.wlf tb_first_capture_deadline_guard -do "run -all; quit -f" -gBUDGET_W=0 
# Start time: 01:42:18 on Oct 21,2026
# ** Note: (vsim-3812) Design is being optimized...
# //  ModelSim SE-64 10.7 Dec  7 2017
# //
# //  Copyright 1991-2017 Mentor Graphics Corporation
# //  All Rights Reserved.
# //
# //  ModelSim SE-64 and its associated documentation contain trade
# //  secrets and commercial or financial information that are the property of
# //  Mentor Graphics Corporation and are privileged, confidential,
# //  and exempt from disclosure under the Freedom of Information Act,
# //  5 U.S.C. Section 552. Furthermore, this information
# //  is prohibited from disclosure under the Trade Secrets Act,
# //  18 U.S.C. Section 1905.
# //
# run -all
# DEEPEYE_FC_RUN width=0 kind=guard
# DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=0 SAFE_BUDGET_W=1
# ** Fatal: DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width
#    Time: 0 ps  Scope: tb_first_capture_deadline_guard.dut File: D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv Line: 137
# ** Note: $finish    : D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv(137)
#    Time: 0 ps  Iteration: 1  Instance: /tb_first_capture_deadline_guard/dut
# End time: 01:42:18 on Oct 21,2026, Elapsed time: 0:00:00
# Errors: 1, Warnings: 0

'''
REAL_GUARD33_LOG = r'''
Reading D:/modelsim1/tcl/vsim/pref.tcl

# 10.7

# vsim -c -quiet -wlf D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\evidence\control3d\first-capture-deadline-20261021\author\preflight-09\guard-w33\sim.wlf tb_first_capture_deadline_guard -do "run -all; quit -f" -gBUDGET_W=33 
# Start time: 01:42:20 on Oct 21,2026
# ** Note: (vsim-3812) Design is being optimized...
# //  ModelSim SE-64 10.7 Dec  7 2017
# //
# //  Copyright 1991-2017 Mentor Graphics Corporation
# //  All Rights Reserved.
# //
# //  ModelSim SE-64 and its associated documentation contain trade
# //  secrets and commercial or financial information that are the property of
# //  Mentor Graphics Corporation and are privileged, confidential,
# //  and exempt from disclosure under the Freedom of Information Act,
# //  5 U.S.C. Section 552. Furthermore, this information
# //  is prohibited from disclosure under the Trade Secrets Act,
# //  18 U.S.C. Section 1905.
# //
# run -all
# DEEPEYE_FC_RUN width=33 kind=guard
# DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=33 SAFE_BUDGET_W=32
# ** Fatal: DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width
#    Time: 0 ps  Scope: tb_first_capture_deadline_guard.dut File: D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv Line: 137
# ** Note: $finish    : D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv(137)
#    Time: 0 ps  Iteration: 1  Instance: /tb_first_capture_deadline_guard/dut
# End time: 01:42:20 on Oct 21,2026, Elapsed time: 0:00:00
# Errors: 1, Warnings: 0

'''


def summary_line(log_text: str) -> str:
    for line in log_text.splitlines():
        if "DEEPEYE_FC_SUMMARY" in line:
            return line
    raise AssertionError("fixture has no summary line")


def finish_line(log_text: str) -> str:
    for line in log_text.splitlines():
        if "DEEPEYE_FC_FINISH" in line:
            return line
    raise AssertionError("fixture has no finish line")


def scenario_line(log_text: str) -> str:
    for line in log_text.splitlines():
        if "DEEPEYE_FC_SCENARIO" in line:
            return line
    raise AssertionError("fixture has no scenario line")


class NormalLogTests(unittest.TestCase):
    def test_real_normal_log_accepted(self):
        ok, parsed, reasons = runner.qualify_normal_log(
            REAL_NORMAL_LOG, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertTrue(ok, reasons)
        self.assertEqual(parsed["runs"], 1)
        self.assertEqual(parsed["summaries"], 1)
        self.assertEqual(parsed["finishes"], 1)
        self.assertEqual(parsed["scenarios"], 125)
        self.assertEqual(parsed["checks"], 59688)
        self.assertEqual(parsed["failures"], 0)

    def test_normal_rejects_nonzero_exit(self):
        ok, _, reasons = runner.qualify_normal_log(
            REAL_NORMAL_LOG, 1, "standalone", runner.SMALL_GROUPS, 1
        )
        self.assertFalse(ok)
        self.assertTrue(any("exit" in reason for reason in reasons), reasons)

    def test_normal_rejects_timeout(self):
        ok, _, reasons = runner.qualify_normal_log(
            REAL_NORMAL_LOG, 1, "standalone", runner.SMALL_GROUPS, 0, timed_out=True
        )
        self.assertFalse(ok)
        self.assertTrue(any("timeout" in reason for reason in reasons), reasons)

    def test_duplicate_summary_rejected(self):
        text = REAL_NORMAL_LOG + "\n" + summary_line(REAL_NORMAL_LOG) + "\n"
        ok, _, reasons = runner.qualify_normal_log(
            text, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("SUMMARY" in reason for reason in reasons), reasons)

    def test_duplicate_finish_rejected(self):
        text = REAL_NORMAL_LOG + "\n" + finish_line(REAL_NORMAL_LOG) + "\n"
        ok, _, reasons = runner.qualify_normal_log(
            text, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("FINISH" in reason for reason in reasons), reasons)

    def test_duplicate_scenario_id_rejected(self):
        text = REAL_NORMAL_LOG + "\n" + scenario_line(REAL_NORMAL_LOG) + "\n"
        ok, _, reasons = runner.qualify_normal_log(
            text, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("duplicate scenario" in reason for reason in reasons), reasons)

    def test_conflicting_summary_rejected(self):
        bad = REAL_NORMAL_LOG.replace("failures=0 groups=", "failures=1 groups=")
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("failures" in reason for reason in reasons), reasons)

    def test_missing_finish_rejected(self):
        bad = REAL_NORMAL_LOG.replace(finish_line(REAL_NORMAL_LOG), "")
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("FINISH" in reason for reason in reasons), reasons)

    def test_unrelated_fatal_rejected(self):
        bad = REAL_NORMAL_LOG + "\n# ** Fatal: (vsim-9999) unrelated failure\n"
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("fatal" in reason or "error" in reason for reason in reasons), reasons)

    def test_unrelated_error_rejected(self):
        bad = REAL_NORMAL_LOG + "\n# ** Error: (vsim-9999) unrelated error\n"
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("fatal" in reason or "error" in reason for reason in reasons), reasons)

    def test_pseudo_finish_prefix_rejected(self):
        bad = REAL_NORMAL_LOG.replace(finish_line(REAL_NORMAL_LOG), "# XDEEPEYE_FC_FINISH width=1 status=PASS")
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("FINISH" in reason or "malformed" in reason for reason in reasons), reasons)

    def test_scenario_count_mismatch_rejected(self):
        bad = REAL_NORMAL_LOG.replace(scenario_line(REAL_NORMAL_LOG) + "\n", "", 1)
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("scenarios" in reason for reason in reasons), reasons)

    def test_group_mismatch_rejected(self):
        bad = REAL_NORMAL_LOG.replace("group=obs", "group=bogus", 1)
        ok, _, reasons = runner.qualify_normal_log(
            bad, 1, "standalone", runner.SMALL_GROUPS, 0
        )
        self.assertFalse(ok)
        self.assertTrue(any("group" in reason for reason in reasons), reasons)


class GuardLogTests(unittest.TestCase):
    def test_real_guard0_accepted(self):
        ok, parsed, reasons = runner.qualify_guard_log(REAL_GUARD0_LOG, 0, 0)
        self.assertTrue(ok, reasons)
        self.assertEqual(parsed["safe_width"], 1)
        self.assertEqual(parsed["params"], [(0, 1)])

    def test_real_guard33_accepted(self):
        ok, parsed, reasons = runner.qualify_guard_log(REAL_GUARD33_LOG, 33, 0)
        self.assertTrue(ok, reasons)
        self.assertEqual(parsed["safe_width"], 32)
        self.assertEqual(parsed["params"], [(33, 32)])

    def test_fake_valid_width_guard_rejected(self):
        fake = REAL_GUARD0_LOG.replace("width=0 kind=guard", "width=3 kind=guard")
        fake = fake.replace("BUDGET_W=0 SAFE_BUDGET_W=1", "BUDGET_W=3 SAFE_BUDGET_W=3")
        ok, _, reasons = runner.qualify_guard_log(fake, 3, 0)
        self.assertFalse(ok)
        self.assertTrue(any("unsupported" in reason or "width" in reason for reason in reasons), reasons)

    def test_wrong_safe_width_rejected(self):
        fake = REAL_GUARD0_LOG.replace("SAFE_BUDGET_W=1", "SAFE_BUDGET_W=2")
        ok, _, reasons = runner.qualify_guard_log(fake, 0, 0)
        self.assertFalse(ok)
        self.assertTrue(any("diagnostic" in reason for reason in reasons), reasons)

    def test_guard_nonzero_exit_rejected(self):
        ok, _, reasons = runner.qualify_guard_log(REAL_GUARD0_LOG, 0, 1)
        self.assertFalse(ok)
        self.assertTrue(any("exit" in reason for reason in reasons), reasons)

    def test_guard_timeout_rejected(self):
        ok, _, reasons = runner.qualify_guard_log(REAL_GUARD0_LOG, 0, 0, timed_out=True)
        self.assertFalse(ok)
        self.assertTrue(any("timeout" in reason for reason in reasons), reasons)


class ProcessTests(unittest.TestCase):
    def test_timeout_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "timeout.log"
            record = runner.run_process(
                [sys.executable, "-B", "-c", "import time; time.sleep(2)"],
                Path(temp_dir), log, 0.2,
            )
        self.assertTrue(record["timed_out"])
        self.assertIsNone(record["exit_code"])

    def test_exit_code_captured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log = Path(temp_dir) / "exit.log"
            record = runner.run_process(
                [sys.executable, "-B", "-c", "raise SystemExit(3)"],
                Path(temp_dir), log, 10,
            )
        self.assertFalse(record["timed_out"])
        self.assertEqual(record["exit_code"], 3)


class MutantLogTests(unittest.TestCase):
    def test_behavioral_mutant_log_accepted(self):
        text = "\n".join([
            "# DEEPEYE_FC_RUN width=1 kind=standalone",
            "# DEEPEYE_FC_SCENARIO id=w1b1o1 width=1 group=obs budget=1 obs=1 checks=18 status=pass",
            "# DEEPEYE_FC_CHECK_FAIL width=1 scenario=w1b1o2 phase=post expired dut=0 ref=1",
            "# DEEPEYE_FC_SUMMARY width=1 kind=standalone scenarios=1 checks=18 failures=1 groups=obs:1",
            "# DEEPEYE_FC_FINISH width=1 status=FAIL",
            "# ** Fatal: DEEPEYE_FC_BEHAVIOR_FAIL width=1 failures=1",
        ]) + "\n"
        ok, parsed, reasons = runner.qualify_mutant_log(text, 1, 0)
        self.assertTrue(ok, reasons)
        self.assertGreaterEqual(parsed["check_fail_lines"], 1)

    def test_mutant_without_check_fail_rejected(self):
        text = "\n".join([
            "# DEEPEYE_FC_RUN width=1 kind=standalone",
            "# DEEPEYE_FC_SUMMARY width=1 kind=standalone scenarios=0 checks=0 failures=0 groups=obs:0",
            "# DEEPEYE_FC_FINISH width=1 status=PASS",
        ]) + "\n"
        ok, _, reasons = runner.qualify_mutant_log(text, 1, 0)
        self.assertFalse(ok)
        self.assertTrue(any("CHECK_FAIL" in reason for reason in reasons), reasons)

    def test_mutant_unexpected_exit_rejected(self):
        text = "\n".join([
            "# DEEPEYE_FC_RUN width=1 kind=standalone",
            "# DEEPEYE_FC_CHECK_FAIL width=1 scenario=s phase=post detail",
            "# DEEPEYE_FC_FINISH width=1 status=FAIL",
        ]) + "\n"
        ok, _, reasons = runner.qualify_mutant_log(text, 1, 2)
        self.assertFalse(ok)
        self.assertTrue(any("exit" in reason for reason in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
