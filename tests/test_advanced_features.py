"""
Comprehensive Tests for Advanced Ludo Features:
- 6-Player Hexagonal Match Mechanics & Board Geometry
- 8-Player Octagonal Match Mechanics & Board Geometry
- 2-Dice Rolling Option, Interactive Die Selection & Movement
- Escaped Danger Particle Trigger & Calculation
- Yard Release Particle Triggers (6 vs 1 Boost)
- Goal & Capture Particle Outcome Triggers
- BotAI Two-Dice Decision Making
"""

import unittest
from server.ludo_engine import (
    LudoGame, Token, Player,
    STEP_YARD, STEP_START
)
from server.bot_ai import BotAI


class TestSixPlayerGame(unittest.TestCase):
    def setUp(self):
        self.configs6 = [
            {"color": "red", "name": "P1", "is_bot": False},
            {"color": "green", "name": "P2", "is_bot": False},
            {"color": "yellow", "name": "P3", "is_bot": True},
            {"color": "blue", "name": "P4", "is_bot": True},
            {"color": "orange", "name": "P5", "is_bot": True},
            {"color": "purple", "name": "P6", "is_bot": True}
        ]
        self.game = LudoGame(self.configs6, rng_seed=100)

    def test_6player_initialization_and_geometry(self):
        self.assertEqual(len(self.game.players), 6)
        self.assertEqual(self.game.board_type, 6)
        self.assertEqual(self.game.track_length, 78)
        self.assertEqual(self.game.step_track_max, 76)
        self.assertEqual(self.game.step_home_start, 77)
        self.assertEqual(self.game.step_goal, 82)

        # Check start offsets and safe squares
        # 6 players spaced by 13: 0, 13, 26, 39, 52, 65
        expected_starts = {"red": 0, "green": 13, "yellow": 26, "blue": 39, "orange": 52, "purple": 65}
        for color, offset in expected_starts.items():
            self.assertEqual(self.game.start_offsets[color], offset)
            self.assertIn(offset, self.game.safe_squares)
            self.assertIn((offset + 8) % 78, self.game.safe_squares)

    def test_6player_token_track_movement_and_turn_order(self):
        red = self.game.players[0]
        green = self.game.players[1]
        red.tokens[0].step = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.current_player_index = 0

        res = self.game.roll_dice(forced_value=5)
        self.assertIn(0, res["valid_moves"])
        move_res = self.game.move_token(0)
        self.assertEqual(move_res["new_step"], 5)
        self.assertEqual(move_res["new_global_index"], 5)
        self.assertEqual(self.game.current_player.color, "green")

    def test_6player_home_run_and_goal(self):
        red = self.game.players[0]
        # Track max is 76; step 77 is Home 1; step 82 is Goal
        red.tokens[0].step = 76
        self.game.turn_state = "WAIT_ROLL"
        self.game.current_player_index = 0

        # Roll 1 -> moves to Home 1 (step 77)
        self.game.roll_dice(forced_value=1)
        move_res = self.game.move_token(0)
        self.assertEqual(move_res["new_step"], 77)
        self.assertFalse(move_res["reached_goal"])

        # Roll 5 -> moves to Goal (77 + 5 = 82)
        red.tokens[0].step = 77
        self.game.turn_state = "WAIT_ROLL"
        self.game.current_player_index = 0
        self.game.roll_dice(forced_value=5)
        move_res2 = self.game.move_token(0)
        self.assertEqual(move_res2["new_step"], 82)
        self.assertTrue(move_res2["reached_goal"])
        self.assertTrue(red.tokens[0].is_in_goal)

    def test_6player_capture_and_yard_reset(self):
        # Red token at step 10 (global 10)
        # Green token at global 15 (Green start is 13, step 2 = global 15, not safe)
        red = self.game.players[0]
        green = self.game.players[1]
        red.tokens[0].step = 10
        green.tokens[0].step = 2

        self.assertNotIn(15, self.game.safe_squares)
        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"

        self.game.roll_dice(forced_value=5)
        move_res = self.game.move_token(0)
        self.assertEqual(len(move_res["captures"]), 1)
        self.assertEqual(move_res["captures"][0]["player"], "green")
        self.assertEqual(green.tokens[0].step, STEP_YARD)


class TestEightPlayerGame(unittest.TestCase):
    def setUp(self):
        self.configs8 = [
            {"color": "red", "name": "P1", "is_bot": False},
            {"color": "green", "name": "P2", "is_bot": True},
            {"color": "yellow", "name": "P3", "is_bot": True},
            {"color": "blue", "name": "P4", "is_bot": True},
            {"color": "orange", "name": "P5", "is_bot": True},
            {"color": "purple", "name": "P6", "is_bot": True},
            {"color": "cyan", "name": "P7", "is_bot": True},
            {"color": "pink", "name": "P8", "is_bot": True}
        ]
        self.game = LudoGame(self.configs8, rng_seed=200)

    def test_8player_initialization_and_geometry(self):
        self.assertEqual(len(self.game.players), 8)
        self.assertEqual(self.game.board_type, 8)
        self.assertEqual(self.game.track_length, 104)
        self.assertEqual(self.game.step_track_max, 102)
        self.assertEqual(self.game.step_home_start, 103)
        self.assertEqual(self.game.step_goal, 108)

        expected_starts = {
            "red": 0, "green": 13, "yellow": 26, "blue": 39,
            "orange": 52, "purple": 65, "cyan": 78, "pink": 91
        }
        for color, offset in expected_starts.items():
            self.assertEqual(self.game.start_offsets[color], offset)
            self.assertIn(offset, self.game.safe_squares)
            self.assertIn((offset + 8) % 104, self.game.safe_squares)

    def test_8player_full_rotation(self):
        # Verify 8 players take turns in order
        colors = ["red", "green", "yellow", "blue", "orange", "purple", "cyan", "pink"]
        for expected in colors:
            self.assertEqual(self.game.current_player.color, expected)
            self.game.roll_dice(forced_value=2)  # In yard, will auto-pass
        self.assertEqual(self.game.current_player.color, "red")

    def test_8player_goal_and_victory(self):
        pink = self.game.players[7]
        pink.tokens[0].step = 108
        pink.tokens[1].step = 108
        pink.tokens[2].step = 108
        pink.tokens[3].step = 106

        self.game.current_player_index = 7
        self.game.turn_state = "WAIT_ROLL"

        self.game.roll_dice(forced_value=2)
        move_res = self.game.move_token(3)
        self.assertTrue(move_res["reached_goal"])
        self.assertTrue(pink.has_won)
        self.assertIn("pink", self.game.winners)


class TestTwoDiceMode(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "P1", "is_bot": False},
            {"color": "green", "name": "P2", "is_bot": True}
        ]
        self.game = LudoGame(self.configs, two_dice_mode=True, rng_seed=300)

    def test_two_dice_roll_structure(self):
        res = self.game.roll_dice()
        self.assertTrue(self.game.two_dice_mode)
        self.assertIsNotNone(res["dice_values"])
        self.assertEqual(len(res["dice_values"]), 2)
        for v in res["dice_values"]:
            self.assertIn(v, [1, 2, 3, 4, 5, 6])
        self.assertIn("valid_moves_by_die", res)
        self.assertEqual(len(res["valid_moves_by_die"]), 2)

    def test_two_dice_select_die_and_moves_filtering(self):
        red = self.game.players[0]
        # Token 0 is in yard (needs 1 or 6 if open_on_one)
        # Token 1 is at step 5
        red.tokens[0].step = -1
        red.tokens[1].step = 5

        self.game.turn_state = "WAIT_ROLL"
        self.game.current_player_index = 0

        # Simulate rolling [6, 3] with open_on_one=False (only 6 can release yard)
        self.game.open_on_one = False
        res = self.game.roll_dice(forced_value=[6, 3])
        self.assertEqual(res["dice_values"], [6, 3])

        # For die 6: can release yard token 0, or move token 1
        valid_for_6 = res["valid_moves_by_die"]["6"]
        self.assertIn(0, valid_for_6)
        self.assertIn(1, valid_for_6)

        # For die 3: yard token 0 CANNOT move; only token 1 can move
        valid_for_3 = res["valid_moves_by_die"]["3"]
        self.assertNotIn(0, valid_for_3)
        self.assertIn(1, valid_for_3)

        # Select die 3
        sel_res = self.game.select_die(3)
        self.assertEqual(sel_res["selected_die"], 3)
        self.assertEqual(sel_res["valid_moves"], [1])

        # Moving with selected die 3 moves token 1 by 3 steps (5 + 3 = 8)
        move_res = self.game.move_token(1, selected_die=3)
        self.assertEqual(move_res["token_id"], 1)
        self.assertEqual(move_res["new_step"], 8)
        self.assertEqual(move_res["dice"], 3)

    def test_two_dice_bot_ai_choose_move(self):
        red = self.game.players[0]
        red.tokens[0].step = 0
        red.tokens[1].step = 10

        moves_by_die = {
            "2": [0, 1],
            "5": [0, 1]
        }
        chosen_die, token_id = BotAI.choose_move_two_dice(self.game, moves_by_die)
        self.assertIn(chosen_die, [2, 5])
        self.assertIn(token_id, [0, 1])


class TestDangerEscapeAndParticleTriggers(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "P1", "is_bot": False},
            {"color": "green", "name": "P2", "is_bot": False}
        ]
        self.game = LudoGame(self.configs, rng_seed=400)

    def test_escaped_danger_trigger_to_safety(self):
        red = self.game.players[0]
        green = self.game.players[1]

        # In 4-player classic:
        # Red start is 0. Green start is 13.
        # Suppose Red token 0 is at global 5 (unsafe square).
        # Green token 0 is at global 2 (Green start is 13; (13 + 41) % 52 = 2, step 41).
        # Green is exactly 3 squares behind Red! Red is in danger!
        # Next square global 8 is a Safe Star Square.
        # Red rolls 3 -> lands on global 8 (step 8).
        # Red escaped danger!
        red.tokens[0].step = 5
        green.tokens[0].step = 41
        self.assertEqual(green.tokens[0].global_track_index, 2)
        self.assertNotIn(5, self.game.safe_squares)
        self.assertIn(8, self.game.safe_squares)

        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=3)
        move_res = self.game.move_token(0)

        self.assertEqual(move_res["new_step"], 8)
        self.assertTrue(move_res["escaped_danger"], "Red should have escaped danger to safe square")

    def test_escaped_danger_trigger_moving_out_of_range(self):
        red = self.game.players[0]
        green = self.game.players[1]

        # Red at global 6 (unsafe). Green at global 4 (unsafe, 2 steps behind).
        # Red rolls 5 -> moves to global 11 (unsafe, but now 7 steps ahead of Green, out of d <= 6 range).
        red.tokens[0].step = 6
        green.tokens[0].step = 43  # (13 + 43) % 52 = 4
        self.assertEqual(green.tokens[0].global_track_index, 4)

        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=5)
        move_res = self.game.move_token(0)

        self.assertEqual(move_res["new_step"], 11)
        self.assertTrue(move_res["escaped_danger"], "Red should have escaped out of enemy die range")

    def test_not_escaped_danger_when_no_threat(self):
        red = self.game.players[0]
        red.tokens[0].step = 6
        # All green tokens are in yard
        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=3)
        move_res = self.game.move_token(0)

        self.assertFalse(move_res["escaped_danger"])

    def test_six_release_particle_trigger_flag(self):
        # Moving from -1 to 0 on roll of 6 should have dice == 6 and old_step == -1, new_step == 0
        red = self.game.players[0]
        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=6)
        move_res = self.game.move_token(0)

        self.assertEqual(move_res["old_step"], -1)
        self.assertEqual(move_res["new_step"], 0)
        self.assertEqual(move_res["dice"], 6)

    def test_no_danger_escape_when_threat_turns_into_home(self):
        # Green is at step 49 (global 10). Red is at global 14 (step 14).
        # Distance is 4, but Green only has 1 track step left before turning into home run!
        # Green cannot reach global 14. Red moving should NOT trigger escaped_danger.
        red = self.game.players[0]
        green = self.game.players[1]
        red.tokens[0].step = 14
        green.tokens[0].step = 49

        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        self.game.roll_dice(forced_value=3)
        move_res = self.game.move_token(0)

        self.assertFalse(move_res["escaped_danger"], "Should not escape danger from opponent turning into home")

    def test_consecutive_double_sixes_penalty_and_reset(self):
        two_d_game = LudoGame(self.configs, two_dice_mode=True, rng_seed=500)
        # 1. Roll [6, 6] -> consec = 1; resolve both dice
        two_d_game.roll_dice(forced_value=[6, 6])
        self.assertEqual(two_d_game.consecutive_sixes, 1)
        two_d_game.move_token(0, selected_die=6)
        two_d_game.move_token(0, selected_die=6)

        # 2. Roll [6, 2] -> not double sixes -> consec must reset to 0; resolve both dice
        two_d_game.roll_dice(forced_value=[6, 2])
        self.assertEqual(two_d_game.consecutive_sixes, 0, "Non-double roll must reset consecutive sixes")
        two_d_game.move_token(1, selected_die=6)
        two_d_game.move_token(1, selected_die=2)

        # 3. Roll [6, 6] again -> consec = 1; resolve both dice
        two_d_game.roll_dice(forced_value=[6, 6])
        self.assertEqual(two_d_game.consecutive_sixes, 1)
        two_d_game.move_token(2, selected_die=6)
        two_d_game.move_token(2, selected_die=6)

        # 4. Roll [6, 6] again -> consec = 2; resolve both dice
        two_d_game.roll_dice(forced_value=[6, 6])
        self.assertEqual(two_d_game.consecutive_sixes, 2)
        two_d_game.move_token(3, selected_die=6)
        two_d_game.move_token(3, selected_die=6)

        # 5. Roll [6, 6] 3rd consecutive time -> Penalty violation & turn forfeit
        pen = two_d_game.roll_dice(forced_value=[6, 6])
        self.assertTrue(pen.get("consecutive_sixes_violation"))
        self.assertEqual(two_d_game.consecutive_sixes, 0)
        self.assertEqual(two_d_game.current_player.color, "green")

    def test_selected_die_cleared_in_game_state_after_move(self):
        two_d_game = LudoGame(self.configs, two_dice_mode=True, rng_seed=600)
        two_d_game.roll_dice(forced_value=[6, 4])
        two_d_game.select_die(6)
        res1 = two_d_game.move_token(0, selected_die=6)
        self.assertFalse(res1["turn_complete"])
        self.assertEqual(res1["remaining_dice"], [4])

        state1 = two_d_game.get_state()
        self.assertIsNone(state1["selected_die"], "selected_die must be reset to None after move")
        self.assertIsNone(state1["dice_value"])
        self.assertEqual(state1["remaining_dice"], [4])

        # Complete second sequential move with remaining die 4
        two_d_game.select_die(4)
        res2 = two_d_game.move_token(0, selected_die=4)
        self.assertTrue(res2["turn_complete"])

        state2 = two_d_game.get_state()
        self.assertIsNone(state2["selected_die"], "selected_die must be reset to None after turn completes")
        self.assertIsNone(state2["dice_value"])
        self.assertIsNone(state2["dice_values"])

    def test_duplicate_rolled_dice_selection(self):
        two_d_game = LudoGame(self.configs, two_dice_mode=True, rng_seed=700)
        # Roll double 4s with open_on_one
        res = two_d_game.roll_dice(forced_value=[4, 4])
        self.assertEqual(res["dice_values"], [4, 4])
        # Auto-passed because red tokens in yard cannot move with 4
        self.assertTrue(res.get("auto_passed"))


if __name__ == "__main__":
    unittest.main()
