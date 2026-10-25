import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from glide_core.hardware.thermal_governor import (
    HardwareThermalGovernor,
    _NvencGate,
    _log_target,
    nvenc_slot,
)


class TestThermalGovernorStress(unittest.TestCase):
    """Stress tests and adversarial verification for HardwareThermalGovernor."""

    def setUp(self):
        self.governor = HardwareThermalGovernor(is_laptop=False)

    def test_extreme_temperatures_escalating_breathers_nvenc(self):
        """Stress-test pace_before_nvenc across extreme temperatures: 75°C, 82°C, 86°C, 90°C."""
        logs = []
        log_cb = lambda msg: logs.append(msg)

        # We mock time.sleep to record sleep duration without slowing down the test run
        with patch("time.sleep") as mock_sleep:
            # 75°C: Below 80°C -> No pause
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(75.0, 95.0)):
                pause_75 = self.governor.pace_before_nvenc(log_callback=log_cb, completed_count=15)
                self.assertEqual(pause_75, 0.0)
                mock_sleep.assert_not_called()

            # 82°C: In [80.0, 84.0) -> 0.15s pause
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(82.0, 98.0)):
                pause_82 = self.governor.pace_before_nvenc(log_callback=log_cb, completed_count=15)
                self.assertEqual(pause_82, 0.15)
                mock_sleep.assert_called_with(0.15)
                mock_sleep.reset_mock()

            # 86°C: In [84.0, 88.0) -> 0.6s pause
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(86.0, 99.0)):
                pause_86 = self.governor.pace_before_nvenc(log_callback=log_cb, completed_count=15)
                self.assertEqual(pause_86, 0.6)
                mock_sleep.assert_called_with(0.6)
                mock_sleep.reset_mock()

            # 90°C: >= 88.0°C (Critical) -> 2.0s pause
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(90.0, 100.0)):
                pause_90 = self.governor.pace_before_nvenc(log_callback=log_cb, completed_count=15)
                self.assertEqual(pause_90, 2.0)
                mock_sleep.assert_called_with(2.0)

        # Verify strict escalating hierarchy
        self.assertLess(pause_75, pause_82)
        self.assertLess(pause_82, pause_86)
        self.assertLess(pause_86, pause_90)
        self.assertEqual((pause_75, pause_82, pause_86, pause_90), (0.0, 0.15, 0.6, 2.0))

        # Check critical zone log
        critical_logs = [m for m in logs if "Zona Crítica" in m and "2.0s" in m]
        self.assertTrue(len(critical_logs) >= 1, "Expected critical zone log at 90°C")

        # Check summary metrics
        summary = self.governor.get_summary()
        self.assertEqual(summary["thermal_interventions"], 3)
        self.assertAlmostEqual(summary["total_cooldown_seconds"], 0.15 + 0.6 + 2.0, places=2)

    def test_extreme_temperatures_escalating_breathers_chunk(self):
        """Stress-test pace_before_chunk across extreme temperatures: 75°C, 82°C, 86°C, 90°C."""
        logs = []
        log_cb = lambda msg: logs.append(msg)

        with patch("time.sleep") as mock_sleep:
            # 75°C: Below 78°C -> 0.0s
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(75.0, 95.0)):
                pause_75 = self.governor.pace_before_chunk(0, 10, log_cb)
                self.assertEqual(pause_75, 0.0)
                mock_sleep.assert_not_called()

            # 82°C: In [82.0, 87.0) -> 0.8s
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(82.0, 98.0)):
                pause_82 = self.governor.pace_before_chunk(1, 10, log_cb)
                self.assertEqual(pause_82, 0.8)
                mock_sleep.assert_called_with(0.8)
                mock_sleep.reset_mock()

            # 86°C: In [82.0, 87.0) -> 0.8s
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(86.0, 99.0)):
                pause_86 = self.governor.pace_before_chunk(2, 10, log_cb)
                self.assertEqual(pause_86, 0.8)
                mock_sleep.assert_called_with(0.8)
                mock_sleep.reset_mock()

            # 90°C: >= 87.0°C (Critical) -> 2.5s
            with patch.object(self.governor, "query_gpu_telemetry", return_value=(90.0, 100.0)):
                pause_90 = self.governor.pace_before_chunk(3, 10, log_cb)
                self.assertEqual(pause_90, 2.5)
                mock_sleep.assert_called_with(2.5)

        # Verify escalating order
        self.assertLess(pause_75, pause_82)
        self.assertEqual(pause_82, pause_86)
        self.assertLess(pause_86, pause_90)
        self.assertEqual((pause_75, pause_82, pause_86, pause_90), (0.0, 0.8, 0.8, 2.5))

    def test_non_nvidia_simulation_laptop_vs_non_laptop(self):
        """Stress-test non-NVIDIA simulation (temp <= 0.0) on is_laptop=True vs is_laptop=False."""
        laptop_gov = HardwareThermalGovernor(is_laptop=True)
        desktop_gov = HardwareThermalGovernor(is_laptop=False)

        # 1. Non-NVIDIA simulation: temp = 0.0 (e.g. nvidia-smi missing or integrated graphics)
        for missing_temp in (0.0, -1.0, -10.0):
            with patch.object(laptop_gov, "query_gpu_telemetry", return_value=(missing_temp, 0.0)):
                with patch("time.sleep") as mock_sleep:
                    logs = []
                    p_nvenc = laptop_gov.pace_before_nvenc(log_callback=lambda m: logs.append(m))
                    self.assertEqual(p_nvenc, 0.25)
                    mock_sleep.assert_called_with(0.25)
                    self.assertTrue(any("0.25s" in m and "Dispositivo móvel/laptop" in m for m in logs))

                    mock_sleep.reset_mock()
                    logs.clear()
                    p_chunk = laptop_gov.pace_before_chunk(chunk_idx=0, total_chunks=5, log_callback=lambda m: logs.append(m))
                    self.assertEqual(p_chunk, 0.25)
                    mock_sleep.assert_called_with(0.25)
                    self.assertTrue(any("0.25s" in m and "Dispositivo móvel/laptop" in m for m in logs))

            # On desktop (is_laptop=False), missing telemetry should NOT cause unnecessary pacing
            with patch.object(desktop_gov, "query_gpu_telemetry", return_value=(missing_temp, 0.0)):
                with patch("time.sleep") as mock_sleep:
                    p_nvenc_d = desktop_gov.pace_before_nvenc()
                    self.assertEqual(p_nvenc_d, 0.0)
                    p_chunk_d = desktop_gov.pace_before_chunk(0, 5)
                    self.assertEqual(p_chunk_d, 0.0)
                    mock_sleep.assert_not_called()

    def test_target_attribute_laptop_fallback_inference(self):
        """Test fallback inference when governor is_laptop is False/None but target specifies laptop."""
        gov = HardwareThermalGovernor(is_laptop=False)

        class MockJob:
            is_laptop = True

        class MockJobBudget:
            budget = {"is_laptop": True}

        with patch.object(gov, "query_gpu_telemetry", return_value=(0.0, 0.0)):
            with patch("time.sleep"):
                # Inherits from target.is_laptop
                p1 = gov.pace_before_nvenc(target=MockJob())
                self.assertEqual(p1, 0.25)

                # Inherits from target.budget['is_laptop']
                p2 = gov.pace_before_chunk(MockJobBudget(), 0, 4)
                self.assertEqual(p2, 0.25)

                # Explicit non-laptop target does not activate fallback
                class MockDesktopJob:
                    is_laptop = False

                p3 = gov.pace_before_nvenc(target=MockDesktopJob())
                self.assertEqual(p3, 0.0)

    def test_boundary_temperature_transitions(self):
        """Adversarially probe precise boundary conditions around float thresholds."""
        gov = HardwareThermalGovernor(is_laptop=False)

        with patch("time.sleep"):
            # NVENC boundary: 79.9 vs 80.0
            with patch.object(gov, "query_gpu_telemetry", return_value=(79.9, 50.0)):
                self.assertEqual(gov.pace_before_nvenc(), 0.0)
            with patch.object(gov, "query_gpu_telemetry", return_value=(80.0, 50.0)):
                self.assertEqual(gov.pace_before_nvenc(), 0.15)

            # NVENC boundary: 83.9 vs 84.0
            with patch.object(gov, "query_gpu_telemetry", return_value=(83.9, 50.0)):
                self.assertEqual(gov.pace_before_nvenc(), 0.15)
            with patch.object(gov, "query_gpu_telemetry", return_value=(84.0, 50.0)):
                self.assertEqual(gov.pace_before_nvenc(), 0.6)

            # NVENC boundary: 87.9 vs 88.0
            with patch.object(gov, "query_gpu_telemetry", return_value=(87.9, 50.0)):
                self.assertEqual(gov.pace_before_nvenc(), 0.6)
            with patch.object(gov, "query_gpu_telemetry", return_value=(88.0, 50.0)):
                self.assertEqual(gov.pace_before_nvenc(), 2.0)

            # Chunk boundary: 77.9 vs 78.0
            with patch.object(gov, "query_gpu_telemetry", return_value=(77.9, 50.0)):
                self.assertEqual(gov.pace_before_chunk(0, 1), 0.0)
            with patch.object(gov, "query_gpu_telemetry", return_value=(78.0, 50.0)):
                self.assertEqual(gov.pace_before_chunk(0, 1), 0.25)

            # Chunk boundary: 81.9 vs 82.0
            with patch.object(gov, "query_gpu_telemetry", return_value=(81.9, 50.0)):
                self.assertEqual(gov.pace_before_chunk(0, 1), 0.25)
            with patch.object(gov, "query_gpu_telemetry", return_value=(82.0, 50.0)):
                self.assertEqual(gov.pace_before_chunk(0, 1), 0.8)

            # Chunk boundary: 86.9 vs 87.0
            with patch.object(gov, "query_gpu_telemetry", return_value=(86.9, 50.0)):
                self.assertEqual(gov.pace_before_chunk(0, 1), 0.8)
            with patch.object(gov, "query_gpu_telemetry", return_value=(87.0, 50.0)):
                self.assertEqual(gov.pace_before_chunk(0, 1), 2.5)

            # Extreme thermal runaway: 105.0°C
            with patch.object(gov, "query_gpu_telemetry", return_value=(105.0, 100.0)):
                self.assertEqual(gov.pace_before_nvenc(), 2.0)
                self.assertEqual(gov.pace_before_chunk(0, 1), 2.5)

    def test_concurrent_stress_under_thermal_pressure(self):
        """Stress-test thread-safety under multi-threaded rapid access."""
        gov = HardwareThermalGovernor(is_laptop=True)
        errors = []

        def worker(thread_id: int):
            try:
                for i in range(25):
                    temp = 75.0 + (i % 18)  # 75 to 92 °C
                    with patch.object(gov, "query_gpu_telemetry", return_value=(temp, 90.0)):
                        with patch("time.sleep"):
                            gov.pace_before_nvenc(completed_count=i)
                            gov.pace_before_chunk(i, 25)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors encountered: {errors}")
        summary = gov.get_summary()
        self.assertGreater(summary["thermal_interventions"], 0)
        self.assertGreater(summary["total_cooldown_seconds"], 0)

    def test_nvenc_gate_concurrency_and_cleanup(self):
        """Verify _NvencGate semaphore behavior and clean release under exceptions."""
        gov = HardwareThermalGovernor(is_laptop=False)
        gate = _NvencGate(governor=gov, max_sessions=2)

        # 1. Acquire up to limit
        with patch.object(gov, "pace_before_nvenc", return_value=0.0):
            gate.acquire()
            self.assertEqual(gate.active, 1)
            gate.acquire()
            self.assertEqual(gate.active, 2)

            # Release
            gate.release()
            self.assertEqual(gate.active, 1)
            gate.release()
            self.assertEqual(gate.active, 0)

        # 2. nvenc_slot context manager safety on exception
        try:
            with nvenc_slot():
                self.assertEqual(gate.active, 0)  # Uses global NVENC_GATE
                raise ValueError("Simulated render crash")
        except ValueError:
            pass
        # Ensure slot didn't leak
        from glide_core.hardware.thermal_governor import NVENC_GATE
        self.assertEqual(NVENC_GATE.active, 0)

    def test_empirical_real_clock_pacing(self):
        """Empirically measure real wall-clock delay during 0.25s preventative fallback."""
        gov = HardwareThermalGovernor(is_laptop=True)
        with patch.object(gov, "query_gpu_telemetry", return_value=(0.0, 0.0)):
            t0 = time.perf_counter()
            p = gov.pace_before_nvenc()
            elapsed = time.perf_counter() - t0
            self.assertEqual(p, 0.25)
            self.assertGreaterEqual(elapsed, 0.23, "Real delay should be at least ~0.23s")
            self.assertLess(elapsed, 0.40, "Real delay should not exceed 0.40s")


if __name__ == "__main__":
    unittest.main()
