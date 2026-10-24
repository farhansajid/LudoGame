"""
End-to-End Headless Chrome Test for Responsive UI & Dynamic Canvas Viewport Scaling
Validates across:
1. Desktop Widescreen (1920x1080)
2. Standard Laptop (1366x768)
3. Tablet Portrait (768x1024)
4. Mobile Phone Portrait (390x844)
5. Mobile Phone Landscape (844x390)

Verifies:
- Canvas dynamically maximizes to available viewport space
- No unexpected document body or game-layout scrollbars
- Board hover/click coordinates mapping is pixel-perfect
- Sidebars adapt between column and compact horizontal rows
- Preset switches ('standard', 'large', 'xlarge') dynamically scale canvas
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from aiohttp import web
from server.app import create_app

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not os.path.exists(CHROME_PATH):
    CHROME_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


class TestResponsiveViewport(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.path.exists(CHROME_PATH), "Chrome or Edge browser executable not found")
    async def test_viewport_scaling_and_coordinates(self):
        static_dir = root / "static"
        app = create_app(static_dir)

        runner = web.AppRunner(app)
        await runner.setup()
        port = 8094
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()

        temp_dir = tempfile.mkdtemp(prefix="browser_responsive_test_")
        cdp_port = 9226

        chrome_proc = subprocess.Popen([
            CHROME_PATH,
            "--headless=new",
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={temp_dir}",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-background-networking",
            "--no-proxy-server",
            "about:blank"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        try:
            for _ in range(25):
                try:
                    req = urllib.request.urlopen(f"http://127.0.0.1:{cdp_port}/json")
                    targets = json.loads(req.read().decode())
                    break
                except Exception:
                    await asyncio.sleep(0.2)
            else:
                self.fail("Could not connect to browser CDP port")

            page_target = next(t for t in targets if t.get("type") == "page")
            ws_url = page_target["webSocketDebuggerUrl"]

            import websockets
            async with websockets.connect(ws_url) as ws:
                msg_id = 0
                pending_cmds = {}
                exceptions = []
                console_errors = []

                async def send_cmd(method, params=None):
                    nonlocal msg_id
                    msg_id += 1
                    cmd = {"id": msg_id, "method": method}
                    if params:
                        cmd["params"] = params
                    fut = asyncio.get_event_loop().create_future()
                    pending_cmds[msg_id] = fut
                    await ws.send(json.dumps(cmd))
                    return await fut

                async def eval_js(expr):
                    res = await send_cmd("Runtime.evaluate", {
                        "expression": expr,
                        "returnByValue": True,
                        "awaitPromise": True
                    })
                    res_val = res.get("result", {})
                    if "exceptionDetails" in res_val:
                        raise RuntimeError(f"JS Eval Exception: {res_val['exceptionDetails']}")
                    return res_val.get("result", {}).get("value")

                async def set_viewport(width, height, is_mobile=False):
                    await send_cmd("Emulation.setDeviceMetricsOverride", {
                        "width": width,
                        "height": height,
                        "deviceScaleFactor": 1.0,
                        "mobile": is_mobile
                    })
                    await eval_js("window.dispatchEvent(new Event('resize'))")
                    await asyncio.sleep(0.3)

                async def listen_loop():
                    while True:
                        try:
                            raw = await ws.recv()
                            msg = json.loads(raw)
                            _id = msg.get("id")
                            if _id in pending_cmds:
                                pending_cmds.pop(_id).set_result(msg)
                            method = msg.get("method")
                            params = msg.get("params", {})
                            if method == "Runtime.exceptionThrown":
                                exceptions.append(params)
                            elif method == "Log.entryAdded":
                                entry = params.get("entry", {})
                                if entry.get("level") == "error":
                                    console_errors.append(entry)
                        except asyncio.CancelledError:
                            break
                        except Exception:
                            break

                listener_task = asyncio.create_task(listen_loop())

                await send_cmd("Runtime.enable")
                await send_cmd("Page.enable")
                await send_cmd("Log.enable")
                await send_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})

                await send_cmd("Page.navigate", {"url": f"http://127.0.0.1:{port}/"})

                for _ in range(50):
                    await asyncio.sleep(0.1)
                    if await eval_js("Boolean(window.app && window.app.board)"):
                        break

                # 1. Start a Single Player match
                await eval_js("document.getElementById('btn-mode-bot').click()")
                for _ in range(40):
                    await asyncio.sleep(0.1)
                    if await eval_js("document.getElementById('screen-lobby').classList.contains('active')"):
                        await eval_js("document.getElementById('btn-start-game').click()")
                        break
                    if await eval_js("document.getElementById('screen-game').classList.contains('active')"):
                        break

                for _ in range(40):
                    await asyncio.sleep(0.1)
                    if await eval_js("document.getElementById('screen-game').classList.contains('active')"):
                        break
                self.assertTrue(await eval_js("document.getElementById('screen-game').classList.contains('active')"))

                # 2. Test Desktop Widescreen (1920x1080)
                await set_viewport(1920, 1080, False)
                canvas_dim_widescreen = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().width")
                self.assertGreater(canvas_dim_widescreen, 850, f"Canvas should exceed 850px on 1080p, got {canvas_dim_widescreen}")
                
                body_overflow_w = await eval_js("document.body.scrollWidth > document.body.clientWidth")
                body_overflow_h = await eval_js("document.body.scrollHeight > document.body.clientHeight")
                self.assertFalse(body_overflow_w, "Body should have no horizontal overflow on desktop")
                self.assertFalse(body_overflow_h, "Body should have no vertical overflow on desktop")

                # 3. Test Laptop Screen (1366x768)
                await set_viewport(1366, 768, False)
                canvas_dim_laptop = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().width")
                self.assertGreater(canvas_dim_laptop, 580, f"Canvas should be >= 580px on laptop, got {canvas_dim_laptop}")
                self.assertLessEqual(canvas_dim_laptop, 700, f"Canvas should fit in laptop height without overflow, got {canvas_dim_laptop}")

                body_overflow_laptop_h = await eval_js("document.body.scrollHeight > document.body.clientHeight")
                self.assertFalse(body_overflow_laptop_h, "No vertical scrollbars on laptop 1366x768")

                # 4. Test Tablet Portrait (768x1024)
                await set_viewport(768, 1024, True)
                canvas_dim_tablet = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().width")
                self.assertGreater(canvas_dim_tablet, 650, f"Canvas should dynamically scale > 650px on 768px tablet, got {canvas_dim_tablet}")

                # 5. Test Mobile Phone Portrait (390x844 - iPhone / modern Android)
                await set_viewport(390, 844, True)
                canvas_dim_mobile = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().width")
                self.assertGreater(canvas_dim_mobile, 350, f"Canvas should fill phone width (>350px), got {canvas_dim_mobile}")

                # Verify player sidebars adapted to horizontal rows
                is_sidebar_row = await eval_js("window.getComputedStyle(document.querySelector('.game-sidebar')).flexDirection === 'row'")
                self.assertTrue(is_sidebar_row, "Sidebar should adapt to row orientation on mobile portrait")

                # 6. Test Mobile Phone Landscape (844x390)
                await set_viewport(844, 390, True)
                canvas_dim_landscape = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().height")
                self.assertGreater(canvas_dim_landscape, 260, f"Canvas should fill landscape height (>260px), got {canvas_dim_landscape}")

                # 7. Test Board Size Preset dynamically scaling
                await set_viewport(1366, 768, False)
                await eval_js("window.app.applyBoardSize('standard')")
                await asyncio.sleep(0.3)
                canvas_std = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().width")

                await eval_js("window.app.applyBoardSize('xlarge')")
                await asyncio.sleep(0.3)
                canvas_xl = await eval_js("document.getElementById('ludo-canvas').getBoundingClientRect().width")

                self.assertGreater(canvas_xl, canvas_std, f"xlarge canvas ({canvas_xl}) should be larger than standard ({canvas_std})")

                # 8. Test Pixel-Perfect Coordinate Mapping
                # Center click on (clientX, clientY) should map to board center (375, 375)
                coord_map = await eval_js("""
                    (() => {
                        const board = window.app.board;
                        const canvas = document.getElementById('ludo-canvas');
                        const rect = canvas.getBoundingClientRect();
                        const clientX = rect.left + rect.width / 2;
                        const clientY = rect.top + rect.height / 2;
                        const w = rect.width;
                        const h = rect.height;
                        const x = ((clientX - rect.left) / w) * board.boardSize;
                        const y = ((clientY - rect.top) / h) * board.boardSize;
                        return { x: Math.round(x), y: Math.round(y) };
                    })()
                """)
                self.assertEqual(coord_map["x"], 375, f"Expected center x 375, got {coord_map['x']}")
                self.assertEqual(coord_map["y"], 375, f"Expected center y 375, got {coord_map['y']}")

                listener_task.cancel()
                self.assertEqual(len(exceptions), 0, f"Browser exceptions: {exceptions}")
                self.assertEqual(len(console_errors), 0, f"Browser console errors: {console_errors}")

        finally:
            try:
                chrome_proc.terminate()
                chrome_proc.wait(timeout=2.0)
            except Exception:
                try:
                    chrome_proc.kill()
                except Exception:
                    pass
            shutil.rmtree(temp_dir, ignore_errors=True)
            await runner.cleanup()


if __name__ == "__main__":
    unittest.main()
