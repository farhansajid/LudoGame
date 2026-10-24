"""
Automated Unit and Integration Tests for 2-Dice Sequential Move Mechanics.

Validates:
1. Sequential moves across two different tokens in the same turn.
2. Sequential moves on the same token in the same turn.
3. Releasing a token from yard with die 1 (6) and advancing it with die 2 in the same turn.
4. Auto-completion of turn when only one die has valid moves and the remaining die has none.
5. Combined sum move consuming both dice simultaneously.
6. Extra turn deferral: bonus rolls for captures, goals, and rolled sixes deferred until sequential moves resolve.
7. pass_remaining() method forfeits leftover dice and properly advances the turn.
8. Bot AI 2-step lookahead evaluation for sequential moves.
9. RoomManager and WebSocket sequential move message protocol.
"""

import asyncio
import unittest
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase

from server.ludo_engine import LudoGame, STEP_YARD, STEP_START
from server.bot_ai import BotAI
from server.app import create_app, ROOM_MGR_KEY


class TestTwoDiceSequentialEngine(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "RedPlayer", "is_bot": False},
            {"color": "green", "name": "GreenPlayer", "is_bot": False},
            {"color": "yellow", "name": "YellowPlayer", "is_bot": False},
            {"color": "blue", "name": "BluePlayer", "is_bot": False}
        ]
        self.game = LudoGame(self.configs, open_on_one=False, two_dice_mode=True, rng_seed=42)

    def test_sequential_moves_two_different_tokens(self):
        red = self.game.players[0]
        # Put token 0 and token 1 on track
        red.tokens[0].step = 0
        red.tokens[1].step = 0

        self.game.turn_state = "WAIT_ROLL"
        roll_res = self.game.roll_dice(forced_value=[3, 5])
        self.assertEqual(roll_res["remaining_dice"], [3, 5])
        self.assertEqual(roll_res["used_dice"], [])

        # Move token 0 with die 3
        m1 = self.game.move_token(0, selected_die=3)
        self.assertFalse(m1["turn_complete"])
        self.assertEqual(m1["remaining_dice"], [5])
        self.assertEqual(m1["used_dice"], [3])
        self.assertEqual(red.tokens[0].step, 3)
        self.assertEqual(self.game.turn_state, "WAIT_MOVE")
        self.assertEqual(self.game.current_player.color, "red")

        # Move token 1 with remaining die 5
        m2 = self.game.move_token(1, selected_die=5)
        self.assertTrue(m2["turn_complete"])
        self.assertEqual(m2["remaining_dice"], [])
        self.assertEqual(red.tokens[1].step, 5)
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")
        self.assertEqual(self.game.current_player.color, "green")

    def test_sequential_moves_same_token(self):
        red = self.game.players[0]
        red.tokens[0].step = 4

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[2, 4])

        # Step 1: move token 0 with 2 -> step 6
        m1 = self.game.move_token(0, selected_die=2)
        self.assertFalse(m1["turn_complete"])
        self.assertEqual(red.tokens[0].step, 6)
        self.assertEqual(m1["remaining_dice"], [4])

        # Step 2: move same token 0 with 4 -> step 10
        m2 = self.game.move_token(0, selected_die=4)
        self.assertTrue(m2["turn_complete"])
        self.assertEqual(red.tokens[0].step, 10)
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")
        self.assertEqual(self.game.current_player.color, "green")

    def test_yard_release_and_advance_in_same_turn(self):
        red = self.game.players[0]
        # All tokens in yard
        for t in red.tokens:
            self.assertEqual(t.step, STEP_YARD)

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[6, 4])

        # Move 1: release token 0 with 6
        m1 = self.game.move_token(0, selected_die=6)
        self.assertFalse(m1["turn_complete"])
        self.assertEqual(red.tokens[0].step, STEP_START)
        self.assertEqual(m1["remaining_dice"], [4])

        # Move 2: advance token 0 with 4
        m2 = self.game.move_token(0, selected_die=4)
        self.assertTrue(m2["turn_complete"])
        self.assertEqual(red.tokens[0].step, 4)
        # 6 gave an extra turn, which was deferred to the end of the turn!
        self.assertTrue(m2["extra_turn"])
        self.assertEqual(m2["extra_turn_reason"], "rolled_six")
        self.assertEqual(self.game.current_player.color, "red")

    def test_single_die_used_when_second_die_has_no_legal_moves(self):
        red = self.game.players[0]
        # Token 0 is at step 53 (goal is 56)
        red.tokens[0].step = 53
        # Tokens 1, 2, 3 in yard (open_on_one is False, so only 6 can release)
        for t in red.tokens[1:]:
            t.step = STEP_YARD

        self.game.turn_state = "WAIT_ROLL"
        # Roll [3, 5]: 3 can move token 0 into goal (53+3=56), but 5 cannot move token 0 (53+5=58 > 56)
        # and 5 cannot release any token from yard!
        self.game.roll_dice(forced_value=[3, 5])

        m1 = self.game.move_token(0, selected_die=3)
        # Token 0 reached goal, and remaining die 5 has NO valid moves!
        # Thus turn_complete should be True immediately
        self.assertTrue(m1["turn_complete"])
        self.assertEqual(red.tokens[0].step, 56)
        self.assertTrue(red.tokens[0].is_in_goal)
        self.assertTrue(m1["reached_goal"])
        # Goal grants an extra turn
        self.assertTrue(m1["extra_turn"])
        self.assertEqual(self.game.current_player.color, "red")

    def test_combined_sum_move_consumes_both_dice(self):
        red = self.game.players[0]
        red.tokens[0].step = 10

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[2, 5])

        # Direct sum move (7)
        m = self.game.move_token(0, selected_die=7)
        self.assertTrue(m["turn_complete"])
        self.assertEqual(m["remaining_dice"], [])
        self.assertEqual(red.tokens[0].step, 17)
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")
        self.assertEqual(self.game.current_player.color, "green")

    def test_extra_turn_deferred_upon_capture_on_first_die(self):
        red = self.game.players[0]
        green = self.game.players[1]

        # Red token 0 at step 0 (global index 0)
        red.tokens[0].step = 0
        # Green token 0 at global index 3 (red's track offset is 0, green's is 13, track length 52)
        # Green token step to be at global index 3: (13 + step) % 52 == 3 -> step = 42
        green.tokens[0].step = 42
        self.assertEqual(green.tokens[0].global_track_index, 3)

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[3, 4])

        # Move 1 with 3: captures green token
        m1 = self.game.move_token(0, selected_die=3)
        self.assertEqual(len(m1["captures"]), 1)
        self.assertFalse(m1["turn_complete"])
        self.assertTrue(m1["pending_extra_turn"])
        self.assertFalse(m1["extra_turn"])  # Not awarded until turn completes
        self.assertEqual(green.tokens[0].step, STEP_YARD)

        # Move 2 with 4: advances token 0 to step 7
        m2 = self.game.move_token(0, selected_die=4)
        self.assertTrue(m2["turn_complete"])
        self.assertTrue(m2["extra_turn"])
        self.assertEqual(m2["extra_turn_reason"], "captured_piece")
        self.assertEqual(self.game.current_player.color, "red")

    def test_pass_remaining_forfeits_second_die(self):
        red = self.game.players[0]
        red.tokens[0].step = 2
        red.tokens[1].step = 5

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[3, 4])

        m1 = self.game.move_token(0, selected_die=3)
        self.assertFalse(m1["turn_complete"])
        self.assertEqual(self.game.remaining_dice, [4])

        # Player decides to pass remainder
        pass_res = self.game.pass_remaining()
        self.assertTrue(pass_res["turn_complete"])
        self.assertEqual(pass_res["passed_dice"], [4])
        self.assertEqual(self.game.remaining_dice, [])
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")
        self.assertEqual(self.game.current_player.color, "green")

    def test_moving_sum_containing_six_awards_extra_turn(self):
        red = self.game.players[0]
        red.tokens[0].step = 10

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[6, 2])

        # Moving sum 8 (consuming [6, 2]) must award extra turn for rolled 6
        m = self.game.move_token(0, selected_die=8)
        self.assertTrue(m["turn_complete"])
        self.assertEqual(red.tokens[0].step, 18)
        self.assertTrue(m["extra_turn"])
        self.assertEqual(m["extra_turn_reason"], "rolled_six")
        self.assertEqual(self.game.current_player.color, "red")

    def test_moving_sum_double_sixes_awards_extra_turn(self):
        red = self.game.players[0]
        red.tokens[0].step = 10

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[6, 6])

        # Moving sum 12 (consuming [6, 6]) must award extra turn
        m = self.game.move_token(0, selected_die=12)
        self.assertTrue(m["turn_complete"])
        self.assertEqual(red.tokens[0].step, 22)
        self.assertTrue(m["extra_turn"])
        self.assertEqual(m["extra_turn_reason"], "rolled_six")
        self.assertEqual(self.game.current_player.color, "red")

    def test_cannot_roll_in_wait_move_state(self):
        red = self.game.players[0]
        red.tokens[0].step = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[6, 4])

        m1 = self.game.move_token(0, selected_die=6)
        self.assertFalse(m1["turn_complete"])
        self.assertEqual(self.game.turn_state, "WAIT_MOVE")

        # Rolling while second die is pending must strictly raise ValueError
        with self.assertRaises(ValueError):
            self.game.roll_dice(forced_value=[3, 3])

    def test_winning_on_first_die_auto_completes_and_awards_no_extra_turn_to_winner(self):
        red = self.game.players[0]
        # Place 3 tokens in goal, 1 token at step 54
        red.tokens[0].step = 56
        red.tokens[1].step = 56
        red.tokens[2].step = 56
        red.tokens[3].step = 54

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[2, 4])

        # Move token 3 with 2 into goal -> Red now has won!
        m1 = self.game.move_token(3, selected_die=2)
        self.assertTrue(red.has_won)
        # Since all tokens are in goal, remaining die 4 has no moves and turn auto-completes immediately
        self.assertTrue(m1["turn_complete"])
        self.assertEqual(m1["remaining_dice"], [])
        self.assertFalse(m1["extra_turn"])
        self.assertEqual(self.game.current_player.color, "green")

    def test_pass_remaining_in_single_die_mode_raises(self):
        single_game = LudoGame(self.configs, open_on_one=False, two_dice_mode=False)
        single_game.turn_state = "WAIT_ROLL"
        single_game.roll_dice(forced_value=3)
        with self.assertRaises(ValueError):
            single_game.pass_remaining()


class TestBotAITwoDiceSequential(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "BotRed", "is_bot": True},
            {"color": "green", "name": "BotGreen", "is_bot": True},
            {"color": "yellow", "name": "BotYellow", "is_bot": True},
            {"color": "blue", "name": "BotBlue", "is_bot": True}
        ]
        self.game = LudoGame(self.configs, open_on_one=False, two_dice_mode=True, rng_seed=42)
        self.ai = BotAI()

    def test_bot_ai_finds_yard_release_and_followup_step(self):
        red = self.game.players[0]
        # All tokens in yard
        for t in red.tokens:
            self.assertEqual(t.step, STEP_YARD)

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[6, 3])
        moves_by_die = {
            "6": self.game.get_valid_moves(6),
            "3": self.game.get_valid_moves(3),
            "9": self.game.get_valid_moves(9)
        }
        chosen_die, token_id = BotAI.choose_move_two_dice(self.game, moves_by_die, difficulty="hard")
        # First move must use die 6 to release a token
        self.assertEqual(chosen_die, 6)
        self.assertIn(token_id, [0, 1, 2, 3])

    def test_bot_ai_prefers_sequential_capture_over_idle_sum(self):
        red = self.game.players[0]
        green = self.game.players[1]

        red.tokens[0].step = 0
        # Opponent at distance 4 (global 4)
        green.tokens[0].step = 43  # (13 + 43) % 52 = 4
        self.assertEqual(green.tokens[0].global_track_index, 4)

        # Roll [4, 2]. Die 4 directly captures green token!
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[4, 2])
        moves_by_die = {
            "4": self.game.get_valid_moves(4),
            "2": self.game.get_valid_moves(2),
            "6": self.game.get_valid_moves(6)
        }
        chosen_die, token_id = BotAI.choose_move_two_dice(self.game, moves_by_die, difficulty="hard")
        self.assertEqual(chosen_die, 4)
        self.assertEqual(token_id, 0)

    def test_bot_ai_double_die_index_selection_in_room(self):
        from server.room_manager import GameRoom
        room = GameRoom("BOT-DOUBLES", "host-1", mode="single", player_count=4, two_dice_mode=True)
        room.game = self.game
        bot_player = room.game.players[0]
        bot_player.tokens[0].step = 0
        bot_player.tokens[1].step = 0

        # Simulate bot turn with doubles [5, 5]
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_values = [5, 5]
        room.game.remaining_dice = [5, 5]
        room.game.used_dice = []

        moves_dict = {"5": [0, 1]}
        chosen_die, token_id = BotAI.choose_move_two_dice(room.game, moves_dict, difficulty="hard")
        self.assertEqual(chosen_die, 5)

        # Move 1
        m1 = room.game.move_token(token_id, selected_die=chosen_die)
        self.assertFalse(m1["turn_complete"])
        self.assertEqual(room.game.used_dice, [5])
        self.assertEqual(room.game.remaining_dice, [5])

        # For Move 2, die_index calculation must pick index 1 (not 0)
        used_indices = []
        if len(room.game.used_dice) == 1 and len(room.game.dice_values) == 2:
            first_used = room.game.used_dice[0]
            if room.game.dice_values[0] == first_used:
                used_indices.append(0)
            elif room.game.dice_values[1] == first_used:
                used_indices.append(1)
        chosen_idx = None
        for idx, v in enumerate(room.game.dice_values):
            if idx not in used_indices and v == chosen_die:
                chosen_idx = idx
                break
        self.assertEqual(chosen_idx, 1)

    def test_bot_ai_evaluates_home_run_sequential_properly(self):
        red = self.game.players[0]
        # Step 48: 3 steps to Home Run (step 51), 7 steps to step 55
        red.tokens[0].step = 48
        # Token 1 at step 0
        red.tokens[1].step = 0

        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=[3, 4])
        moves_by_die = {
            "3": [0, 1],
            "4": [0, 1],
            "7": [0]
        }
        chosen_die, token_id = BotAI.choose_move_two_dice(self.game, moves_by_die, difficulty="hard")
        # Moving token 0 into home run is top priority
        self.assertEqual(token_id, 0)


class TestTwoDiceWebSocketFlow(AioHTTPTestCase):
    async def get_application(self):
        static_dir = Path(__file__).parent.parent / "static"
        return create_app(static_dir)

    async def test_websocket_sequential_moves_flow(self):
        ws = await self.client.ws_connect("/ws")
        # 1. Join Room with two_dice_mode=True
        await ws.send_json({
            "type": "join_room",
            "room_id": "2DICE-SEQ",
            "name": "SeqTester",
            "mode": "single",
            "player_count": 4,
            "two_dice_mode": True,
            "open_on_one": False
        })
        msg_joined = await ws.receive_json()
        self.assertEqual(msg_joined["type"], "room_joined")

        msg_init_state = await ws.receive_json()
        self.assertEqual(msg_init_state["type"], "game_state")

        # 2. Start Game
        await ws.send_json({"type": "start_game"})
        msg_started = await ws.receive_json()
        self.assertEqual(msg_started["type"], "game_started")

        msg_game_state = await ws.receive_json()
        self.assertEqual(msg_game_state["type"], "game_state")

        room_mgr = self.app[ROOM_MGR_KEY]
        room = room_mgr.get_room("2DICE-SEQ")
        red = room.game.players[0]
        red.tokens[0].step = 2
        red.tokens[1].step = 5

        # 3. Force roll with [3, 4]
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_values = [3, 4]
        room.game.remaining_dice = [3, 4]
        room.game.used_dice = []
        room.game.selected_die = None

        # Select die 3
        await ws.send_json({
            "type": "select_die",
            "die_value": 3,
            "die_index": 0
        })
        sel_msg = await ws.receive_json()
        self.assertEqual(sel_msg["type"], "die_selected")
        self.assertEqual(sel_msg["selected_die"], 3)
        self.assertEqual(sel_msg["remaining_dice"], [3, 4])

        state_after_sel = await ws.receive_json()
        self.assertEqual(state_after_sel["type"], "game_state")

        # Move token 0 with die 3
        await ws.send_json({
            "type": "move_token",
            "token_id": 0,
            "selected_die": 3
        })
        move1_msg = await ws.receive_json()
        self.assertEqual(move1_msg["type"], "token_moved")
        self.assertFalse(move1_msg["turn_complete"])
        self.assertEqual(move1_msg["remaining_dice"], [4])
        self.assertEqual(move1_msg["used_dice"], [3])

        state_after_move1 = await ws.receive_json()
        self.assertEqual(state_after_move1["type"], "game_state")
        self.assertEqual(state_after_move1["game"]["turn_state"], "WAIT_MOVE")

        # Select second die 4
        await ws.send_json({
            "type": "select_die",
            "die_value": 4,
            "die_index": 1
        })
        sel2_msg = await ws.receive_json()
        self.assertEqual(sel2_msg["type"], "die_selected")
        self.assertEqual(sel2_msg["selected_die"], 4)
        self.assertEqual(sel2_msg["remaining_dice"], [4])

        state_after_sel2 = await ws.receive_json()
        self.assertEqual(state_after_sel2["type"], "game_state")

        # Move token 1 with die 4
        await ws.send_json({
            "type": "move_token",
            "token_id": 1,
            "selected_die": 4
        })
        move2_msg = await ws.receive_json()
        self.assertEqual(move2_msg["type"], "token_moved")
        self.assertTrue(move2_msg["turn_complete"])
        self.assertEqual(move2_msg["remaining_dice"], [])

        state_after_move2 = await ws.receive_json()
        self.assertEqual(state_after_move2["type"], "game_state")

        await ws.close()

    async def test_websocket_pass_turn_flow(self):
        ws = await self.client.ws_connect("/ws")
        await ws.send_json({
            "type": "join_room",
            "room_id": "PASS-ROOM",
            "name": "PassUser",
            "mode": "single",
            "player_count": 4,
            "two_dice_mode": True
        })
        await ws.receive_json()  # room_joined
        await ws.receive_json()  # game_state

        await ws.send_json({"type": "start_game"})
        await ws.receive_json()  # game_started
        await ws.receive_json()  # game_state

        room_mgr = self.app[ROOM_MGR_KEY]
        room = room_mgr.get_room("PASS-ROOM")
        room.game.turn_state = "WAIT_MOVE"
        room.game.dice_values = [3, 5]
        room.game.remaining_dice = [3, 5]
        room.game.used_dice = []

        # Send pass_turn
        await ws.send_json({"type": "pass_turn"})
        pass_msg = await ws.receive_json()
        self.assertEqual(pass_msg["type"], "turn_passed")
        self.assertTrue(pass_msg["turn_complete"])
        self.assertEqual(pass_msg["passed_dice"], [3, 5])

        state_after_pass = await ws.receive_json()
        self.assertEqual(state_after_pass["type"], "game_state")
        self.assertEqual(state_after_pass["game"]["turn_state"], "WAIT_ROLL")

        await ws.close()


if __name__ == "__main__":
    unittest.main()
