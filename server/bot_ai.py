"""
Intelligent Bot AI for Ludo Game
Evaluates board state and chooses optimal moves based on:
- Capturing opponent tokens
- Escaping danger
- Reaching goal
- Entering board on sixes
- Reaching safe star squares
- Distance advancement
"""

import random
from typing import List, Optional, Tuple, Dict
from .ludo_engine import LudoGame, SAFE_SQUARES, START_OFFSETS, STEP_GOAL, STEP_HOME_START, STEP_START, STEP_YARD


class BotAI:
    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"

    @staticmethod
    def choose_move(game: LudoGame, valid_token_ids: List[int], dice_value: Optional[int] = None, difficulty: str = "hard") -> int:
        """
        Chooses valid token move based on selected difficulty level:
        - 'easy': Relaxed bot, picks random legal moves 65% of the time, blunders frequently.
        - 'medium': Competent bot, captures and advances, but doesn't calculate danger evasion.
        - 'hard': Master heuristic bot with full tactical and defensive evaluation.
        """
        if not valid_token_ids:
            raise ValueError("No valid moves available for bot to choose from")

        if len(valid_token_ids) == 1:
            return valid_token_ids[0]

        diff = (difficulty or "hard").lower().strip()
        rng = getattr(game, "rng", random)

        if diff == "easy" and rng.random() < 0.65:
            return rng.choice(valid_token_ids)
        elif diff == "medium" and rng.random() < 0.25:
            return rng.choice(valid_token_ids)

        player = game.current_player
        if game.team_mode and player.has_won:
            partner = game.get_player(game.get_partner_color(player.color))
            if partner and not partner.has_won:
                player = partner

        dice = dice_value or game.dice_value or (game.dice_values[0] if game.dice_values else 1)

        best_score = -999999.0
        best_token_id = valid_token_ids[0]

        for token_id in valid_token_ids:
            score = BotAI._evaluate_move(game, player, token_id, dice, difficulty=diff)
            if score > best_score:
                best_score = score
                best_token_id = token_id

        return best_token_id

    @staticmethod
    def choose_move_two_dice(game: LudoGame, valid_moves_by_die: Dict[str, List[int]], difficulty: str = "hard") -> Tuple[int, int]:
        """
        Chooses optimal (die_value, token_id) combination in 2-dice mode with 2-step sequential planning.
        Evaluates potential two-step sequences (moving token A with die 1, then token A or B with die 2)
        versus using the combined sum directly.
        Returns: (chosen_die_value, chosen_token_id)
        """
        diff = (difficulty or "hard").lower().strip()
        rng = getattr(game, "rng", random)

        if diff == "easy" and rng.random() < 0.60:
            available = [(int(d), tid) for d, tids in valid_moves_by_die.items() for tid in tids]
            if available:
                return rng.choice(available)
        elif diff == "medium" and rng.random() < 0.20:
            available = [(int(d), tid) for d, tids in valid_moves_by_die.items() for tid in tids]
            if available:
                return rng.choice(available)

        player = game.current_player
        if game.team_mode and player.has_won:
            partner = game.get_player(game.get_partner_color(player.color))
            if partner and not partner.has_won:
                player = partner

        best_score = -999999.0
        chosen_die = None
        chosen_token = None

        remaining = getattr(game, "remaining_dice", None)
        if remaining is None:
            remaining = getattr(game, "dice_values", None)

        # 2-step sequential lookahead when 2 dice are available
        if remaining and len(remaining) == 2:
            d_a, d_b = remaining[0], remaining[1]
            d_sum = d_a + d_b
            sum_str = str(d_sum)

            # Evaluate sequential moves for both permutations: [d_a, d_b] and [d_b, d_a]
            permutations = [(d_a, d_b)]
            if d_a != d_b:
                permutations.append((d_b, d_a))

            for d1, d2 in permutations:
                d1_str = str(d1)
                if d1_str not in valid_moves_by_die:
                    continue

                for t1 in valid_moves_by_die[d1_str]:
                    score1 = BotAI._evaluate_move(game, player, t1, d1, difficulty=diff)

                    # Simulate move 1 to evaluate step 2
                    tok1 = player.tokens[t1]
                    old_step1 = tok1.step
                    captured_opps = []

                    if tok1.is_in_yard:
                        tok1.step = STEP_START
                    else:
                        tok1.step += d1

                    # Check simulated captures
                    if tok1.is_on_track and tok1.global_track_index is not None:
                        safe_sq = getattr(game, "safe_squares", SAFE_SQUARES)
                        if tok1.global_track_index not in safe_sq:
                            for opp in game.players:
                                if opp.color == player.color:
                                    continue
                                if game.team_mode and game.is_teammate(player.color, opp.color):
                                    continue
                                for opp_tok in opp.tokens:
                                    if opp_tok.is_on_track and opp_tok.global_track_index == tok1.global_track_index:
                                        captured_opps.append((opp_tok, opp_tok.step))
                                        opp_tok.step = STEP_YARD

                    # Find legal moves for d2 on simulated board
                    valid_t2 = game.get_valid_moves(d2)
                    best_score2 = 0.0
                    best_t2 = None
                    if valid_t2:
                        best_score2 = -999999.0
                        for t2 in valid_t2:
                            s2 = BotAI._evaluate_move(game, player, t2, d2, difficulty=diff)
                            if s2 > best_score2:
                                best_score2 = s2
                                best_t2 = t2

                    # Revert simulation
                    tok1.step = old_step1
                    for opp_tok, old_opp_step in captured_opps:
                        opp_tok.step = old_opp_step

                    was_yard = (old_step1 == STEP_YARD)
                    if was_yard:
                        total_seq_score = score1 + (best_score2 if best_t2 is not None else 0.0)
                    elif best_t2 == t1:
                        # Moving same token on track: evaluate full advancement from initial state plus intermediate captures
                        comb_score = BotAI._evaluate_move(game, player, t1, d1 + d2, difficulty=diff)
                        total_seq_score = comb_score + (1200.0 * len(captured_opps))
                    else:
                        total_seq_score = score1 + (best_score2 if best_t2 is not None else 0.0)

                    if total_seq_score > best_score:
                        best_score = total_seq_score
                        chosen_die = d1
                        chosen_token = t1

            # Also evaluate sum move if available
            if sum_str in valid_moves_by_die:
                for t_sum in valid_moves_by_die[sum_str]:
                    sum_score = BotAI._evaluate_move(game, player, t_sum, d_sum, difficulty=diff)
                    if sum_score >= best_score:
                        best_score = sum_score
                        chosen_die = d_sum
                        chosen_token = t_sum
        else:
            # Single die remaining or standard evaluation
            for die_str, token_ids in valid_moves_by_die.items():
                die_val = int(die_str)
                for tid in token_ids:
                    score = BotAI._evaluate_move(game, player, tid, die_val, difficulty=diff)
                    if score > best_score:
                        best_score = score
                        chosen_die = die_val
                        chosen_token = tid

        if chosen_die is None or chosen_token is None:
            # Fallback
            for die_str, token_ids in valid_moves_by_die.items():
                if token_ids:
                    return int(die_str), token_ids[0]
            raise ValueError("No valid moves across rolled dice")

        return chosen_die, chosen_token

    @staticmethod
    def _evaluate_move(game: LudoGame, player, token_id: int, dice: int, difficulty: str = "hard") -> float:
        token = player.tokens[token_id]
        score = 0.0
        diff = (difficulty or "hard").lower().strip()

        step_goal = getattr(game, "step_goal", STEP_GOAL)
        step_home_start = getattr(game, "step_home_start", STEP_HOME_START)
        step_track_max = getattr(game, "step_track_max", 50)
        track_length = getattr(game, "track_length", 52)
        safe_squares = getattr(game, "safe_squares", SAFE_SQUARES)

        # Case 1: Releasing a token from the yard
        if token.is_in_yard:
            # Bringing a token out is strong, especially if few tokens are out
            tokens_out = sum(1 for t in player.tokens if not t.is_in_yard and not t.is_in_goal)
            score += 300.0 - (tokens_out * 40.0)
            return score

        # Case 2: Moving on track or into homerun
        target_step = token.step + dice

        # Reaching the Goal
        if target_step == step_goal:
            score += 900.0
            return score

        # Entering Home Run (safe from all attacks)
        if token.step <= step_track_max and target_step >= step_home_start:
            score += 450.0

        # If target step is on outer perimeter
        if target_step <= step_track_max:
            target_global = (token.global_track_index + dice) % track_length if token.global_track_index is not None else None

            if target_global is not None:
                # Check for capture
                if target_global not in safe_squares:
                    for opp in game.players:
                        if opp.color == player.color:
                            continue
                        if game.team_mode and game.is_teammate(player.color, opp.color):
                            continue
                        for opp_token in opp.tokens:
                            if opp_token.is_on_track and opp_token.global_track_index == target_global:
                                # Capturing opponent piece is highest value!
                                score += 1200.0

                # Landing on teammate square in team mode (cooperation / safety)
                if game.team_mode:
                    partner_color = game.get_partner_color(player.color)
                    partner = game.get_player(partner_color)
                    if partner:
                        for pt in partner.tokens:
                            if pt.is_on_track and pt.global_track_index == target_global:
                                score += 250.0  # Team cooperation bonus

                # Landing on a safe square
                if target_global in safe_squares:
                    score += 350.0

                # Check if landing in enemy attack range (1..6 steps ahead of an opponent) - calculated on hard
                if diff == "hard" and target_global not in safe_squares:
                    for opp in game.players:
                        if opp.color == player.color:
                            continue
                        if game.team_mode and game.is_teammate(player.color, opp.color):
                            continue
                        for opp_token in opp.tokens:
                            if opp_token.is_on_track and opp_token.global_track_index is not None:
                                dist = (target_global - opp_token.global_track_index) % track_length
                                if 1 <= dist <= 6 and (opp_token.step + dist <= step_track_max):
                                    score -= 200.0  # Risk of being captured

        # Check if current position was in danger and this move escapes it - hard difficulty
        if diff == "hard" and token.is_on_track and token.global_track_index is not None and token.global_track_index not in safe_squares:
            for opp in game.players:
                if opp.color == player.color:
                    continue
                if game.team_mode and game.is_teammate(player.color, opp.color):
                    continue
                for opp_token in opp.tokens:
                    if opp_token.is_on_track and opp_token.global_track_index is not None:
                        dist = (token.global_track_index - opp_token.global_track_index) % track_length
                        if 1 <= dist <= 6 and (opp_token.step + dist <= step_track_max):
                            score += 300.0  # Escaping danger

        # General advancement bonus (push furthest or balance progress)
        score += target_step * 3.0

        return score
