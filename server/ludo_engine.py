"""
Ludo Game Engine - Core Rules & State Machine
Implements standard international Ludo rules:
- 2 to 4 players (Red, Green, Yellow, Blue)
- 4 tokens per player
- 52-step perimeter track + 5 home run steps + goal
- 8 safe squares (4 start squares + 4 star squares)
- Roll 6 to release token from yard
- Extra turn on: rolling 6, capturing opponent, reaching goal
- Consecutive three 6s penalty
- Exact roll required to reach goal
"""

import random
from typing import Dict, List, Optional, Tuple, Any

PLAYER_COLORS = ["red", "green", "yellow", "blue"]
ALL_PLAYER_COLORS = ["red", "green", "yellow", "blue", "orange", "purple", "cyan", "pink"]

# Global track index for each player's starting square
START_OFFSETS = {
    "red": 0,
    "green": 13,
    "yellow": 26,
    "blue": 39,
    "orange": 52,
    "purple": 65,
    "cyan": 78,
    "pink": 91
}

# 8 Safe squares on the 4-player global track (4 starts + 4 stars)
SAFE_SQUARES = {0, 8, 13, 21, 26, 34, 39, 47}


def get_board_config(player_count: int) -> Dict[str, Any]:
    """
    Returns board parameters for player_count (2, 3, 4, 6, 8).
    For 2, 3, 4 players: standard 4-arm board (52 perimeter cells).
    For 6 players: hexagonal 6-arm board (78 perimeter cells).
    For 8 players: octagonal 8-arm board (104 perimeter cells).
    """
    if player_count <= 4:
        return {
            "board_type": 4,
            "track_length": 52,
            "step_track_max": 50,
            "step_home_start": 51,
            "step_goal": 56,
            "colors": ALL_PLAYER_COLORS[:player_count],
            "start_offsets": {c: START_OFFSETS[c] for c in ALL_PLAYER_COLORS[:4]},
            "safe_squares": {0, 8, 13, 21, 26, 34, 39, 47}
        }
    elif player_count == 6:
        colors = ALL_PLAYER_COLORS[:6]
        safe = set()
        for i, c in enumerate(colors):
            start = i * 13
            safe.add(start)
            safe.add(start + 8)
        return {
            "board_type": 6,
            "track_length": 78,
            "step_track_max": 76,
            "step_home_start": 77,
            "step_goal": 82,
            "colors": colors,
            "start_offsets": {c: i * 13 for i, c in enumerate(colors)},
            "safe_squares": safe
        }
    elif player_count == 8:
        colors = ALL_PLAYER_COLORS[:8]
        safe = set()
        for i, c in enumerate(colors):
            start = i * 13
            safe.add(start)
            safe.add(start + 8)
        return {
            "board_type": 8,
            "track_length": 104,
            "step_track_max": 102,
            "step_home_start": 103,
            "step_goal": 108,
            "colors": colors,
            "start_offsets": {c: i * 13 for i, c in enumerate(colors)},
            "safe_squares": safe
        }
    else:
        raise ValueError(f"Unsupported player count: {player_count}. Expected 2, 3, 4, 6, or 8.")

# 52 Global track grid coordinates (row, col) on a 15x15 board
TRACK_COORDINATES = [
    # Red arm (horizontal left)
    (6, 1), (6, 2), (6, 3), (6, 4), (6, 5),          # 0..4 (0 is Red start)
    # Green arm (vertical top)
    (5, 6), (4, 6), (3, 6), (2, 6), (1, 6), (0, 6),  # 5..10 (8 is Star)
    (0, 7),                                          # 11 (Green turn-in)
    (0, 8), (1, 8), (2, 8), (3, 8), (4, 8), (5, 8),  # 12..17 (13 is Green start)
    # Yellow arm (horizontal right)
    (6, 9), (6, 10), (6, 11), (6, 12), (6, 13), (6, 14), # 18..23 (21 is Star)
    (7, 14),                                         # 24 (Yellow turn-in)
    (8, 14), (8, 13), (8, 12), (8, 11), (8, 10), (8, 9), # 25..30 (26 is Yellow start)
    # Blue arm (vertical bottom)
    (9, 8), (10, 8), (11, 8), (12, 8), (13, 8), (14, 8), # 31..36 (34 is Star)
    (14, 7),                                         # 37 (Blue turn-in)
    (14, 6), (13, 6), (12, 6), (11, 6), (10, 6), (9, 6), # 38..43 (39 is Blue start)
    # Return to Red arm
    (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0),  # 44..49 (47 is Star)
    (7, 0),                                          # 50 (Red turn-in)
    (6, 0)                                           # 51
]

# Home run coordinates for each player (H1 to H5 + Goal)
HOME_RUN_COORDINATES = {
    "red": [
        (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6)
    ],
    "green": [
        (1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7)
    ],
    "yellow": [
        (7, 13), (7, 12), (7, 11), (7, 10), (7, 9), (7, 8)
    ],
    "blue": [
        (13, 7), (12, 7), (11, 7), (10, 7), (9, 7), (8, 7)
    ]
}

# Base / Yard slot coordinates for each color
YARD_COORDINATES = {
    "red": [(2, 2), (2, 3), (3, 2), (3, 3)],
    "green": [(2, 11), (2, 12), (3, 11), (3, 12)],
    "yellow": [(11, 11), (11, 12), (12, 11), (12, 12)],
    "blue": [(11, 2), (11, 3), (12, 2), (12, 3)]
}

# Step constants
STEP_YARD = -1
STEP_START = 0
STEP_TRACK_MAX = 50
STEP_HOME_START = 51
STEP_GOAL = 56


class Token:
    def __init__(
        self,
        token_id: int,
        color: str,
        track_length: int = 52,
        step_track_max: int = 50,
        step_home_start: int = 51,
        step_goal: int = 56,
        start_offset: Optional[int] = None
    ):
        self.id = token_id
        self.color = color
        self.step = STEP_YARD  # -1 = yard, 0..max = track, home_start..goal-1 = homerun, goal = finished
        self.track_length = track_length
        self.step_track_max = step_track_max
        self.step_home_start = step_home_start
        self.step_goal = step_goal
        self._start_offset = start_offset

    @property
    def start_offset(self) -> int:
        if self._start_offset is not None:
            return self._start_offset
        return START_OFFSETS.get(self.color, 0)

    @property
    def is_in_yard(self) -> bool:
        return self.step == STEP_YARD

    @property
    def is_on_track(self) -> bool:
        return 0 <= self.step <= self.step_track_max

    @property
    def is_in_homerun(self) -> bool:
        return self.step_home_start <= self.step < self.step_goal

    @property
    def is_in_goal(self) -> bool:
        return self.step == self.step_goal

    @property
    def global_track_index(self) -> Optional[int]:
        if self.is_on_track:
            return (self.start_offset + self.step) % self.track_length
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "color": self.color,
            "step": self.step,
            "is_in_yard": self.is_in_yard,
            "is_on_track": self.is_on_track,
            "is_in_homerun": self.is_in_homerun,
            "is_in_goal": self.is_in_goal,
            "global_index": self.global_track_index
        }


class Player:
    def __init__(
        self,
        color: str,
        name: str,
        is_bot: bool = False,
        avatar: str = "default",
        track_length: int = 52,
        step_track_max: int = 50,
        step_home_start: int = 51,
        step_goal: int = 56,
        start_offset: Optional[int] = None
    ):
        self.color = color
        self.name = name
        self.is_bot = is_bot
        self.avatar = avatar
        self.tokens = [
            Token(i, color, track_length, step_track_max, step_home_start, step_goal, start_offset)
            for i in range(4)
        ]
        self.finished_rank: Optional[int] = None

    @property
    def has_won(self) -> bool:
        return all(t.is_in_goal for t in self.tokens)

    @property
    def tokens_in_goal_count(self) -> int:
        return sum(1 for t in self.tokens if t.is_in_goal)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "color": self.color,
            "name": self.name,
            "is_bot": self.is_bot,
            "avatar": self.avatar,
            "tokens": [t.to_dict() for t in self.tokens],
            "finished_rank": self.finished_rank,
            "tokens_in_goal": self.tokens_in_goal_count,
            "has_won": self.has_won
        }


class LudoGame:
    def __init__(
        self,
        player_configs: List[Dict[str, Any]],
        rng_seed: Optional[int] = None,
        open_on_one: bool = True,
        team_mode: bool = False,
        two_dice_mode: bool = False,
        board_type: Optional[int] = None
    ):
        """
        player_configs: list of dicts:
        [{ "color": "red", "name": "Player 1", "is_bot": False, "avatar": "lion" }, ...]
        Supports 2, 3, 4, 6, and 8 players.
        open_on_one: if True, tokens in yard can open on rolling a 1 or a 6 (Fast Boost rule).
        team_mode: if True and 4 players, 2v2 partnership rules apply (Red & Yellow vs Green & Blue).
        two_dice_mode: if True, two dice are rolled and player selects which die to step with.
        board_type: optional override (4, 6, 8). Defaults to 6 for 6 players, 8 for 8 players, else 4.
        """
        num_players = len(player_configs)
        if num_players not in (2, 3, 4, 6, 8):
            raise ValueError(f"Ludo requires 2, 3, 4, 6, or 8 players (got {num_players})")

        self.rng = random.Random(rng_seed)
        self.open_on_one = open_on_one
        self._team_mode = bool(team_mode and num_players == 4)
        self.two_dice_mode = bool(two_dice_mode)

        if board_type in (4, 6, 8):
            self.board_type = board_type
        elif num_players == 6:
            self.board_type = 6
        elif num_players == 8:
            self.board_type = 8
        else:
            self.board_type = 4

        b_cfg = get_board_config(self.board_type)
        self.track_length = b_cfg["track_length"]
        self.step_track_max = b_cfg["step_track_max"]
        self.step_home_start = b_cfg["step_home_start"]
        self.step_goal = b_cfg["step_goal"]
        self.safe_squares = set(b_cfg["safe_squares"])
        self.start_offsets = dict(b_cfg["start_offsets"])

        self.players: List[Player] = []
        for cfg in player_configs:
            col = cfg["color"]
            s_off = self.start_offsets.get(col, START_OFFSETS.get(col, 0))
            self.players.append(Player(
                color=col,
                name=cfg.get("name", col.capitalize()),
                is_bot=cfg.get("is_bot", False),
                avatar=cfg.get("avatar", "default"),
                track_length=self.track_length,
                step_track_max=self.step_track_max,
                step_home_start=self.step_home_start,
                step_goal=self.step_goal,
                start_offset=s_off
            ))

        self.current_player_index = 0
        self.dice_value: Optional[int] = None
        self.dice_values: Optional[List[int]] = None
        self.remaining_dice: List[int] = []
        self.used_dice: List[int] = []
        self.selected_die: Optional[int] = None
        self.turn_state: str = "WAIT_ROLL"  # "WAIT_ROLL", "WAIT_MOVE", "GAME_OVER"
        self.consecutive_sixes: int = 0
        self.extra_turn_awarded: bool = False
        self.extra_turn_reason: Optional[str] = None
        self.winners: List[str] = []  # Colors in order of winning
        self.move_history: List[Dict[str, Any]] = []

    @property
    def team_mode(self) -> bool:
        return self._team_mode

    @team_mode.setter
    def team_mode(self, val: bool):
        self._team_mode = bool(val and len(self.players) == 4)

    def is_teammate(self, color1: str, color2: str) -> bool:
        if not self.team_mode or color1 == color2:
            return False
        partner = self.get_partner_color(color1)
        return partner == color2

    def get_partner_color(self, color: str) -> Optional[str]:
        if not self.team_mode:
            return None
        pairs = {
            "red": "yellow",
            "yellow": "red",
            "green": "blue",
            "blue": "green"
        }
        return pairs.get(color)

    def get_player(self, color: Optional[str]) -> Optional[Player]:
        if not color:
            return None
        for p in self.players:
            if p.color == color:
                return p
        return None

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    @property
    def dice_sum(self) -> Optional[int]:
        if self.two_dice_mode and self.dice_values and len(self.dice_values) >= 2:
            return sum(self.dice_values)
        return None

    def roll_dice(self, forced_value: Optional[Any] = None) -> Dict[str, Any]:
        """
        Rolls the dice for current player.
        Supports 1-die mode and 2-dice mode.
        """
        if self.turn_state != "WAIT_ROLL":
            raise ValueError(f"Cannot roll dice in state {self.turn_state}")

        rolling_player_color = self.current_player.color

        if self.two_dice_mode:
            if forced_value is not None:
                if isinstance(forced_value, (list, tuple)):
                    vals = [int(forced_value[0]), int(forced_value[1])]
                else:
                    vals = [int(forced_value), int(forced_value)]
            else:
                vals = [self.rng.randint(1, 6), self.rng.randint(1, 6)]

            self.dice_values = vals
            self.remaining_dice = list(vals)
            self.used_dice = []
            self.extra_turn_awarded = False
            self.extra_turn_reason = None
            self.selected_die = None
            self.dice_value = None

            # Three consecutive double-sixes penalty
            if vals[0] == 6 and vals[1] == 6:
                self.consecutive_sixes += 1
            else:
                self.consecutive_sixes = 0

            if self.consecutive_sixes == 3:
                self.consecutive_sixes = 0
                self.turn_state = "WAIT_ROLL"
                next_color = self._advance_turn()
                self.dice_value = None
                self.dice_values = None
                self.remaining_dice = []
                self.used_dice = []
                penalty_info = {
                    "player": rolling_player_color,
                    "dice": vals[0],
                    "dice_values": vals,
                    "remaining_dice": [],
                    "used_dice": [],
                    "consecutive_sixes_violation": True,
                    "valid_moves": [],
                    "valid_moves_by_die": {str(vals[0]): [], str(vals[1]): []},
                    "next_player": next_color
                }
                self.move_history.append(penalty_info)
                return penalty_info

            # Check valid moves for both dice as well as combined sum of both dice
            valid_d0 = self.get_valid_moves(vals[0])
            valid_d1 = self.get_valid_moves(vals[1])
            dice_sum = vals[0] + vals[1]
            valid_sum = self.get_valid_moves(dice_sum)
            combined_moves = sorted(list(set(valid_d0 + valid_d1 + valid_sum)))

            if not combined_moves:
                # No moves possible with either die or sum
                self.consecutive_sixes = 0
                self.turn_state = "WAIT_ROLL"
                next_color = self._advance_turn()
                self.dice_value = None
                self.dice_values = None
                self.remaining_dice = []
                self.used_dice = []
                result = {
                    "player": rolling_player_color,
                    "dice": vals[0],
                    "dice_values": vals,
                    "remaining_dice": [],
                    "used_dice": [],
                    "dice_sum": dice_sum,
                    "consecutive_sixes_violation": False,
                    "valid_moves": [],
                    "valid_moves_by_die": {str(vals[0]): [], str(vals[1]): []},
                    "valid_moves_sum": [],
                    "auto_passed": True,
                    "next_player": next_color
                }
                self.move_history.append(result)
                return result

            # If only one die has valid moves, auto-select it
            if valid_d0 and not valid_d1 and not valid_sum:
                self.selected_die = vals[0]
                self.dice_value = vals[0]
            elif valid_d1 and not valid_d0 and not valid_sum:
                self.selected_die = vals[1]
                self.dice_value = vals[1]

            self.turn_state = "WAIT_MOVE"
            return {
                "player": rolling_player_color,
                "dice": self.dice_value or vals[0],
                "dice_values": vals,
                "remaining_dice": list(self.remaining_dice),
                "used_dice": list(self.used_dice),
                "dice_sum": dice_sum,
                "selected_die": self.selected_die,
                "consecutive_sixes_violation": False,
                "valid_moves": combined_moves,
                "valid_moves_by_die": {str(vals[0]): valid_d0, str(vals[1]): valid_d1},
                "valid_moves_sum": valid_sum,
                "auto_passed": False,
                "next_player": rolling_player_color
            }

        else:
            # 1 die mode
            val = forced_value if forced_value is not None else self.rng.randint(1, 6)
            self.dice_value = val
            self.dice_values = [val]
            self.remaining_dice = [val]
            self.used_dice = []
            self.extra_turn_awarded = False
            self.extra_turn_reason = None
            self.selected_die = val

            if val == 6:
                self.consecutive_sixes += 1
            else:
                self.consecutive_sixes = 0

            # Three consecutive sixes rule
            if self.consecutive_sixes == 3:
                self.consecutive_sixes = 0
                self.turn_state = "WAIT_ROLL"
                next_color = self._advance_turn()
                self.dice_value = None
                self.dice_values = None
                self.remaining_dice = []
                self.used_dice = []
                penalty_info = {
                    "player": rolling_player_color,
                    "dice": val,
                    "dice_values": [val],
                    "remaining_dice": [],
                    "used_dice": [],
                    "consecutive_sixes_violation": True,
                    "valid_moves": [],
                    "next_player": next_color
                }
                self.move_history.append(penalty_info)
                return penalty_info

            valid_token_ids = self.get_valid_moves(val)

            if not valid_token_ids:
                # No valid moves: turn passes automatically
                self.consecutive_sixes = 0
                self.turn_state = "WAIT_ROLL"
                next_color = self._advance_turn()
                self.dice_value = None
                self.dice_values = None
                self.remaining_dice = []
                self.used_dice = []
                result = {
                    "player": rolling_player_color,
                    "dice": val,
                    "dice_values": [val],
                    "remaining_dice": [],
                    "used_dice": [],
                    "consecutive_sixes_violation": False,
                    "valid_moves": [],
                    "auto_passed": True,
                    "next_player": next_color
                }
                self.move_history.append(result)
                return result

            self.turn_state = "WAIT_MOVE"
            return {
                "player": rolling_player_color,
                "dice": val,
                "dice_values": [val],
                "remaining_dice": list(self.remaining_dice),
                "used_dice": list(self.used_dice),
                "consecutive_sixes_violation": False,
                "valid_moves": valid_token_ids,
                "auto_passed": False,
                "next_player": rolling_player_color
            }

    def select_die(self, die_value: int) -> Dict[str, Any]:
        """Sets active die value in 2-dice mode and returns valid moves for it."""
        if not self.two_dice_mode or self.turn_state != "WAIT_MOVE":
            raise ValueError("Cannot select die in current game state")
        available_dice = self.remaining_dice if self.remaining_dice else (self.dice_values or [])
        if not available_dice:
            raise ValueError("Cannot select die with no remaining dice")
        dice_sum = sum(available_dice) if len(available_dice) == 2 else None
        if die_value not in available_dice and (dice_sum is None or die_value != dice_sum):
            raise ValueError(f"Die value {die_value} is not among available dice {available_dice} or sum {dice_sum}")

        self.selected_die = die_value
        self.dice_value = die_value
        valid_moves = self.get_valid_moves(die_value)
        return {
            "selected_die": die_value,
            "valid_moves": valid_moves,
            "remaining_dice": list(self.remaining_dice),
            "used_dice": list(self.used_dice)
        }

    def get_valid_moves(self, dice_value: Optional[int] = None) -> List[int]:
        """Returns list of token IDs (0..3) that can legally move with dice_value."""
        val = dice_value if dice_value is not None else self.dice_value
        if val is None:
            if self.two_dice_mode and self.remaining_dice:
                m_all = []
                for d in self.remaining_dice:
                    m_all.extend(self.get_valid_moves(d))
                if len(self.remaining_dice) == 2:
                    m_all.extend(self.get_valid_moves(sum(self.remaining_dice)))
                return sorted(list(set(m_all)))
            elif self.two_dice_mode and self.dice_values:
                m0 = self.get_valid_moves(self.dice_values[0])
                m1 = self.get_valid_moves(self.dice_values[1])
                ms = self.get_valid_moves(sum(self.dice_values))
                return sorted(list(set(m0 + m1 + ms)))
            return []

        player = self.current_player
        moving_player = player
        if self.team_mode and player.has_won:
            partner = self.get_player(self.get_partner_color(player.color))
            if partner and not partner.has_won:
                moving_player = partner

        valid_moves = []
        for token in moving_player.tokens:
            if token.is_in_goal:
                continue

            if token.is_in_yard:
                if val == 6 or (self.open_on_one and val == 1):
                    valid_moves.append(token.id)
            else:
                target_step = token.step + val
                if target_step <= self.step_goal:
                    valid_moves.append(token.id)

        return valid_moves

    def move_token(self, token_id: int, selected_die: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes move for token_id.
        Returns outcome including captures, extra turn, win state, next player, and escaped_danger.
        """
        if self.turn_state != "WAIT_MOVE":
            raise ValueError(f"Cannot move token in state {self.turn_state}")

        # Resolve selected die in 2-dice mode if needed
        consumed_dice = []
        if self.two_dice_mode:
            avail = self.remaining_dice if self.remaining_dice else (self.dice_values or [])
            dice_sum = sum(avail) if len(avail) == 2 else None

            if selected_die is not None:
                if dice_sum is not None and selected_die == dice_sum:
                    self.selected_die = dice_sum
                    self.dice_value = dice_sum
                    consumed_dice = list(avail)
                elif selected_die in avail:
                    self.selected_die = selected_die
                    self.dice_value = selected_die
                    consumed_dice = [selected_die]
                else:
                    raise ValueError(f"Selected die {selected_die} not available in {avail}")
            elif self.selected_die is not None:
                if dice_sum is not None and self.selected_die == dice_sum:
                    consumed_dice = list(avail)
                elif self.selected_die in avail:
                    consumed_dice = [self.selected_die]
                else:
                    self.selected_die = None

            if not consumed_dice:
                # Infer die based on token_id validity
                candidates = []
                for d in avail:
                    if token_id in self.get_valid_moves(d):
                        candidates.append((d, [d]))
                if dice_sum is not None and token_id in self.get_valid_moves(dice_sum):
                    candidates.append((dice_sum, list(avail)))

                if not candidates:
                    raise ValueError(f"Token {token_id} cannot move with available dice {avail}")

                chosen_val, c_dice = candidates[0]
                self.selected_die = chosen_val
                self.dice_value = chosen_val
                consumed_dice = c_dice
        else:
            consumed_dice = [self.dice_value]

        valid_token_ids = self.get_valid_moves(self.dice_value)
        if token_id not in valid_token_ids:
            raise ValueError(f"Token {token_id} cannot move with dice {self.dice_value}")

        player = self.current_player
        moving_player = player
        is_partner_assist = False
        if self.team_mode and player.has_won:
            partner = self.get_player(self.get_partner_color(player.color))
            if partner and not partner.has_won:
                moving_player = partner
                is_partner_assist = True

        token = moving_player.tokens[token_id]
        dice = self.dice_value
        selected_die_used = self.selected_die
        old_step = token.step

        # Danger assessment before the move
        was_in_danger = False
        if token.is_on_track and token.global_track_index is not None and token.global_track_index not in self.safe_squares:
            old_global = token.global_track_index
            for opp in self.players:
                if opp.color == moving_player.color:
                    continue
                if self.team_mode and self.is_teammate(moving_player.color, opp.color):
                    continue
                for opp_tok in opp.tokens:
                    if opp_tok.is_on_track and opp_tok.global_track_index is not None:
                        dist = (old_global - opp_tok.global_track_index) % self.track_length
                        if 1 <= dist <= 6 and (opp_tok.step + dist <= self.step_track_max):
                            was_in_danger = True
                            break
                if was_in_danger:
                    break

        captures: List[Dict[str, Any]] = []
        reached_goal = False

        if token.is_in_yard:
            token.step = STEP_START
        else:
            token.step += dice

        if token.is_in_goal:
            reached_goal = True
            self.extra_turn_awarded = True
            self.extra_turn_reason = "reached_goal"

            # Check if player finished
            if moving_player.has_won and moving_player.finished_rank is None:
                moving_player.finished_rank = len(self.winners) + 1
                self.winners.append(moving_player.color)

        # Check for captures on perimeter track
        if token.is_on_track:
            token_global = token.global_track_index
            if token_global not in self.safe_squares:
                # Capture any opponent tokens on this square (teammates protected)
                for opp in self.players:
                    if opp.color == moving_player.color:
                        continue
                    if self.team_mode and self.is_teammate(moving_player.color, opp.color):
                        continue
                    for opp_token in opp.tokens:
                        if opp_token.is_on_track and opp_token.global_track_index == token_global:
                            # Capture!
                            opp_token.step = STEP_YARD
                            captures.append({
                                "player": opp.color,
                                "token_id": opp_token.id,
                                "global_index": token_global
                            })
                            self.extra_turn_awarded = True
                            self.extra_turn_reason = "captured_piece"

        # Check escaped danger after move
        escaped_danger = False
        if was_in_danger:
            if token.is_in_goal or token.is_in_homerun or (token.is_on_track and token.global_track_index in self.safe_squares):
                escaped_danger = True
            elif token.is_on_track and token.global_track_index is not None:
                new_g = token.global_track_index
                still_in_danger = False
                for opp in self.players:
                    if opp.color == moving_player.color:
                        continue
                    if self.team_mode and self.is_teammate(moving_player.color, opp.color):
                        continue
                    for opp_tok in opp.tokens:
                        if opp_tok.is_on_track and opp_tok.global_track_index is not None:
                            dist = (new_g - opp_tok.global_track_index) % self.track_length
                            if 1 <= dist <= 6 and (opp_tok.step + dist <= self.step_track_max):
                                still_in_danger = True
                                break
                    if still_in_danger:
                        break
                if not still_in_danger:
                    escaped_danger = True

        # Six gives extra turn unless already awarded (checking both direct die and consumed dice)
        if (dice == 6 or (consumed_dice and 6 in consumed_dice)) and not self.extra_turn_awarded:
            self.extra_turn_awarded = True
            self.extra_turn_reason = "rolled_six"

        # Consume used dice
        if self.two_dice_mode:
            for cd in consumed_dice:
                if cd in self.remaining_dice:
                    self.remaining_dice.remove(cd)
                self.used_dice.append(cd)
        else:
            self.remaining_dice = []
            if self.dice_value is not None:
                self.used_dice.append(self.dice_value)

        # Check game over condition
        game_over = False
        extra_turn = False
        extra_turn_reason: Optional[str] = None
        if self.team_mode:
            red = self.get_player("red")
            yellow = self.get_player("yellow")
            green = self.get_player("green")
            blue = self.get_player("blue")

            team_alpha_won = bool(red and red.has_won and yellow and yellow.has_won)
            team_bravo_won = bool(green and green.has_won and blue and blue.has_won)
            game_over = team_alpha_won or team_bravo_won

            if game_over:
                self.turn_state = "GAME_OVER"
                self.dice_value = None
                self.dice_values = None
                self.remaining_dice = []
                self.used_dice = []
                self.selected_die = None
                winning_team = ["red", "yellow"] if team_alpha_won else ["green", "blue"]
                losing_team = ["green", "blue"] if team_alpha_won else ["red", "yellow"]
                self.winners = winning_team + losing_team
                next_player_color = None
                turn_complete = True
            else:
                turn_complete = False
                if self.two_dice_mode and self.remaining_dice:
                    rem_die = self.remaining_dice[0]
                    valid_rem = self.get_valid_moves(rem_die)
                    if valid_rem:
                        turn_complete = False
                        self.turn_state = "WAIT_MOVE"
                        self.selected_die = None
                        self.dice_value = None
                        next_player_color = player.color
                    else:
                        turn_complete = True
                else:
                    turn_complete = True

                if turn_complete:
                    extra_turn = self.extra_turn_awarded
                    extra_turn_reason = self.extra_turn_reason

                    if player.has_won and not is_partner_assist:
                        extra_turn = False
                        extra_turn_reason = None
                        self.consecutive_sixes = 0
                        next_player_color = self._advance_turn()
                    elif extra_turn:
                        next_player_color = player.color
                    else:
                        self.consecutive_sixes = 0
                        next_player_color = self._advance_turn()

                    self.dice_value = None
                    self.dice_values = None
                    self.remaining_dice = []
                    self.used_dice = []
                    self.selected_die = None
                    self.turn_state = "WAIT_ROLL"
                    self.extra_turn_awarded = False
                    self.extra_turn_reason = None
                else:
                    extra_turn = False
                    extra_turn_reason = None
        else:
            active_unfinished = [p for p in self.players if not p.has_won]
            game_over = len(active_unfinished) <= 1

            if game_over:
                self.turn_state = "GAME_OVER"
                self.dice_value = None
                self.dice_values = None
                self.remaining_dice = []
                self.used_dice = []
                self.selected_die = None
                for p in active_unfinished:
                    if p.finished_rank is None:
                        p.finished_rank = len(self.winners) + 1
                        self.winners.append(p.color)
                next_player_color = None
                turn_complete = True
            else:
                turn_complete = False
                if self.two_dice_mode and self.remaining_dice:
                    rem_die = self.remaining_dice[0]
                    valid_rem = self.get_valid_moves(rem_die)
                    if valid_rem:
                        turn_complete = False
                        self.turn_state = "WAIT_MOVE"
                        self.selected_die = None
                        self.dice_value = None
                        next_player_color = player.color
                    else:
                        turn_complete = True
                else:
                    turn_complete = True

                if turn_complete:
                    extra_turn = self.extra_turn_awarded
                    extra_turn_reason = self.extra_turn_reason

                    if player.has_won:
                        extra_turn = False
                        extra_turn_reason = None
                        self.consecutive_sixes = 0
                        next_player_color = self._advance_turn()
                    elif extra_turn:
                        next_player_color = player.color
                    else:
                        self.consecutive_sixes = 0
                        next_player_color = self._advance_turn()

                    self.dice_value = None
                    self.dice_values = None
                    self.remaining_dice = []
                    self.used_dice = []
                    self.selected_die = None
                    self.turn_state = "WAIT_ROLL"
                    self.extra_turn_awarded = False
                    self.extra_turn_reason = None
                else:
                    extra_turn = False
                    extra_turn_reason = None

        result = {
            "player": player.color,
            "moving_color": moving_player.color,
            "is_partner_assist": is_partner_assist,
            "token_id": token_id,
            "dice": dice,
            "dice_values": self.dice_values,
            "remaining_dice": list(self.remaining_dice),
            "used_dice": list(self.used_dice),
            "turn_complete": turn_complete,
            "selected_die": selected_die_used,
            "old_step": old_step,
            "new_step": token.step,
            "new_global_index": token.global_track_index,
            "captures": captures,
            "reached_goal": reached_goal,
            "escaped_danger": escaped_danger,
            "extra_turn": extra_turn,
            "extra_turn_reason": extra_turn_reason,
            "pending_extra_turn": bool(self.extra_turn_awarded and not turn_complete),
            "bonus_roll_awarded": bool(extra_turn and extra_turn_reason == "captured_piece"),
            "game_over": game_over,
            "winners": list(self.winners),
            "next_player": next_player_color,
            "team_mode": self.team_mode
        }
        self.move_history.append(result)
        return result

    def pass_remaining(self) -> Dict[str, Any]:
        """Concludes turn by forfeiting any unused remaining dice in 2-dice mode."""
        if self.turn_state != "WAIT_MOVE":
            raise ValueError(f"Cannot pass turn in state {self.turn_state}")
        if not self.two_dice_mode:
            raise ValueError("Cannot pass turn in single-die mode")

        player = self.current_player
        passed_dice = list(self.remaining_dice)

        extra_turn = self.extra_turn_awarded
        extra_turn_reason = self.extra_turn_reason

        is_partner_assist = False
        if self.team_mode and player.has_won:
            partner = self.get_player(self.get_partner_color(player.color))
            if partner and not partner.has_won:
                is_partner_assist = True

        if player.has_won and not is_partner_assist:
            extra_turn = False
            extra_turn_reason = None
            self.consecutive_sixes = 0
            next_player_color = self._advance_turn()
        elif extra_turn:
            next_player_color = player.color
        else:
            self.consecutive_sixes = 0
            next_player_color = self._advance_turn()

        self.dice_value = None
        self.dice_values = None
        self.remaining_dice = []
        self.used_dice = []
        self.selected_die = None
        self.turn_state = "WAIT_ROLL"
        self.extra_turn_awarded = False
        self.extra_turn_reason = None

        result = {
            "player": player.color,
            "passed_dice": passed_dice,
            "turn_complete": True,
            "extra_turn": extra_turn,
            "extra_turn_reason": extra_turn_reason,
            "next_player": next_player_color
        }
        self.move_history.append(result)
        return result

    def _advance_turn(self) -> str:
        """Advances turn to the next player who has not finished yet (or whose partner hasn't finished in team mode)."""
        num_players = len(self.players)
        for _ in range(num_players):
            self.current_player_index = (self.current_player_index + 1) % num_players
            candidate = self.players[self.current_player_index]
            if not candidate.has_won:
                return candidate.color
            if self.team_mode:
                partner = self.get_player(self.get_partner_color(candidate.color))
                if partner and not partner.has_won:
                    return candidate.color

        # If everyone has won
        self.turn_state = "GAME_OVER"
        return self.players[0].color

    def get_state(self) -> Dict[str, Any]:
        """Returns the complete serializable game state."""
        dice_sum = sum(self.remaining_dice) if (self.two_dice_mode and len(self.remaining_dice) == 2) else None
        valid_moves_sum = self.get_valid_moves(dice_sum) if (dice_sum is not None and self.turn_state == "WAIT_MOVE") else []
        valid_moves_by_die = {}
        if self.two_dice_mode and self.remaining_dice and self.turn_state == "WAIT_MOVE":
            for d in self.remaining_dice:
                valid_moves_by_die[str(d)] = self.get_valid_moves(d)

        return {
            "players": [p.to_dict() for p in self.players],
            "current_player": self.current_player.color,
            "current_player_index": self.current_player_index,
            "turn_state": self.turn_state,
            "dice_value": self.dice_value,
            "dice_values": self.dice_values,
            "remaining_dice": list(self.remaining_dice),
            "used_dice": list(self.used_dice),
            "dice_sum": dice_sum,
            "selected_die": self.selected_die,
            "two_dice_mode": self.two_dice_mode,
            "board_type": self.board_type,
            "track_length": self.track_length,
            "step_track_max": self.step_track_max,
            "step_home_start": self.step_home_start,
            "step_goal": self.step_goal,
            "valid_moves": self.get_valid_moves() if self.turn_state == "WAIT_MOVE" else [],
            "valid_moves_by_die": valid_moves_by_die,
            "valid_moves_sum": valid_moves_sum,
            "consecutive_sixes": self.consecutive_sixes,
            "winners": list(self.winners),
            "game_over": self.turn_state == "GAME_OVER",
            "open_on_one": self.open_on_one,
            "team_mode": self.team_mode
        }
