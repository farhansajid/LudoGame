"""
Empirical Challenge Test Suite: Render Deployment, Dynamic PORT Binding, Health, and CORS.
Tested by challenger_1.
"""

import os
import re
import sys
import unittest
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from main import parse_arguments
from server.app import create_app


class TestDynamicPortBinding(unittest.TestCase):
    """Stress-test and verify dynamic PORT environment binding and CLI overrides."""

    def setUp(self):
        self._orig_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._orig_env)

    def test_default_port_without_env_or_cli(self):
        os.environ.pop("PORT", None)
        args = parse_arguments([])
        self.assertEqual(args.port, 8080)
        self.assertEqual(args.host, "0.0.0.0")
        self.assertFalse(args.no_browser)

    def test_dynamic_port_from_env_render_mock(self):
        os.environ["PORT"] = "9451"
        args = parse_arguments([])
        self.assertEqual(args.port, 9451, "Server failed to bind to $env:PORT='9451'")

    def test_cli_override_takes_precedence_over_env_port(self):
        os.environ["PORT"] = "9451"
        args = parse_arguments(["--port", "8090"])
        self.assertEqual(args.port, 8090, "CLI argument --port did not take precedence over $PORT")

    def test_cli_override_with_custom_host_and_no_browser(self):
        os.environ["PORT"] = "7777"
        args = parse_arguments(["--host", "127.0.0.1", "--port", "5000", "--no-browser"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 5000)
        self.assertTrue(args.no_browser)


class TestRenderBlueprintSpecification(unittest.TestCase):
    """Verify render.yaml adheres strictly to Render blueprint standards."""

    def test_render_yaml_validity(self):
        project_root = Path(__file__).resolve().parent.parent
        yaml_path = project_root / "render.yaml"
        self.assertTrue(yaml_path.exists(), "render.yaml does not exist in project root")

        content = yaml_path.read_text(encoding="utf-8")
        self.assertIn("services:", content)
        self.assertIn("type: web", content)
        self.assertIn("name: royal-ludo", content)
        self.assertIn("runtime: python", content)
        self.assertIn("branch: main", content)
        self.assertIn("buildCommand: pip install -r requirements.txt", content)
        self.assertIn("startCommand: python main.py --host 0.0.0.0 --no-browser", content)
        self.assertIn("healthCheckPath: /health", content)
        self.assertIn("PYTHON_VERSION", content)
        self.assertIn("3.11", content)
        self.assertIn("RENDER", content)


class TestHealthAndCORSEndpoints(AioHTTPTestCase):
    """Verify /health endpoint and CORS headers for mobile WebView compatibility."""

    async def get_application(self):
        project_root = Path(__file__).resolve().parent.parent
        static_dir = project_root / "static"
        return create_app(static_dir)

    @unittest_run_loop
    async def test_health_check_endpoint_status_and_body(self):
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200, f"Expected HTTP 200 on /health, got {resp.status}")
        self.assertEqual(resp.content_type, "application/json")
        body = await resp.json()
        self.assertEqual(body.get("status"), "healthy")
        self.assertEqual(body.get("service"), "royal-ludo")
        # CORS check on health check
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    @unittest_run_loop
    async def test_cors_options_preflight(self):
        headers = {
            "Origin": "capacitor://localhost",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        }
        resp = await self.client.request("OPTIONS", "/api/create_room", headers=headers)
        self.assertEqual(resp.status, 204)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))
        self.assertIn("Content-Type", resp.headers.get("Access-Control-Allow-Headers", ""))

    @unittest_run_loop
    async def test_cors_on_api_status(self):
        headers = {"Origin": "capacitor://localhost"}
        resp = await self.client.request("GET", "/api/status", headers=headers)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        body = await resp.json()
        self.assertEqual(body.get("status"), "online")
        self.assertIn("active_rooms", body)
        self.assertIn("local_ip", body)

    @unittest_run_loop
    async def test_cors_on_api_create_room(self):
        headers = {
            "Origin": "capacitor://localhost",
            "Content-Type": "application/json"
        }
        payload = {"mode": "solo", "player_count": 4}
        resp = await self.client.request("POST", "/api/create_room", headers=headers, json=payload)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        body = await resp.json()
        self.assertIn("room_id", body)
        self.assertEqual(body.get("mode"), "solo")


if __name__ == "__main__":
    unittest.main()
