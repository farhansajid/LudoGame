"""
Integration Tests for Server Endpoints
Validates:
- GET /api/status returns local IP and online status
- POST /api/create_room creates a room
- GET /api/room_info retrieves room info
"""

import unittest
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase
from server.app import create_app, ROOM_MGR_KEY


class TestServerApp(AioHTTPTestCase):
    async def get_application(self):
        static_dir = Path(__file__).parent.parent / "static"
        return create_app(static_dir)

    async def test_health_check(self):
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "royal-ludo")
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    async def test_api_status(self):
        resp = await self.client.request("GET", "/api/status")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("local_ip", data)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")

    async def test_cors_options_preflight(self):
        resp = await self.client.request("OPTIONS", "/api/create_room")
        self.assertEqual(resp.status, 204)
        self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))

    async def test_api_create_room(self):
        resp = await self.client.request(
            "POST",
            "/api/create_room",
            json={"mode": "online", "player_count": 4, "room_id": "TEST12"}
        )
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data["room_id"], "TEST12")
        self.assertEqual(data["mode"], "online")

        # Now test room_info
        info_resp = await self.client.request("GET", "/api/room_info?room_id=TEST12")
        self.assertEqual(info_resp.status, 200)
        info_data = await info_resp.json()
        self.assertEqual(info_data["room_id"], "TEST12")
        self.assertEqual(info_data["status"], "LOBBY")
        self.assertTrue(info_data["open_on_one"])

    async def test_websocket_game_and_audio(self):
        ws = await self.client.ws_connect("/ws")
        # 1. Join Room
        await ws.send_json({
            "type": "join_room",
            "room_id": "WS-TEST",
            "name": "Tester",
            "mode": "single",
            "player_count": 4
        })

        # Expect room_joined response
        msg = await ws.receive_json()
        self.assertEqual(msg["type"], "room_joined")
        self.assertEqual(msg["room_id"], "WS-TEST")
        session_id = msg["session_id"]

        # Expect game_state broadcast
        state_msg = await ws.receive_json()
        self.assertEqual(state_msg["type"], "game_state")
        self.assertTrue(state_msg["open_on_one"])

        # 2. Test Audio Join
        await ws.send_json({
            "type": "audio_join",
            "room_id": "WS-TEST",
            "player_name": "Tester",
            "color": "red"
        })
        audio_roster_msg = await ws.receive_json()
        self.assertEqual(audio_roster_msg["type"], "audio_roster")

        # 3. Test Binary Audio Relay
        pcm_frame = b"\x00\x10\x20\x30\x40"
        await ws.send_bytes(pcm_frame)

        # 4. Close clean
        await ws.close()

    async def test_websocket_update_rules(self):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "type": "join_room",
            "room_id": "RULE-TEST",
            "name": "HostPlayer",
            "mode": "single",
            "player_count": 4,
            "open_on_one": False
        })
        joined = await ws.receive_json()
        self.assertEqual(joined["type"], "room_joined")

        init_state = await ws.receive_json()
        self.assertEqual(init_state["type"], "game_state")
        self.assertFalse(init_state["open_on_one"])

        # Now update rule to True
        await ws.send_json({
            "type": "update_rules",
            "open_on_one": True,
            "team_mode": True
        })
        updated_state = await ws.receive_json()
        self.assertEqual(updated_state["type"], "game_state")
        self.assertTrue(updated_state["open_on_one"])
        self.assertTrue(updated_state["team_mode"])

        await ws.close()

    async def test_update_rules_during_wait_move_no_deadlock(self):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "type": "join_room",
            "room_id": "DEADLOCK-TEST",
            "name": "HostPlayer",
            "mode": "single",
            "player_count": 4,
            "open_on_one": True
        })
        await ws.receive_json()  # room_joined
        await ws.receive_json()  # game_state

        # Start game
        await ws.send_json({"type": "start_game"})
        await ws.receive_json()  # game_started
        start_state = await ws.receive_json()  # game_state

        room_mgr = self.app[ROOM_MGR_KEY]
        room = room_mgr.get_room("DEADLOCK-TEST")
        self.assertIsNotNone(room)

        # Force WAIT_MOVE on roll of 1 with all tokens in yard
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_value = 1

        # Now update rules to classic (open_on_one = False) while in WAIT_MOVE
        await ws.send_json({
            "type": "update_rules",
            "open_on_one": False
        })
        state_after = await ws.receive_json()
        self.assertEqual(state_after["type"], "game_state")
        # Turn must have auto-advanced instead of freezing in WAIT_MOVE with 0 valid moves
        self.assertEqual(room.game.turn_state, "WAIT_ROLL")
        self.assertIsNone(room.game.dice_value)

        await ws.close()

    async def test_create_room_api_then_join_ws_preserves_rules(self):
        # Create room with team mode via REST API
        resp = await self.client.request(
            "POST",
            "/api/create_room",
            json={
                "room_id": "TEAM-PRESET",
                "mode": "online",
                "player_count": 4,
                "open_on_one": True,
                "team_mode": True
            }
        )
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertTrue(data["team_mode"])

        # First player joins the pre-created room over WS
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "type": "join_room",
            "room_id": "TEAM-PRESET",
            "name": "TeamHost",
            "team_mode": True,
            "open_on_one": True
        })
        joined = await ws.receive_json()
        self.assertEqual(joined["type"], "room_joined")
        self.assertTrue(joined["is_host"])
        state = await ws.receive_json()
        self.assertEqual(state["type"], "game_state")
        self.assertTrue(state["team_mode"])
        self.assertTrue(state["open_on_one"])
        await ws.close()

    async def test_update_rules_during_wait_move_triggers_bot_turn(self):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "type": "join_room",
            "room_id": "BOT-TRIGGER-TEST",
            "name": "HostPlayer",
            "mode": "single",
            "player_count": 4,
            "open_on_one": True
        })
        await ws.receive_json()  # room_joined
        await ws.receive_json()  # game_state

        await ws.send_json({"type": "start_game"})
        await ws.receive_json()  # game_started
        await ws.receive_json()  # game_state

        room_mgr = self.app[ROOM_MGR_KEY]
        room = room_mgr.get_room("BOT-TRIGGER-TEST")

        # Set turn to Red (human) in WAIT_MOVE on roll of 1
        room.game.current_player_index = 0
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_value = 1

        # Turn off open_on_one -> auto-advances turn to Green (which is a bot!)
        await ws.send_json({
            "type": "update_rules",
            "open_on_one": False
        })
        state = await ws.receive_json()
        self.assertEqual(state["type"], "game_state")
        # Ensure bot task was scheduled and is not None
        self.assertIsNotNone(room.bot_task)
        await ws.close()

    async def test_websocket_two_dice_and_six_player_match(self):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "type": "join_room",
            "room_id": "HEX-2DICE",
            "name": "HexPlayer",
            "mode": "local",
            "player_count": 6,
            "two_dice_mode": True,
            "open_on_one": True
        })
        joined = await ws.receive_json()
        self.assertEqual(joined["type"], "room_joined")

        state1 = await ws.receive_json()
        self.assertEqual(state1["type"], "game_state")
        self.assertEqual(state1["max_players"], 6)
        self.assertTrue(state1["two_dice_mode"])

        # Start game
        await ws.send_json({"type": "start_game"})
        started = await ws.receive_json()
        self.assertEqual(started["type"], "game_started")

        state2 = await ws.receive_json()
        self.assertEqual(state2["type"], "game_state")
        self.assertEqual(len(state2["players"]), 6)
        self.assertEqual(state2["game"]["board_type"], 6)
        self.assertTrue(state2["game"]["two_dice_mode"])

        room_mgr = self.app[ROOM_MGR_KEY]
        room = room_mgr.get_room("HEX-2DICE")
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_values = [6, 4]

        # If move was possible or we force WAIT_MOVE
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_values = [6, 4]

        # Select die 6 with die_index 0
        await ws.send_json({
            "type": "select_die",
            "die_value": 6,
            "die_index": 0
        })
        die_sel = await ws.receive_json()
        self.assertEqual(die_sel["type"], "die_selected")
        self.assertEqual(die_sel["selected_die"], 6)
        self.assertEqual(die_sel["die_index"], 0)

        sel_state = await ws.receive_json()
        self.assertEqual(sel_state["type"], "game_state")
        self.assertEqual(sel_state["game"]["selected_die"], 6)

        # Move token
        await ws.send_json({
            "type": "move_token",
            "token_id": 0,
            "selected_die": 6
        })
        move_msg = await ws.receive_json()
        self.assertEqual(move_msg["type"], "token_moved")
        self.assertEqual(move_msg["token_id"], 0)
        self.assertEqual(move_msg["new_step"], 0)

        move_state = await ws.receive_json()
        # Ensure selected_die was cleanly reset to None after move
        self.assertIsNone(move_state["game"]["selected_die"])

        await ws.close()


class TestMainServerConfig(unittest.TestCase):
    def test_dynamic_port_env_var(self):
        import os
        from main import parse_arguments

        old_port = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "9443"
            args = parse_arguments([])
            self.assertEqual(args.port, 9443)
        finally:
            if old_port is not None:
                os.environ["PORT"] = old_port
            else:
                os.environ.pop("PORT", None)

    def test_default_port_fallback(self):
        import os
        from main import parse_arguments

        old_port = os.environ.get("PORT")
        try:
            os.environ.pop("PORT", None)
            args = parse_arguments([])
            self.assertEqual(args.port, 8080)
        finally:
            if old_port is not None:
                os.environ["PORT"] = old_port

    def test_cli_flags_and_port_override(self):
        import os
        from main import parse_arguments

        old_port = os.environ.get("PORT")
        try:
            os.environ["PORT"] = "9443"
            args = parse_arguments(["--port", "7070", "--host", "0.0.0.0", "--no-browser"])
            self.assertEqual(args.port, 7070)
            self.assertEqual(args.host, "0.0.0.0")
            self.assertTrue(args.no_browser)
        finally:
            if old_port is not None:
                os.environ["PORT"] = old_port
            else:
                os.environ.pop("PORT", None)


if __name__ == "__main__":
    unittest.main()
