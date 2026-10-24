"""
Full Game End-to-End Simulation Tests
Simulates complete 2-player, 3-player, and 4-player AI matches to verify:
- No deadlocks or infinite loops
- Finishing ranks (1st, 2nd, 3rd, 4th) correctly assigned
- State machine correctly reaches GAME_OVER
"""
import unittest
from server.ludo_engine import LudoGame
from server.bot_ai import BotAI


class TestGameSimulation(unittest.TestCase):
    def test_full_4_player_match_simulation(self):
        for seed in [42, 101, 777]:
            configs = [
                {"color": "red", "name": "Bot Red", "is_bot": True},
                {"color": "green", "name": "Bot Green", "is_bot": True},
                {"color": "yellow", "name": "Bot Yellow", "is_bot": True},
                {"color": "blue", "name": "Bot Blue", "is_bot": True}
            ]
            game = LudoGame(configs, rng_seed=seed)
            turns = 0
            max_turns = 3000

            while game.turn_state != "GAME_OVER" and turns < max_turns:
                turns += 1
                if game.turn_state == "WAIT_ROLL":
                    roll_res = game.roll_dice()
                    if roll_res.get("auto_passed") or roll_res.get("consecutive_sixes_violation"):
                        continue
                if game.turn_state == "WAIT_MOVE":
                    valid_moves = game.get_valid_moves()
                    if not valid_moves:
                        break
                    token_id = BotAI.choose_move(game, valid_moves)
                    game.move_token(token_id)

            self.assertEqual(game.turn_state, "GAME_OVER")
            self.assertEqual(len(game.winners), 4)
            # Ranks must be 1, 2, 3, 4
            ranks = [p.finished_rank for p in game.players]
            self.assertEqual(sorted(ranks), [1, 2, 3, 4])

    def test_full_2_player_match_simulation(self):
        configs = [
            {"color": "red", "name": "Bot Red", "is_bot": True},
            {"color": "yellow", "name": "Bot Yellow", "is_bot": True}
        ]
        game = LudoGame(configs, rng_seed=999)
        turns = 0
        max_turns = 2000

        while game.turn_state != "GAME_OVER" and turns < max_turns:
            turns += 1
            if game.turn_state == "WAIT_ROLL":
                roll_res = game.roll_dice()
                if roll_res.get("auto_passed") or roll_res.get("consecutive_sixes_violation"):
                    continue
            if game.turn_state == "WAIT_MOVE":
                valid_moves = game.get_valid_moves()
                if not valid_moves:
                    break
                token_id = BotAI.choose_move(game, valid_moves)
                game.move_token(token_id)

        self.assertEqual(game.turn_state, "GAME_OVER")
        self.assertEqual(len(game.winners), 2)
        ranks = [p.finished_rank for p in game.players]
        self.assertEqual(sorted(ranks), [1, 2])

    def test_full_match_simulation_classic_mode(self):
        # Verify 4-player match completes with open_on_one=False
        configs = [
            {"color": "red", "name": "Classic Red", "is_bot": True},
            {"color": "green", "name": "Classic Green", "is_bot": True},
            {"color": "yellow", "name": "Classic Yellow", "is_bot": True},
            {"color": "blue", "name": "Classic Blue", "is_bot": True}
        ]
        game = LudoGame(configs, rng_seed=555, open_on_one=False)
        turns = 0
        max_turns = 3500

        while game.turn_state != "GAME_OVER" and turns < max_turns:
            turns += 1
            if game.turn_state == "WAIT_ROLL":
                roll_res = game.roll_dice()
                if roll_res.get("auto_passed") or roll_res.get("consecutive_sixes_violation"):
                    continue
            if game.turn_state == "WAIT_MOVE":
                valid_moves = game.get_valid_moves()
                if not valid_moves:
                    break
                token_id = BotAI.choose_move(game, valid_moves)
                game.move_token(token_id)

        self.assertEqual(game.turn_state, "GAME_OVER")
        self.assertEqual(len(game.winners), 4)
        ranks = [p.finished_rank for p in game.players]
        self.assertEqual(sorted(ranks), [1, 2, 3, 4])

    def test_full_team_mode_match_simulation(self):
        # Verify 4-player 2v2 team match completes with team_mode=True
        for seed in [123, 888]:
            configs = [
                {"color": "red", "name": "TeamA Red", "is_bot": True},
                {"color": "green", "name": "TeamB Green", "is_bot": True},
                {"color": "yellow", "name": "TeamA Yellow", "is_bot": True},
                {"color": "blue", "name": "TeamB Blue", "is_bot": True}
            ]
            game = LudoGame(configs, rng_seed=seed, team_mode=True)
            self.assertTrue(game.team_mode)
            turns = 0
            max_turns = 3500

            while game.turn_state != "GAME_OVER" and turns < max_turns:
                turns += 1
                if game.turn_state == "WAIT_ROLL":
                    roll_res = game.roll_dice()
                    if roll_res.get("auto_passed") or roll_res.get("consecutive_sixes_violation"):
                        continue
                if game.turn_state == "WAIT_MOVE":
                    valid_moves = game.get_valid_moves()
                    if not valid_moves:
                        break
                    token_id = BotAI.choose_move(game, valid_moves)
                    game.move_token(token_id)

            self.assertEqual(game.turn_state, "GAME_OVER")
            self.assertEqual(len(game.winners), 4)
            # Winning team must be either red+yellow or green+blue
            winner_team = set(game.winners[:2])
            self.assertIn(winner_team, [{"red", "yellow"}, {"green", "blue"}])


if __name__ == "__main__":
    unittest.main()
