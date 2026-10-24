"""
Comprehensive Automated Unit Tests for New Features:
1. Bonus Turn / Extra Roll Awarded on Token Capture (1-die & 2-dice modes)
2. Simultaneous 2-Dice Play and Combined Sum Move Option
3. AI Bot Difficulty Levels (Easy, Medium, Hard)
4. Audio Signaling for 1-on-1 Individual Calls vs Conference Routing
5. Mid-Game Player Quit with AI Bot Handover
6. Player Preferred Color Selection & Lobby Color Swapping
"""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from server.ludo_engine import LudoGame, Token, Player, STEP_YARD, STEP_START
from server.bot_ai import BotAI
from server.audio_signaling import AudioSignalingManager, AudioRoom, AudioPeer
from server.room_manager import GameRoom, RoomManager, RoomPlayer


class TestCaptureBonusRoll(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "Alice", "is_bot": False},
            {"color": "green", "name": "Bob", "is_bot": False},
            {"color": "yellow", "name": "Charlie", "is_bot": True},
            {"color": "blue", "name": "Dave", "is_bot": True}
        ]

    def test_single_die_capture_awards_bonus_roll(self):
        game = LudoGame(self.configs, open_on_one=False, two_dice_mode=False)
        red = game.players[0]
        green = game.players[1]

        # Place Red at global index 2 (step 2)
        # Place Green at global index 5 (green start is 13; step 44 wraps to 5: (13+44)%52 = 5)
        # Global 5 is not a safe square (safe squares: 0, 8, 13, 21, 26, 34, 39, 47)
        red.tokens[0].step = 2
        green.tokens[0].step = 44
        self.assertNotIn(5, game.safe_squares)

        game.current_player_index = 0
        game.turn_state = "WAIT_ROLL"

        # Roll a 3: Red token moves 2 -> 5, capturing Green
        game.roll_dice(forced_value=3)
        res = game.move_token(0)

        self.assertEqual(len(res["captures"]), 1)
        self.assertEqual(res["captures"][0]["player"], "green")
        self.assertTrue(res["bonus_roll_awarded"])
        self.assertTrue(res["extra_turn"])
        self.assertEqual(res["extra_turn_reason"], "captured_piece")
        # Current player should still be Red
        self.assertEqual(game.current_player.color, "red")
        self.assertEqual(game.turn_state, "WAIT_ROLL")

    def test_two_dice_mode_capture_with_sum_awards_bonus_roll(self):
        game = LudoGame(self.configs, open_on_one=False, two_dice_mode=True)
        red = game.players[0]
        green = game.players[1]

        # Red token at step 1 (global 1)
        # Green token at global 6 ((13 + 45)%52 = 6, not a safe square)
        red.tokens[0].step = 1
        green.tokens[0].step = 45
        self.assertNotIn(6, game.safe_squares)

        game.current_player_index = 0
        game.turn_state = "WAIT_ROLL"

        # Roll [2, 3] -> sum is 5
        roll_res = game.roll_dice(forced_value=[2, 3])
        self.assertEqual(game.dice_sum, 5)
        self.assertIn(0, roll_res["valid_moves_sum"])
        self.assertIn(0, game.get_valid_moves(game.dice_sum))

        # Select sum as active die value and move
        sel = game.select_die(5)
        self.assertEqual(sel["selected_die"], 5)
        res = game.move_token(0, selected_die=5)

        self.assertEqual(len(res["captures"]), 1)
        self.assertEqual(res["captures"][0]["player"], "green")
        self.assertTrue(res["bonus_roll_awarded"])
        self.assertTrue(res["extra_turn"])
        self.assertEqual(res["extra_turn_reason"], "captured_piece")
        self.assertEqual(game.current_player.color, "red")


class TestBotDifficultyLevels(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "BotRed", "is_bot": True},
            {"color": "green", "name": "BotGreen", "is_bot": True},
            {"color": "yellow", "name": "BotYellow", "is_bot": True},
            {"color": "blue", "name": "BotBlue", "is_bot": True}
        ]
        self.game = LudoGame(self.configs, open_on_one=True, two_dice_mode=False)

    def test_hard_difficulty_prioritizes_capture(self):
        red = self.game.players[0]
        green = self.game.players[1]

        # Token 0 can capture Green at step 5
        red.tokens[0].step = 2
        green.tokens[0].step = 44  # global 5

        # Token 1 is just wandering at step 10
        red.tokens[1].step = 10

        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=3)

        # Both token 0 and token 1 can move
        valid_moves = [0, 1]
        chosen = BotAI.choose_move(self.game, valid_moves, difficulty="hard")
        self.assertEqual(chosen, 0, "Hard AI should decisively choose capture move")

    def test_easy_difficulty_returns_valid_token(self):
        valid_moves = [0, 1, 2]
        chosen = BotAI.choose_move(self.game, valid_moves, difficulty="easy")
        self.assertIn(chosen, valid_moves)

    def test_two_dice_hard_difficulty_selects_best_die_and_move(self):
        two_game = LudoGame(self.configs, open_on_one=True, two_dice_mode=True)
        two_game.current_player_index = 0
        two_game.turn_state = "WAIT_ROLL"
        roll_res = two_game.roll_dice(forced_value=[1, 6])

        valid_moves_by_die = roll_res["valid_moves_by_die"]
        die_val, token_id = BotAI.choose_move_two_dice(two_game, valid_moves_by_die, difficulty="hard")
        self.assertIn(die_val, [1, 6])
        self.assertIn(token_id, [0, 1, 2, 3])

    def test_two_dice_bot_evaluates_and_chooses_sum_move(self):
        # When moving with the sum of both dice enables a capture that single dice cannot,
        # BotAI on hard difficulty chooses the sum die!
        two_game = LudoGame(self.configs, open_on_one=False, two_dice_mode=True)
        red = two_game.players[0]
        green = two_game.players[1]

        # Red token 0 at step 2 (global 2)
        # Green token 0 at step 44 (global 7: (13+46)%52 = 7)
        # Difference is 5 (global 2 -> global 7)
        red.tokens[0].step = 2
        green.tokens[0].step = 46  # global 7
        self.assertNotIn(7, two_game.safe_squares)

        # Token 1 is at step 20
        red.tokens[1].step = 20

        two_game.current_player_index = 0
        two_game.turn_state = "WAIT_ROLL"
        roll_res = two_game.roll_dice(forced_value=[2, 3])  # sum is 5!

        moves_dict = dict(roll_res["valid_moves_by_die"])
        if roll_res.get("dice_sum") and roll_res.get("valid_moves_sum"):
            moves_dict[str(roll_res["dice_sum"])] = roll_res["valid_moves_sum"]

        die_val, token_id = BotAI.choose_move_two_dice(two_game, moves_dict, difficulty="hard")
        self.assertEqual(die_val, 5, "Hard AI should choose the sum 5 because it captures Green token!")
        self.assertEqual(token_id, 0)


class TestAudioSignalingPrivateCalls(unittest.IsolatedAsyncioTestCase):
    async def test_audio_room_individual_call_routing(self):
        room = AudioRoom("TEST_ROOM")

        ws_alice = AsyncMock()
        ws_alice.closed = False
        ws_bob = AsyncMock()
        ws_bob.closed = False
        ws_charlie = AsyncMock()
        ws_charlie.closed = False

        room.add_peer(AudioPeer("sid_alice", "Alice", "red", ws_alice))
        room.add_peer(AudioPeer("sid_bob", "Bob", "green", ws_bob))
        room.add_peer(AudioPeer("sid_charlie", "Charlie", "yellow", ws_charlie))

        # In conference mode: audio from Alice reaches both Bob and Charlie
        await room.relay_audio_bytes("sid_alice", b"conference_audio")
        ws_bob.send_bytes.assert_called_with(b"conference_audio")
        ws_charlie.send_bytes.assert_called_with(b"conference_audio")

        ws_bob.send_bytes.reset_mock()
        ws_charlie.send_bytes.reset_mock()

        # Alice starts private 1-on-1 call with Bob
        room.private_calls["sid_alice"] = "sid_bob"
        room.private_calls["sid_bob"] = "sid_alice"
        self.assertEqual(room.private_calls.get("sid_alice"), "sid_bob")
        self.assertEqual(room.private_calls.get("sid_bob"), "sid_alice")
        self.assertNotIn("sid_charlie", room.private_calls)

        # Audio from Alice should ONLY go to Bob, NOT Charlie
        await room.relay_audio_bytes("sid_alice", b"secret_audio_from_alice")
        ws_bob.send_bytes.assert_called_with(b"secret_audio_from_alice")
        ws_charlie.send_bytes.assert_not_called()

        ws_bob.send_bytes.reset_mock()

        # Audio from Charlie (non-private) should NOT reach Alice or Bob
        await room.relay_audio_bytes("sid_charlie", b"charlie_audio")
        ws_alice.send_bytes.assert_not_called()
        ws_bob.send_bytes.assert_not_called()

        # End private call
        del room.private_calls["sid_alice"]
        del room.private_calls["sid_bob"]
        self.assertNotIn("sid_alice", room.private_calls)
        self.assertNotIn("sid_bob", room.private_calls)

        # Broadcast resumes
        ws_bob.send_bytes.reset_mock()
        ws_charlie.send_bytes.reset_mock()
        await room.relay_audio_bytes("sid_alice", b"conference_restored")
        ws_bob.send_bytes.assert_called_with(b"conference_restored")
        ws_charlie.send_bytes.assert_called_with(b"conference_restored")


class TestPlayerQuitAndColorChoice(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.room_mgr = RoomManager()

    def test_preferred_color_assignment_and_lobby_switching(self):
        room = self.room_mgr.create_room("host_123", mode="online", player_count=4)
        ws_mock = MagicMock()

        # Player requests yellow as preferred color
        p1 = room.add_human_player("host_123", "Alice", ws_mock, preferred_color="yellow")
        self.assertEqual(p1.color, "yellow")

        # Player requests yellow in lobby when already taken by herself: succeeds
        ok = room.change_player_color("host_123", "yellow")
        self.assertTrue(ok)

        # Switch to green in lobby
        ok = room.change_player_color("host_123", "green")
        self.assertTrue(ok)
        self.assertEqual(p1.color, "green")

    async def test_mid_game_player_quit_handover_to_ai(self):
        room = self.room_mgr.create_room("host_123", mode="online", player_count=4)
        ws1 = MagicMock()
        ws2 = MagicMock()

        p1 = room.add_human_player("sid_alice", "Alice", ws1, preferred_color="red")
        p2 = room.add_human_player("sid_bob", "Bob", ws2, preferred_color="green")
        room.fill_remaining_with_bots()
        room.start_game()

        self.assertEqual(room.status, "PLAYING")
        self.assertFalse(p1.is_bot)

        # Alice quits mid-game
        res = room.player_quit("sid_alice")
        self.assertIsNotNone(res)
        self.assertEqual(res["action"], "replaced_by_bot")
        self.assertEqual(res["player"], "red")
        self.assertTrue(p1.is_bot)
        self.assertIn("(AI)", p1.name)
        # Match continues because Bob is still an active human
        self.assertEqual(room.status, "PLAYING")

        # Now Bob quits too: all humans left
        res2 = room.player_quit("sid_bob")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["action"], "replaced_by_bot")
        self.assertTrue(res2.get("match_ended"))
        self.assertEqual(room.status, "FINISHED")

    def test_two_player_mode_color_choice_all_four_colors(self):
        # 2-player game allows choosing from all 4 standard board colors (red, green, yellow, blue)
        room = self.room_mgr.create_room("host_2p", mode="online", player_count=2)
        ws = MagicMock()
        p = room.add_human_player("host_2p", "Alice", ws, preferred_color="yellow")
        self.assertEqual(p.color, "yellow")

        # Switching to blue succeeds
        self.assertTrue(room.change_player_color("host_2p", "blue"))
        self.assertEqual(p.color, "blue")

    async def test_abrupt_disconnect_hands_over_to_ai_bot(self):
        # Disconnecting without explicit quit should hand over seat to bot
        room = self.room_mgr.create_room("host_abrupt", mode="online", player_count=4)
        ws1 = MagicMock()
        ws1.closed = False
        ws2 = MagicMock()
        ws2.closed = False
        p1 = room.add_human_player("sid_alice", "Alice", ws1, preferred_color="red")
        p2 = room.add_human_player("sid_bob", "Bob", ws2, preferred_color="green")
        room.fill_remaining_with_bots()
        room.start_game()

        self.assertEqual(room.status, "PLAYING")
        self.assertFalse(p1.is_bot)

        # Alice closes tab abruptly
        ws1.closed = True
        self.room_mgr.remove_socket("sid_alice")

        self.assertTrue(p1.is_bot)
        self.assertIn("(AI)", p1.name)
        self.assertEqual(room.status, "PLAYING")

    async def test_private_call_partner_notified_on_disconnect(self):
        audio_mgr = AudioSignalingManager()
        room = audio_mgr.get_or_create_room("ROOM1")
        ws_a = AsyncMock()
        ws_a.closed = False
        ws_b = AsyncMock()
        ws_b.closed = False

        peer_a = AudioPeer("sid_a", "Alice", "red", ws_a)
        peer_b = AudioPeer("sid_b", "Bob", "blue", ws_b)
        room.add_peer(peer_a)
        room.add_peer(peer_b)

        # Alice and Bob enter a private 1-on-1 call
        room.private_calls["sid_a"] = "sid_b"
        room.private_calls["sid_b"] = "sid_a"

        # Bob disconnects abruptly
        await audio_mgr.handle_disconnect("sid_b")

        # Alice should have received audio_call_ended
        ws_a.send_json.assert_any_call({
            "type": "audio_call_ended",
            "room_id": "ROOM1"
        })
        self.assertNotIn("sid_a", room.private_calls)
        self.assertNotIn("sid_b", room.private_calls)


if __name__ == "__main__":
    unittest.main()
