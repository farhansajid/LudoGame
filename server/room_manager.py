"""
Room Manager for Ludo Game
Manages:
- Game rooms (multiplayer LAN, pass-and-play, single-player vs AI)
- Slot assignments (human players & AI bots)
- Bot automated turns with async delays for realistic gameplay
- Spectators, chat messages, and emoji reactions
- Game state broadcasts
"""

import asyncio
import logging
import random
import string
from typing import Dict, List, Optional, Any
from aiohttp import web

from .ludo_engine import LudoGame, PLAYER_COLORS, ALL_PLAYER_COLORS
from .bot_ai import BotAI

logger = logging.getLogger("room_manager")


class RoomPlayer:
    def __init__(self, session_id: Optional[str], name: str, color: str, is_bot: bool = False, avatar: str = "lion"):
        self.session_id = session_id
        self.name = name
        self.color = color
        self.is_bot = is_bot
        self.avatar = avatar
        self.is_host = False
        self.is_ready = False
        self.is_connected = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "color": self.color,
            "is_bot": self.is_bot,
            "avatar": self.avatar,
            "is_host": self.is_host,
            "is_ready": self.is_ready,
            "is_connected": self.is_connected
        }


class GameRoom:
    def __init__(self, room_id: str, host_session_id: str, mode: str = "online", player_count: int = 4, open_on_one: bool = True, team_mode: bool = False, two_dice_mode: bool = False, difficulty: str = "hard"):
        self.room_id = room_id
        self.host_session_id = host_session_id
        self.mode = mode  # "online", "single", "local"
        self.max_players = player_count
        self.open_on_one = open_on_one
        self.team_mode = team_mode and player_count == 4
        self.two_dice_mode = bool(two_dice_mode)
        self.difficulty = difficulty or "hard"
        self.players: List[RoomPlayer] = []
        self.sockets: Dict[str, web.WebSocketResponse] = {}  # session_id -> ws
        self.game: Optional[LudoGame] = None
        self.status = "LOBBY"  # "LOBBY", "PLAYING", "FINISHED"
        self.bot_task: Optional[asyncio.Task] = None

    def get_player_by_session(self, session_id: str) -> Optional[RoomPlayer]:
        for p in self.players:
            if p.session_id == session_id:
                return p
        return None

    def get_player_by_color(self, color: str) -> Optional[RoomPlayer]:
        for p in self.players:
            if p.color == color:
                return p
        return None

    def add_human_player(self, session_id: str, name: str, ws: web.WebSocketResponse, avatar: str = "lion", preferred_color: Optional[str] = None) -> RoomPlayer:
        self.sockets[session_id] = ws

        # Check if reconnecting
        board_capacity = 4 if self.max_players <= 4 else self.max_players
        palette = ALL_PLAYER_COLORS[:board_capacity]

        existing = self.get_player_by_session(session_id)
        if existing:
            existing.is_connected = True
            if preferred_color and preferred_color in palette:
                if not any(p.color == preferred_color and p.session_id != session_id for p in self.players):
                    existing.color = preferred_color
            return existing

        assigned_colors = {p.color for p in self.players}
        if preferred_color and preferred_color in palette and preferred_color not in assigned_colors:
            color = preferred_color
        else:
            available_colors = [c for c in palette if c not in assigned_colors]
            color = available_colors[0] if available_colors else "spectator"

        player = RoomPlayer(session_id, name, color, is_bot=False, avatar=avatar)
        if session_id == self.host_session_id or len(self.players) == 0:
            player.is_host = True
            player.is_ready = True
            self.host_session_id = session_id

        self.players.append(player)
        return player

    def change_player_color(self, session_id: str, new_color: str) -> bool:
        """Allows a player to change their selected color in the lobby."""
        player = self.get_player_by_session(session_id)
        if not player or self.status != "LOBBY":
            return False
        board_capacity = 4 if self.max_players <= 4 else self.max_players
        if new_color not in ALL_PLAYER_COLORS[:board_capacity]:
            return False

        # If another human player already has this color, reject
        for other in self.players:
            if other.session_id != session_id and other.color == new_color:
                if not other.is_bot:
                    return False
                else:
                    # Swap color with bot
                    other.color = player.color
                    player.color = new_color
                    return True

        player.color = new_color
        return True

    def player_quit(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Allows a player to quit the match at any time."""
        player = self.get_player_by_session(session_id)
        if not player:
            return None

        keys_to_del = [sid for sid in self.sockets if sid == session_id or sid.startswith(f"{session_id}_")]
        for k in keys_to_del:
            del self.sockets[k]


        if self.status == "PLAYING" and self.game:
            # Replaced by an automated bot so other players can continue smoothly
            player.is_bot = True
            player.name = f"{player.name} (AI)"
            player.is_connected = False
            res = {
                "action": "replaced_by_bot",
                "player": player.color,
                "name": player.name
            }
            active_humans = [p for p in self.players if not p.is_bot and p.is_connected]
            if not active_humans:
                if self.bot_task and not self.bot_task.done():
                    self.bot_task.cancel()
                self.status = "FINISHED"
                res["match_ended"] = True
            else:
                self.trigger_bot_turn_if_needed()
            return res
        else:
            self.players = [p for p in self.players if p.session_id != session_id]
            if player.is_host and self.players:
                humans = [p for p in self.players if not p.is_bot]
                if humans:
                    humans[0].is_host = True
                    self.host_session_id = humans[0].session_id
            return {
                "action": "left_lobby",
                "player": player.color,
                "name": player.name
            }

    def fill_remaining_with_bots(self) -> None:
        """Fills open slots up to max_players with AI bots."""
        assigned_colors = {p.color for p in self.players}
        bot_names = {
            "red": "Scarlet (Bot)",
            "green": "Emerald (Bot)",
            "yellow": "Blaze (Bot)",
            "blue": "Cobalt (Bot)",
            "orange": "Amber (Bot)",
            "purple": "Shadow (Bot)",
            "cyan": "Zephyr (Bot)",
            "pink": "Lotus (Bot)"
        }
        bot_avatars = {
            "red": "dragon",
            "green": "alien",
            "yellow": "fox",
            "blue": "bear",
            "orange": "tiger",
            "purple": "wolf",
            "cyan": "eagle",
            "pink": "phoenix"
        }

        for color in ALL_PLAYER_COLORS[:self.max_players]:
            if color not in assigned_colors:
                bot_player = RoomPlayer(
                    session_id=None,
                    name=bot_names.get(color, f"Bot {color.capitalize()}"),
                    color=color,
                    is_bot=True,
                    avatar=bot_avatars.get(color, "robot")
                )
                bot_player.is_ready = True
                self.players.append(bot_player)

    def start_game(self) -> None:
        """Initializes and starts the Ludo game."""
        color_order = {c: i for i, c in enumerate(ALL_PLAYER_COLORS)}
        active_players = [p for p in self.players if p.color in color_order]
        active_players.sort(key=lambda p: color_order[p.color])

        configs = [
            {
                "color": p.color,
                "name": p.name,
                "is_bot": p.is_bot,
                "avatar": p.avatar
            }
            for p in active_players
        ]

        self.game = LudoGame(
            configs,
            open_on_one=self.open_on_one,
            team_mode=self.team_mode,
            two_dice_mode=self.two_dice_mode
        )
        self.status = "PLAYING"

    async def broadcast(self, message: Dict[str, Any], exclude_session_id: Optional[str] = None) -> None:
        """Broadcasts message to all connected unique sockets in this room."""
        sent_sockets = set()
        for sid, ws in list(self.sockets.items()):
            if exclude_session_id and sid == exclude_session_id:
                continue
            if ws in sent_sockets:
                continue
            if not ws.closed:
                try:
                    sent_sockets.add(ws)
                    await ws.send_json(message)
                except Exception as e:
                    logger.warning(f"Error broadcasting to {sid}: {e}")

    async def broadcast_state(self) -> None:
        """Broadcasts the entire room and game state."""
        state = {
            "type": "game_state",
            "room_id": self.room_id,
            "status": self.status,
            "mode": self.mode,
            "max_players": self.max_players,
            "open_on_one": self.open_on_one,
            "team_mode": self.team_mode,
            "two_dice_mode": self.two_dice_mode,
            "difficulty": self.difficulty,
            "players": [p.to_dict() for p in self.players],
            "game": self.game.get_state() if self.game else None
        }
        await self.broadcast(state)

    def trigger_bot_turn_if_needed(self) -> None:
        """Schedules bot turn if current player is a bot."""
        if not self.game or self.status != "PLAYING" or self.game.turn_state == "GAME_OVER":
            return

        curr_color = self.game.current_player.color
        curr_player = self.get_player_by_color(curr_color)

        if curr_player and curr_player.is_bot:
            if self.bot_task and not self.bot_task.done():
                self.bot_task.cancel()
            self.bot_task = asyncio.create_task(self._run_bot_turn())

    async def _run_bot_turn(self) -> None:
        """Executes a bot's turn with realistic delays for dice roll and piece moving."""
        try:
            await asyncio.sleep(0.9)  # Thinking delay
            if not self.game or self.status != "PLAYING":
                return

            # Bot rolls dice
            if self.game.turn_state == "WAIT_ROLL":
                roll_result = self.game.roll_dice()
                await self.broadcast({
                    "type": "dice_rolled",
                    "player": roll_result["player"],
                    "dice": roll_result["dice"],
                    "dice_values": roll_result.get("dice_values"),
                    "remaining_dice": roll_result.get("remaining_dice"),
                    "used_dice": roll_result.get("used_dice"),
                    "selected_die": roll_result.get("selected_die"),
                    "valid_moves": roll_result["valid_moves"],
                    "valid_moves_by_die": roll_result.get("valid_moves_by_die"),
                    "auto_passed": roll_result.get("auto_passed", False),
                    "consecutive_sixes_violation": roll_result.get("consecutive_sixes_violation", False)
                })
                await self.broadcast_state()

                if roll_result.get("auto_passed") or roll_result.get("consecutive_sixes_violation"):
                    # Turn passed
                    await asyncio.sleep(0.6)
                    self.trigger_bot_turn_if_needed()
                    return

            # Execute bot moves while turn_state is WAIT_MOVE and current player is a bot
            while self.game and self.status == "PLAYING" and self.game.turn_state == "WAIT_MOVE":
                curr_color = self.game.current_player.color
                curr_player = self.get_player_by_color(curr_color)
                if not curr_player or not curr_player.is_bot:
                    break

                # Delay between moves for realistic animation
                await asyncio.sleep(0.75)

                if self.game.two_dice_mode and self.game.remaining_dice:
                    moves_dict = {}
                    for d in self.game.remaining_dice:
                        v = self.game.get_valid_moves(d)
                        if v:
                            moves_dict[str(d)] = v
                    if len(self.game.remaining_dice) == 2:
                        d_sum = sum(self.game.remaining_dice)
                        v_sum = self.game.get_valid_moves(d_sum)
                        if v_sum:
                            moves_dict[str(d_sum)] = v_sum

                    if not moves_dict:
                        self.game.pass_remaining()
                        await self.broadcast_state()
                        break

                    chosen_die, token_id = BotAI.choose_move_two_dice(self.game, moves_dict, difficulty=self.difficulty)
                    sel_res = self.game.select_die(chosen_die)
                    chosen_idx = None
                    if self.game.dice_values:
                        used_indices = []
                        if len(self.game.used_dice) == 1 and len(self.game.dice_values) == 2:
                            first_used = self.game.used_dice[0]
                            if self.game.dice_values[0] == first_used:
                                used_indices.append(0)
                            elif self.game.dice_values[1] == first_used:
                                used_indices.append(1)
                        for idx, v in enumerate(self.game.dice_values):
                            if idx not in used_indices and v == chosen_die:
                                chosen_idx = idx
                                break

                    await self.broadcast({
                        "type": "die_selected",
                        "player": self.game.current_player.color,
                        "selected_die": chosen_die,
                        "die_index": chosen_idx,
                        "remaining_dice": sel_res.get("remaining_dice"),
                        "used_dice": sel_res.get("used_dice"),
                        "valid_moves": sel_res["valid_moves"]
                    })
                    await self.broadcast_state()
                    await asyncio.sleep(0.35)
                    move_result = self.game.move_token(token_id, selected_die=chosen_die)
                else:
                    valid_moves = self.game.get_valid_moves()
                    if not valid_moves:
                        break
                    token_id = BotAI.choose_move(self.game, valid_moves, difficulty=self.difficulty)
                    move_result = self.game.move_token(token_id)

                await self.broadcast({
                    "type": "token_moved",
                    **move_result
                })
                await self.broadcast_state()

                if move_result.get("game_over"):
                    self.status = "FINISHED"
                    await self.broadcast({
                        "type": "game_over",
                        "winners": move_result["winners"]
                    })
                    return

                if move_result.get("turn_complete", True):
                    break

            # If bot got extra turn or next player is also a bot
            await asyncio.sleep(0.5)
            self.trigger_bot_turn_if_needed()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in bot turn execution: {e}", exc_info=True)


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}

    def generate_room_code(self) -> str:
        """Generates random 4-letter room code."""
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
            room_id = f"LUDO-{code}"
            if room_id not in self.rooms:
                return room_id

    def create_room(self, host_session_id: str, mode: str = "online", player_count: int = 4, custom_id: Optional[str] = None, open_on_one: bool = True, team_mode: bool = False, two_dice_mode: bool = False, difficulty: str = "hard") -> GameRoom:
        room_id = custom_id if custom_id else self.generate_room_code()
        room = GameRoom(room_id, host_session_id, mode=mode, player_count=player_count, open_on_one=open_on_one, team_mode=team_mode, two_dice_mode=two_dice_mode, difficulty=difficulty)
        self.rooms[room_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[GameRoom]:
        rid = room_id.upper().strip()
        if rid in self.rooms:
            return self.rooms[rid]
        if f"LUDO-{rid}" in self.rooms:
            return self.rooms[f"LUDO-{rid}"]
        if rid.startswith("LUDO-"):
            raw = rid[5:]
            if raw in self.rooms:
                return self.rooms[raw]
        return None

    def remove_socket(self, session_id: str) -> None:
        for room in list(self.rooms.values()):
            if session_id in room.sockets:
                del room.sockets[session_id]
                player = room.get_player_by_session(session_id)
                if player:
                    player.is_connected = False
                    if room.status == "PLAYING" and room.game:
                        room.player_quit(session_id)
                # If room is completely empty, clean it up after a while
                if not any(not ws.closed for ws in room.sockets.values()):
                    if room.bot_task and not room.bot_task.done():
                        room.bot_task.cancel()
