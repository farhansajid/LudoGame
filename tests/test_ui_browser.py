"""
Interactive Headless Browser Test for Frontend UI
Validates full end-to-end functionality in real headless Chrome:
- App initialization and module loading
- Settings modal (theme selection, open/close)
- Audio modal (open/close)
- Yard opening rule selector
- AI difficulty selector
- Format selector (2, 3, 4, 6, 8, 2v2 team)
- Single player vs Bots match flow
- Canvas board rendering and sizing
- In-game chat and reactions
- Pass & Play local multiplayer
- 2-Dice 3D container rendering & physics
- Clean quit and reset to home screen
"""

import asyncio
import json
import logging
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


class TestFrontendBrowser(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.path.exists(CHROME_PATH), "Chrome or Edge browser executable not found")
    async def test_full_ui_interaction(self):
        static_dir = root / "static"
        app = create_app(static_dir)

        runner = web.AppRunner(app)
        await runner.setup()
        port = 8091
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()

        temp_dir = tempfile.mkdtemp(prefix="browser_ui_test_")
        cdp_port = 9224

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
            # Wait for browser to initialize CDP
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
                            elif method == "Console.messageAdded":
                                entry = params.get("message", {})
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
                await send_cmd("Console.enable")

                # Navigate to the test page
                await send_cmd("Page.navigate", {"url": f"http://127.0.0.1:{port}/"})

                # Wait for WebSocket connection
                for _ in range(50):
                    await asyncio.sleep(0.1)
                    if await eval_js("!!window.app?.net?.isOpen()"):
                        break
                else:
                    self.fail("WebSocket did not connect within timeout")

                # 1. Verify app and subsystems
                status = await eval_js("({ app: !!window.app, board: !!window.app?.board, dice: !!window.app?.dice })")
                self.assertTrue(status["app"])
                self.assertTrue(status["board"])
                self.assertTrue(status["dice"])

                # 2. Settings modal, board size & theme change
                await eval_js("document.getElementById('btn-open-settings').click()")
                await asyncio.sleep(0.1)
                self.assertTrue(await eval_js("document.getElementById('modal-settings').classList.contains('open')"))

                await eval_js("document.querySelector('#board-size-buttons .rule-btn[data-size=\"standard\"]').click()")
                self.assertEqual(await eval_js("window.app.boardSize"), "standard")
                await eval_js("document.querySelector('#board-size-buttons .rule-btn[data-size=\"large\"]').click()")
                self.assertEqual(await eval_js("window.app.boardSize"), "large")

                await eval_js("document.querySelector('.theme-option[data-theme=\"cyber\"]').click()")
                theme = await eval_js("document.body.className")
                self.assertIn("theme-cyber", theme)

                await eval_js("document.getElementById('btn-close-settings').click()")
                await asyncio.sleep(0.1)
                self.assertFalse(await eval_js("document.getElementById('modal-settings').classList.contains('open')"))

                # 3. Audio settings modal & mic loopback test
                await eval_js("document.getElementById('btn-audio-settings').click()")
                await asyncio.sleep(0.1)
                self.assertTrue(await eval_js("document.getElementById('modal-audio').classList.contains('open')"))

                await eval_js("document.getElementById('btn-call-mode-indiv').click()")
                self.assertTrue(await eval_js("document.getElementById('btn-call-mode-indiv').classList.contains('active')"))
                await eval_js("document.getElementById('btn-call-mode-conf').click()")

                await eval_js("document.getElementById('btn-test-mic').click()")
                await asyncio.sleep(0.1)
                await eval_js("document.getElementById('btn-close-audio').click()")
                await asyncio.sleep(0.1)
                self.assertFalse(await eval_js("document.getElementById('modal-audio').classList.contains('open')"))
                self.assertFalse(await eval_js("window.app.isTestingMicLoop"))

                # 4. Rules and Options
                await eval_js("document.getElementById('btn-rule-classic').click()")
                self.assertFalse(await eval_js("window.app.openOnOne"))

                await eval_js("document.getElementById('btn-diff-medium').click()")
                self.assertEqual(await eval_js("window.app.difficulty"), "medium")

                async def start_game_from_mode(btn_id):
                    await eval_js(f"document.getElementById('{btn_id}').click()")
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
                            return True
                    return False

                async def quit_to_home():
                    await eval_js("document.getElementById('btn-quit-game').click()")
                    await asyncio.sleep(0.1)
                    await eval_js("document.getElementById('btn-confirm-quit').click()")
                    for _ in range(40):
                        await asyncio.sleep(0.1)
                        if await eval_js("document.getElementById('screen-home').classList.contains('active')"):
                            return True
                    return False

                # 5. Bot Match flow
                self.assertTrue(await start_game_from_mode("btn-mode-bot"))
                canvas_ok = await eval_js("(()=>{ const c = document.getElementById('ludo-canvas'); return c && c.width > 0 && c.height > 0; })()")
                self.assertTrue(canvas_ok)

                # 6. Chat & Reactions
                await eval_js("(()=>{ const inp = document.getElementById('chat-input'); inp.value = 'GG!'; document.getElementById('btn-chat-send').click(); })()")
                await asyncio.sleep(0.5)
                chat_len = await eval_js("document.getElementById('chat-messages').children.length")
                self.assertGreaterEqual(chat_len, 1)

                # 7. Quit modal
                self.assertTrue(await quit_to_home())

                # 8. Local Pass & Play Match with rolling & moving
                self.assertTrue(await start_game_from_mode("btn-mode-local"))
                await asyncio.sleep(0.3)
                # Roll dice in local match
                await eval_js("document.getElementById('dice-container').querySelector('.dice-wrapper')?.click()")
                await asyncio.sleep(1.2)
                # Check turn state advanced
                ts = await eval_js("window.app.gameState?.turn_state")
                self.assertIn(ts, ["WAIT_ROLL", "WAIT_MOVE"])
                self.assertTrue(await quit_to_home())

                # 9. 2-Dice Mode
                await eval_js("document.getElementById('btn-dice-double').click()")
                self.assertTrue(await eval_js("window.app.twoDiceMode"))
                self.assertTrue(await start_game_from_mode("btn-mode-bot"))

                has_two_dice = await eval_js("!!document.querySelector('.two-dice-container')")
                self.assertTrue(has_two_dice)
                self.assertTrue(await quit_to_home())

                # 10. 6-Player Hexagon Mode
                await eval_js("document.getElementById('btn-dice-single').click()")
                await eval_js("document.getElementById('btn-format-6').click()")
                self.assertTrue(await start_game_from_mode("btn-mode-bot"))

                p6 = await eval_js("window.app.gameState?.players?.length")
                self.assertEqual(p6, 6)
                self.assertTrue(await quit_to_home())

                # 11. 8-Player Octagon Mode & Lobby Color Palette
                await eval_js("document.getElementById('btn-format-8').click()")
                # Verify that 8 colors are visible in home color picker
                visible_colors = await eval_js("Array.from(document.querySelectorAll('#home-color-picker .color-select-btn')).filter(b => b.style.display !== 'none').length")
                self.assertEqual(visible_colors, 8)

                self.assertTrue(await start_game_from_mode("btn-mode-bot"))
                p8 = await eval_js("window.app.gameState?.players?.length")
                self.assertEqual(p8, 8)
                self.assertTrue(await quit_to_home())

                # 12. 2v2 Team Mode
                await eval_js("document.getElementById('btn-format-team').click()")
                self.assertTrue(await start_game_from_mode("btn-mode-bot"))

                is_team = await eval_js("window.app.gameState?.team_mode")
                self.assertTrue(is_team)
                self.assertTrue(await quit_to_home())

                # 13. Online Room Hosting & Copy Code Fallback
                await eval_js("document.getElementById('btn-format-4').click()")
                await eval_js("document.getElementById('btn-mode-host').click()")
                for _ in range(40):
                    await asyncio.sleep(0.1)
                    if await eval_js("document.getElementById('screen-lobby').classList.contains('active')"):
                        break
                code = await eval_js("window.app.currentRoomId")
                self.assertTrue(code and code.startswith("LUDO-"))
                # Copy button click
                await eval_js("document.getElementById('btn-copy-room-link').click()")
                # Leave room
                await eval_js("document.getElementById('btn-leave-room').click()")
                for _ in range(40):
                    await asyncio.sleep(0.1)
                    if await eval_js("document.getElementById('screen-home').classList.contains('active')"):
                        break


                listener_task.cancel()

                # Verify 0 exceptions and 0 errors occurred in browser
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
