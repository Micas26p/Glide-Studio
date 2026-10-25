import json
import time
import unittest
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from desktop_app import DesktopRuntime, APP_VERSION


class TestDesktopSmokeStress(unittest.TestCase):
    """Adversarial stress and latency verification for desktop runtime and all 14 API routes."""

    @classmethod
    def setUpClass(cls):
        cls.runtime = DesktopRuntime()
        cls.runtime.start()
        cls.base_url = cls.runtime.base_url
        cls.routes = [
            "/api/health",
            "/api/config",
            "/api/cta-assets",
            "/",
            "/favicon.ico",
            "/static/app.js",
            "/static/modules/runtime-config.js",
            "/static/style.css",
            "/assets/glide_studio_icon_256.png",
            "/assets/glide_studio.ico",
            "/assets/glide_studio_icon_32.png",
            "/assets/glide_studio_icon_48.png",
            "/assets/glide_studio_icon.png",
            "/assets/site.webmanifest",
        ]

    @classmethod
    def tearDownClass(cls):
        cls.runtime.stop_and_wait()

    def test_all_14_routes_respond_200_within_strict_timeouts(self):
        """Verify each of the 14 routes returns HTTP 200 within strict timeouts (cold < 5s, warm < 100ms)."""
        # Pass 1: Cold requests (first access, media probing for cta-assets)
        cold_latencies = {}
        for route in self.routes:
            url = self.base_url + route
            t0 = time.perf_counter()
            with urllib.request.urlopen(url, timeout=10.0) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                content = resp.read()
                cold_latencies[route] = elapsed_ms
                self.assertEqual(resp.status, 200, f"Route {route} failed with HTTP {resp.status}")
                self.assertGreater(len(content), 0, f"Route {route} returned empty body")
                # Cold timeout assertion: must respond within 5000ms
                self.assertLess(
                    elapsed_ms,
                    5000.0,
                    f"Route {route} exceeded cold timeout: {elapsed_ms:.2f}ms >= 5000ms",
                )

        # Pass 2: Warm requests (cached state, steady-state runtime performance)
        warm_latencies = {}
        for route in self.routes:
            url = self.base_url + route
            t0 = time.perf_counter()
            with urllib.request.urlopen(url, timeout=5.0) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                content = resp.read()
                warm_latencies[route] = elapsed_ms
                self.assertEqual(resp.status, 200)
                # Warm timeout assertion: every single route must respond in < 100ms
                self.assertLess(
                    elapsed_ms,
                    100.0,
                    f"Route {route} exceeded warm timeout: {elapsed_ms:.2f}ms >= 100ms",
                )

        avg_warm_latency = sum(warm_latencies.values()) / len(warm_latencies)
        self.assertLess(avg_warm_latency, 35.0, f"Average warm latency too high: {avg_warm_latency:.2f}ms")

    def test_api_health_yunet_metadata(self):
        """Verify /api/health reports OpenCV YuNet active, valid, and error-free."""
        url = self.base_url + "/api/health"
        with urllib.request.urlopen(url, timeout=3.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))

        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("version"), APP_VERSION)

        yunet = data.get("visual_face_detector")
        self.assertIsInstance(yunet, dict)
        self.assertEqual(yunet.get("engine"), "opencv_yunet")
        self.assertEqual(yunet.get("model"), "face_detection_yunet_2023mar.onnx")
        self.assertTrue(yunet.get("model_available"))
        self.assertTrue(yunet.get("model_valid"))
        self.assertGreaterEqual(yunet.get("model_size", 0), 100_000)
        self.assertTrue(yunet.get("runtime_available"))
        self.assertTrue(yunet.get("active"))
        self.assertEqual(yunet.get("runtime_error"), "")

    def test_burst_concurrency_stress(self):
        """Adversarial burst concurrency stress test: 50 requests across 10 threads."""
        request_count = 50
        concurrency = 10
        route_list = [self.routes[i % len(self.routes)] for i in range(request_count)]

        latencies = []
        errors = []

        def make_req(path: str):
            url = self.base_url + path
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(url, timeout=5.0) as resp:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    if resp.status != 200:
                        errors.append(f"{path}: status {resp.status}")
                    latencies.append(elapsed_ms)
            except Exception as exc:
                errors.append(f"{path}: exception {exc}")

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(make_req, r) for r in route_list]
            for f in as_completed(futures):
                f.result()

        self.assertEqual(errors, [], f"Burst concurrency encountered errors: {errors}")
        self.assertEqual(len(latencies), request_count)

        min_lat = min(latencies)
        max_lat = max(latencies)
        avg_lat = sum(latencies) / len(latencies)
        p95_lat = sorted(latencies)[int(0.95 * len(latencies))]

        # Even under concurrent load, p95 must be under 500ms
        self.assertLess(p95_lat, 500.0, f"p95 latency under burst load too high: {p95_lat:.2f}ms")


if __name__ == "__main__":
    unittest.main()
