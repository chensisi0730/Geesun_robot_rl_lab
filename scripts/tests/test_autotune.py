from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import autotune  # noqa: E402


class AutotuneDiagnosisTest(unittest.TestCase):
    @staticmethod
    def _points(values: list[float]) -> list[tuple[int, float]]:
        return list(enumerate(values))

    def test_policy_step_ignores_wall_time_axis(self):
        tb = {
            "Train/mean_reward": [(1500, 1.0)],
            "Train/mean_reward/time": [(25000, 1.0)],
        }
        self.assertEqual(autotune._policy_step(tb), 1500)

    def test_combined_adverse_trends_are_degradation(self):
        first = [1.0] * 200
        last = [0.7] * 200
        tb = {
            "Train/mean_reward": self._points([10.0 * value for value in first + last]),
            "Metrics/base_velocity/error_vel_xy": self._points([0.2] * 200 + [0.25] * 200),
            "Metrics/base_velocity/error_vel_yaw": self._points([0.3] * 400),
            "Episode_Termination/time_out": self._points(first + last),
            "Episode_Termination/bad_orientation": self._points([0.01] * 400),
        }
        findings = autotune.diagnose(tb)
        self.assertTrue(findings["degrading"])
        self.assertIn("reward -30%", findings["degradation_reasons"])

    def test_single_noisy_curve_does_not_trigger_degradation(self):
        tb = {
            "Train/mean_reward": self._points([10.0] * 200 + [7.0] * 200),
            "Metrics/base_velocity/error_vel_xy": self._points([0.2] * 400),
            "Metrics/base_velocity/error_vel_yaw": self._points([0.3] * 400),
            "Episode_Termination/time_out": self._points([0.9] * 400),
            "Episode_Termination/bad_orientation": self._points([0.01] * 400),
        }
        self.assertFalse(autotune.diagnose(tb)["degrading"])

    def test_value_loss_divergence_is_degradation(self):
        tb = {
            "Train/mean_reward": self._points([10.0] * 400),
            "Metrics/base_velocity/error_vel_xy": self._points([0.2] * 400),
            "Metrics/base_velocity/error_vel_yaw": self._points([0.3] * 400),
            "Episode_Termination/time_out": self._points([0.9] * 400),
            "Episode_Termination/bad_orientation": self._points([0.01] * 400),
            "Loss/value_function": self._points([150.0] * 200),
        }
        findings = autotune.diagnose(tb)
        self.assertTrue(findings["value_diverged"])
        self.assertTrue(findings["degrading"])

    @mock.patch.object(autotune, "read_knob", return_value=8e-4)
    def test_value_divergence_reduces_learning_rate(self, _read_knob):
        findings = {
            "value_diverged": True,
            "value_loss_med": 150.0,
            "degrading": True,
            "degradation_reasons": ["value_loss median 150"],
            "plateau": False,
            "range_incomplete": True,
            "exploration_collapsed": False,
            "lr_pinned_frac": 0.0,
            "falls_rising": False,
            "yaw_stuck": False,
            "lin_stuck": False,
        }
        action = autotune.decide(findings, {"actions": []})
        self.assertEqual(action["knob"], "learning_rate")
        self.assertAlmostEqual(action["new"], 4e-4)


class AutotuneCooldownTest(unittest.TestCase):
    def test_fresh_run_does_not_inherit_old_iteration_cooldown(self):
        findings = {"step": 2000}
        state = {
            "actions": [{"run": "old-run", "status": "applied"}],
            "last_action_run": "old-run",
            "last_action_step": 100000,
            "last_action_ts": 1.0,
        }
        self.assertIsNone(autotune.cooldown_reason(findings, state, "fresh-run", now=20000.0))

    def test_same_run_keeps_iteration_cooldown(self):
        findings = {"step": 2000}
        state = {
            "actions": [{"run": "same-run", "status": "applied"}],
            "last_action_run": "same-run",
            "last_action_step": 1800,
            "last_action_ts": 1.0,
        }
        with mock.patch.object(autotune, "MIN_SECONDS_BETWEEN_ACTIONS", 0):
            self.assertEqual(
                autotune.cooldown_reason(findings, state, "same-run", now=20000.0),
                "iteration cooldown active",
            )


if __name__ == "__main__":
    unittest.main()
