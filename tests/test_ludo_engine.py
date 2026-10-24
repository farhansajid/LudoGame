"""
Comprehensive Tests for Ludo Engine
Validates:
- Player initialization (2, 3, 4 players)
- Yard to Start token release on roll of 6
- Yard tokens cannot move on 1-5
- Token movement along track
- Safe squares protection
- Captures on unsafe squares
- Entering home run
- Exact roll to reach goal & overshoot prevention
- Extra turns on: roll 6, capture, goal
- Three consecutive sixes penalty
- Game over and player ranking
"""

import unittest
from server.ludo_engine import (
    LudoGame, Token, Player, SAFE_SQUARES,
    STEP_YARD, STEP_START, STEP_GOAL, STEP_HOME_START
)


class TestLudoEngine(unittest.TestCase):
    def setUp(self):
        self.configs = [
            {"color": "red", "name": "Alice", "is_bot": False},
            {"color": "green", "name": "Bob", "is_bot": False},
            {"color": "yellow", "name": "Charlie", "is_bot": True},
            {"color": "blue", "name": "David", "is_bot": True}
        ]
        self.game = LudoGame(self.configs, rng_seed=42)

    def test_initialization(self):
        self.assertEqual(len(self.game.players), 4)
        self.assertEqual(self.game.current_player.color, "red")
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")
        for p in self.game.players:
            self.assertEqual(len(p.tokens), 4)
            for t in p.tokens:
                self.assertTrue(t.is_in_yard)

    def test_roll_non_six_in_yard_passes_turn(self):
        # Rolling non-6 when all tokens are in yard should auto-pass
        res = self.game.roll_dice(forced_value=3)
        self.assertEqual(res["dice"], 3)
        self.assertEqual(res["valid_moves"], [])
        self.assertTrue(res["auto_passed"])
        self.assertEqual(res["next_player"], "green")
        self.assertEqual(self.game.current_player.color, "green")
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")

    def test_roll_six_in_yard_allows_release(self):
        res = self.game.roll_dice(forced_value=6)
        self.assertEqual(res["dice"], 6)
        self.assertFalse(res["auto_passed"])
        self.assertEqual(len(res["valid_moves"]), 4)  # All 4 yard tokens can be released
        self.assertEqual(self.game.turn_state, "WAIT_MOVE")

        # Move token 0 out
        move_res = self.game.move_token(0)
        self.assertEqual(move_res["player"], "red")
        self.assertEqual(move_res["token_id"], 0)
        self.assertEqual(move_res["new_step"], STEP_START)
        self.assertEqual(move_res["new_global_index"], 0)
        self.assertTrue(move_res["extra_turn"])
        self.assertEqual(move_res["extra_turn_reason"], "rolled_six")
        # Player should get extra turn because they rolled a 6
        self.assertEqual(self.game.current_player.color, "red")
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")

    def test_movement_on_track(self):
        # Put token 0 on track
        self.game.players[0].tokens[0].step = 0
        self.game.turn_state = "WAIT_ROLL"

        res = self.game.roll_dice(forced_value=4)
        self.assertIn(0, res["valid_moves"])

        move_res = self.game.move_token(0)
        self.assertEqual(move_res["new_step"], 4)
        self.assertEqual(move_res["new_global_index"], 4)
        self.assertFalse(move_res["extra_turn"])
        # Turn advances to next player
        self.assertEqual(self.game.current_player.color, "green")

    def test_capture_opponent(self):
        # Red token at global 10 (step 10)
        # Green token at global 14 (Green start is 13, step 1 is global 14)
        # Suppose Red is at global 10 and rolls 4 -> lands on global 14 (not safe). Green should be captured!
        red = self.game.players[0]
        green = self.game.players[1]

        red.tokens[0].step = 10  # Red start is 0, so global is 10
        green.tokens[0].step = 1  # Green start is 13, so global is 14

        self.assertNotIn(14, SAFE_SQUARES)

        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"

        roll_res = self.game.roll_dice(forced_value=4)
        move_res = self.game.move_token(0)

        self.assertEqual(len(move_res["captures"]), 1)
        self.assertEqual(move_res["captures"][0]["player"], "green")
        self.assertEqual(move_res["captures"][0]["token_id"], 0)
        self.assertTrue(green.tokens[0].is_in_yard)  # Returned to yard
        self.assertTrue(move_res["extra_turn"])
        self.assertEqual(move_res["extra_turn_reason"], "captured_piece")
        # Red keeps turn!
        self.assertEqual(self.game.current_player.color, "red")

    def test_safe_square_no_capture(self):
        # Global 21 is a Safe Star Square
        # Red start is 0, so Red step 21 is global 21
        # Yellow start is 26.
        # If Green is at global 21 (safe), Red cannot capture Green.
        red = self.game.players[0]
        green = self.game.players[1]

        self.assertIn(21, SAFE_SQUARES)

        # Place Green at global 21 (Green start is 13, step 8 -> global 21)
        green.tokens[0].step = 8
        self.assertEqual(green.tokens[0].global_track_index, 21)

        # Place Red at global 18 (step 18)
        red.tokens[0].step = 18
        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"

        self.game.roll_dice(forced_value=3)
        move_res = self.game.move_token(0)

        self.assertEqual(red.tokens[0].global_track_index, 21)
        # No captures because it is safe
        self.assertEqual(len(move_res["captures"]), 0)
        self.assertFalse(green.tokens[0].is_in_yard)

    def test_home_run_and_overshoot(self):
        red = self.game.players[0]
        # Red token at step 53 (H3). Needs 3 to reach Goal (step 56)
        red.tokens[0].step = 53
        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"

        # Rolling 4 overshoots (53 + 4 = 57 > 56). Cannot move!
        res = self.game.roll_dice(forced_value=4)
        self.assertNotIn(0, res["valid_moves"])
        self.assertTrue(res["auto_passed"])

        # Reset turn to Red for testing exact roll
        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"
        res2 = self.game.roll_dice(forced_value=3)
        self.assertIn(0, res2["valid_moves"])

        move_res = self.game.move_token(0)
        self.assertEqual(move_res["new_step"], STEP_GOAL)
        self.assertTrue(move_res["reached_goal"])
        self.assertTrue(move_res["extra_turn"])

    def test_three_consecutive_sixes_penalty(self):
        self.game.players[0].tokens[0].step = 0
        self.game.turn_state = "WAIT_ROLL"

        # 1st six
        r1 = self.game.roll_dice(forced_value=6)
        self.game.move_token(0)

        # 2nd six
        r2 = self.game.roll_dice(forced_value=6)
        self.game.move_token(0)

        # 3rd six -> penalty, turn passes immediately without move
        r3 = self.game.roll_dice(forced_value=6)
        self.assertTrue(r3["consecutive_sixes_violation"])
        self.assertEqual(r3["valid_moves"], [])
        self.assertEqual(self.game.current_player.color, "green")

    def test_win_condition(self):
        # Set 3 of Red's tokens in goal, and 4th near goal
        red = self.game.players[0]
        red.tokens[0].step = STEP_GOAL
        red.tokens[1].step = STEP_GOAL
        red.tokens[2].step = STEP_GOAL
        red.tokens[3].step = 55  # Needs 1

        self.game.current_player_index = 0
        self.game.turn_state = "WAIT_ROLL"

        self.game.roll_dice(forced_value=1)
        move_res = self.game.move_token(3)

        self.assertTrue(red.has_won)
        self.assertEqual(red.finished_rank, 1)
        self.assertIn("red", self.game.winners)
        # Winning player must NOT get an extra turn; turn advances to green
        self.assertFalse(move_res["extra_turn"])
        self.assertEqual(move_res["next_player"], "green")
        self.assertEqual(self.game.current_player.color, "green")
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")
        self.assertIsNone(self.game.dice_value)

    def test_dice_cleared_on_auto_pass(self):
        res = self.game.roll_dice(forced_value=3)
        self.assertTrue(res["auto_passed"])
        self.assertIsNone(self.game.dice_value)
        self.assertEqual(self.game.current_player.color, "green")

    def test_roll_one_in_yard_allows_release(self):
        # Rolling 1 with open_on_one=True (default) allows opening token from yard
        self.assertTrue(self.game.open_on_one)
        res = self.game.roll_dice(forced_value=1)
        self.assertEqual(res["dice"], 1)
        self.assertFalse(res["auto_passed"])
        self.assertEqual(len(res["valid_moves"]), 4)  # All 4 yard tokens can open
        self.assertEqual(self.game.turn_state, "WAIT_MOVE")

        # Move token 0 out
        move_res = self.game.move_token(0)
        self.assertEqual(move_res["player"], "red")
        self.assertEqual(move_res["token_id"], 0)
        self.assertEqual(move_res["new_step"], STEP_START)
        self.assertEqual(move_res["new_global_index"], 0)
        # Crucial rule: rolling 1 does NOT grant an extra turn (only 6 does)
        self.assertFalse(move_res["extra_turn"])
        self.assertIsNone(move_res["extra_turn_reason"])
        # Turn advances to next player (Green)
        self.assertEqual(self.game.current_player.color, "green")
        self.assertEqual(self.game.turn_state, "WAIT_ROLL")

    def test_roll_one_disabled_auto_passes(self):
        # When open_on_one is disabled (classic 6-only mode), rolling 1 in yard auto-passes
        classic_game = LudoGame(self.configs, rng_seed=42, open_on_one=False)
        self.assertFalse(classic_game.open_on_one)
        res = classic_game.roll_dice(forced_value=1)
        self.assertEqual(res["dice"], 1)
        self.assertEqual(res["valid_moves"], [])
        self.assertTrue(res["auto_passed"])
        self.assertEqual(classic_game.current_player.color, "green")

    def test_roll_one_with_token_on_track_allows_choice(self):
        # 1 token on track (step 5), 3 in yard.
        # Rolling 1 should allow moving token on track (step 5 -> 6) OR opening any yard token (1, 2, 3)
        self.game.players[0].tokens[0].step = 5
        self.game.turn_state = "WAIT_ROLL"

        res = self.game.roll_dice(forced_value=1)
        self.assertEqual(set(res["valid_moves"]), {0, 1, 2, 3})

        # Test advancing token on track
        move_res = self.game.move_token(0)
        self.assertEqual(move_res["new_step"], 6)
        self.assertFalse(move_res["extra_turn"])
        self.assertEqual(self.game.current_player.color, "green")

    def test_open_on_one_in_game_state(self):
        state = self.game.get_state()
        self.assertIn("open_on_one", state)
        self.assertTrue(state["open_on_one"])
        self.assertIn("team_mode", state)

    def test_consecutive_sixes_reset_on_auto_pass(self):
        # Red has 1 token at step 55 (needs 1 to finish).
        # Rolling 6 overshoots and has no valid moves.
        # Ensure consecutive_sixes is reset to 0 instead of leaking to next turn!
        red = self.game.players[0]
        red.tokens[0].step = STEP_GOAL
        red.tokens[1].step = STEP_GOAL
        red.tokens[2].step = STEP_GOAL
        red.tokens[3].step = 55
        self.game.turn_state = "WAIT_ROLL"

        res = self.game.roll_dice(forced_value=6)
        self.assertTrue(res["auto_passed"])
        self.assertEqual(self.game.consecutive_sixes, 0, "consecutive_sixes must reset to 0 on auto_passed")

    def test_team_mode_no_friendly_fire(self):
        # In 2v2 team mode, Red and Yellow are teammates.
        team_game = LudoGame(self.configs, rng_seed=42, team_mode=True)
        self.assertTrue(team_game.team_mode)
        red = team_game.players[0]
        yellow = team_game.players[2]

        # Put Yellow token at global track index 4 (not safe).
        # Yellow start offset is 26. To be at global index 4: (26 + step) % 52 == 4 -> step = 30.
        yellow.tokens[0].step = 30
        self.assertEqual(yellow.tokens[0].global_track_index, 4)
        self.assertNotIn(4, SAFE_SQUARES)

        # Put Red token at step 0 (global index 0). Red rolls 4 -> lands on global index 4.
        red.tokens[0].step = 0
        team_game.turn_state = "WAIT_ROLL"
        team_game.current_player_index = 0

        team_game.roll_dice(forced_value=4)
        move_res = team_game.move_token(0)

        # Friendly fire check: Yellow must NOT be captured!
        self.assertEqual(move_res["captures"], [], "Teammate Yellow must not be captured by Red")
        self.assertNotEqual(yellow.tokens[0].step, STEP_YARD, "Teammate Yellow must remain on track")
        self.assertEqual(yellow.tokens[0].step, 30)

    def test_team_mode_captures_opponents(self):
        # In 2v2 team mode, Red and Green are opponents.
        team_game = LudoGame(self.configs, rng_seed=42, team_mode=True)
        red = team_game.players[0]
        green = team_game.players[1]

        # Put Green at global 4
        green.tokens[0].step = 43  # (13 + 43) % 52 = 4
        self.assertEqual(green.tokens[0].global_track_index, 4)

        # Red moves from 0 to 4 -> captures Green!
        red.tokens[0].step = 0
        team_game.turn_state = "WAIT_ROLL"
        team_game.current_player_index = 0

        team_game.roll_dice(forced_value=4)
        move_res = team_game.move_token(0)

        self.assertEqual(len(move_res["captures"]), 1, "Opponent Green must be captured")
        self.assertEqual(green.tokens[0].step, STEP_YARD)
        self.assertTrue(move_res["extra_turn"])

    def test_team_mode_partner_assist(self):
        # In 2v2 team mode, when Red finishes all 4 tokens, Red's rolls assist partner Yellow!
        team_game = LudoGame(self.configs, rng_seed=42, team_mode=True)
        red = team_game.players[0]
        yellow = team_game.players[2]

        for t in red.tokens:
            t.step = STEP_GOAL
        self.assertTrue(red.has_won)

        # Yellow has token 0 at step 5
        yellow.tokens[0].step = 5

        # It's Red's turn! Red should not be skipped; Red rolls and gets valid moves for Yellow!
        team_game.current_player_index = 0
        team_game.turn_state = "WAIT_ROLL"

        res = team_game.roll_dice(forced_value=3)
        self.assertIn(0, res["valid_moves"])

        # Red moves Yellow's token 0
        move_res = team_game.move_token(0)
        self.assertEqual(move_res["player"], "red")
        self.assertEqual(move_res["moving_color"], "yellow")
        self.assertTrue(move_res["is_partner_assist"])
        self.assertEqual(yellow.tokens[0].step, 8)

    def test_team_mode_victory(self):
        # Team Alpha (Red + Yellow) wins when BOTH Red and Yellow finish all tokens.
        team_game = LudoGame(self.configs, rng_seed=42, team_mode=True)
        red = team_game.players[0]
        yellow = team_game.players[2]

        for t in red.tokens:
            t.step = STEP_GOAL

        # Yellow has 3 in goal, 1 at step 55 (needs 1)
        yellow.tokens[0].step = STEP_GOAL
        yellow.tokens[1].step = STEP_GOAL
        yellow.tokens[2].step = STEP_GOAL
        yellow.tokens[3].step = 55

        team_game.current_player_index = 0
        team_game.turn_state = "WAIT_ROLL"

        team_game.roll_dice(forced_value=1)
        move_res = team_game.move_token(3)

        self.assertTrue(move_res["game_over"])
        self.assertEqual(team_game.turn_state, "GAME_OVER")
        self.assertEqual(move_res["winners"][:2], ["red", "yellow"])


if __name__ == "__main__":
    unittest.main()
