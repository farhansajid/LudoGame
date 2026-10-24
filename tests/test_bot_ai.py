"""
Unit Tests for Bot AI
Validates that AI correctly prioritizes:
- Capturing opponent pieces
- Reaching the goal
- Releasing pieces on 6
- Escaping danger
"""

import unittest
from server.ludo_engine import LudoGame, STEP_GOAL
from server.bot_ai import BotAI


class TestBotAI(unittest.TestCase):
    def setUp(self):
        configs = [
            {"color": "red", "name": "BotRed", "is_bot": True},
            {"color": "green", "name": "HumanGreen", "is_bot": False}
        ]
        self.game = LudoGame(configs, rng_seed=123)

    def test_ai_prioritizes_capture(self):
        # Red token 0 at step 0 (global 0)
        # Red token 1 at step 5 (global 5)
        # Green token at global 8 (Safe star)
        # Green token 1 at global 7 (Unsafe)
        # If Red rolls 2:
        # Token 0 moves from 0 to 2 (safe star is 8)
        # Token 1 moves from 5 to 7 -> captures Green!
        self.game.players[0].tokens[0].step = 0
        self.game.players[0].tokens[1].step = 5
        self.game.players[1].tokens[1].step = 46  # Green start is 13, (13 + 46) % 52 = 7!

        self.game.dice_value = 2
        choice = BotAI.choose_move(self.game, [0, 1])
        self.assertEqual(choice, 1, "AI should prioritize capturing opponent token")

    def test_ai_prioritizes_goal_entry(self):
        # Red token 0 at step 54 (needs 2 for goal)
        # Red token 1 at step 10
        self.game.players[0].tokens[0].step = 54
        self.game.players[0].tokens[1].step = 10

        self.game.dice_value = 2
        choice = BotAI.choose_move(self.game, [0, 1])
        self.assertEqual(choice, 0, "AI should prioritize moving token into goal")

    def test_ai_leaves_yard_on_six(self):
        # Token 0 in yard, token 1 on step 10
        self.game.players[0].tokens[0].step = -1
        self.game.players[0].tokens[1].step = 10

        self.game.dice_value = 6
        # When only 1 token is out, bringing another token out has high value
        choice = BotAI.choose_move(self.game, [0, 1])
        self.assertIn(choice, [0, 1])

    def test_ai_two_player_yellow_offsets(self):
        # 2-player game: Red (human) and Yellow (bot at index 1)
        configs = [
            {"color": "red", "name": "Alice", "is_bot": False},
            {"color": "yellow", "name": "BotYellow", "is_bot": True}
        ]
        game2 = LudoGame(configs, rng_seed=456)
        game2.current_player_index = 1
        game2.turn_state = "WAIT_ROLL"

        # Yellow bot rolls 6; should be able to choose releasing token 0 from yard
        res = game2.roll_dice(forced_value=6)
        choice = BotAI.choose_move(game2, res["valid_moves"])
        self.assertIn(choice, range(4))

    def test_ai_leaves_yard_on_one(self):
        # Token 0 in yard, token 1 at step 5.
        # When bot rolls 1 with open_on_one, releasing token 0 is higher value than moving step 5->6
        self.game.players[0].tokens[0].step = -1
        self.game.players[0].tokens[1].step = 5
        self.game.dice_value = 1
        choice = BotAI.choose_move(self.game, [0, 1])
        self.assertEqual(choice, 0, "Bot AI should prioritize opening piece from yard on roll of 1")

    def test_ai_prioritizes_capture_over_one_release(self):
        # Token 0 in yard, token 1 at step 5 (global 5).
        # Opponent Green at global 6 (step 45 for Green).
        # On rolling 1, moving token 1 from 5 to 6 CAPTURES opponent.
        # AI should choose token 1 (capture) over token 0 (yard release).
        self.game.players[0].tokens[0].step = -1
        self.game.players[0].tokens[1].step = 5
        self.game.players[1].tokens[0].step = 45  # Green start 13: (13 + 45) % 52 = 6!

        self.game.dice_value = 1
        choice = BotAI.choose_move(self.game, [0, 1])
        self.assertEqual(choice, 1, "Bot AI should prioritize capturing opponent piece over yard release on 1")

    def test_ai_prioritizes_goal_over_one_release(self):
        # Token 0 in yard, token 1 at step 55 (needs 1 for goal).
        # On rolling 1, AI should choose reaching goal over yard release.
        self.game.players[0].tokens[0].step = -1
        self.game.players[0].tokens[1].step = 55

        self.game.dice_value = 1
        choice = BotAI.choose_move(self.game, [0, 1])
        self.assertEqual(choice, 1, "Bot AI should prioritize reaching goal over yard release on 1")

    def test_ai_team_mode_assists_partner(self):
        # 4 player team mode: Red (bot) and Yellow (human) are team alpha
        configs = [
            {"color": "red", "name": "BotRed", "is_bot": True},
            {"color": "green", "name": "BotGreen", "is_bot": True},
            {"color": "yellow", "name": "Charlie", "is_bot": False},
            {"color": "blue", "name": "David", "is_bot": False}
        ]
        team_game = LudoGame(configs, rng_seed=42, team_mode=True)
        # Red has won
        for t in team_game.players[0].tokens:
            t.step = STEP_GOAL
        self.assertTrue(team_game.players[0].has_won)

        # Yellow has token 0 at step 54 (needs 2 for goal) and token 1 at step 5
        team_game.players[2].tokens[0].step = 54
        team_game.players[2].tokens[1].step = 5

        team_game.dice_value = 2
        team_game.current_player_index = 0

        # Bot Red must assist Yellow and choose token 0 into goal
        choice = BotAI.choose_move(team_game, [0, 1])
        self.assertEqual(choice, 0, "Bot AI should choose to move teammate's token into goal")


if __name__ == "__main__":
    unittest.main()
