"""
Aiohttp Application Server
Provides HTTP static file serving, REST endpoints, and WebSocket handler
for both Game events and Real-Time Local Audio Calling.
"""

import asyncio
import json
import logging
import os
import socket
import uuid
from pathlib import Path
from aiohttp import web, WSMsgType

from .room_manager import RoomManager
from .audio_signaling import AudioSignalingManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")


def get_local_ip() -> str:
    """Finds the primary local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send packets, just determines routing interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


ROOM_MGR_KEY = web.AppKey("room_mgr", RoomManager)
AUDIO_MGR_KEY = web.AppKey("audio_mgr", AudioSignalingManager)
STATIC_DIR_KEY = web.AppKey("static_dir", Path)
LOCAL_IP_KEY = web.AppKey("local_ip", str)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """CORS middleware allowing cross-origin requests from Capacitor mobile WebViews."""
    if request.method == "OPTIONS":
        response = web.Response(status=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        return response

    try:
        response = await handler(request)
    except web.HTTPException as ex:
        response = ex

    if not isinstance(response, web.StreamResponse) or not response.prepared:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"

    return response


def create_app(static_dir: Path) -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    room_mgr = RoomManager()
    audio_mgr = AudioSignalingManager()

    app[ROOM_MGR_KEY] = room_mgr
    app[AUDIO_MGR_KEY] = audio_mgr
    app[STATIC_DIR_KEY] = static_dir
    app[LOCAL_IP_KEY] = get_local_ip()

    async def health_check(request: web.Request) -> web.Response:
        return web.json_response({
            "status": "healthy",
            "service": "royal-ludo"
        })

    async def index_handler(request: web.Request) -> web.Response:
        index_path = static_dir / "index.html"
        if not index_path.exists():
            return web.Response(text="Index file not found", status=404)
        return web.FileResponse(index_path)

    async def api_status(request: web.Request) -> web.Response:
        return web.json_response({
            "status": "online",
            "local_ip": app[LOCAL_IP_KEY],
            "active_rooms": len(room_mgr.rooms)
        })

    async def api_create_room(request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}

        mode = data.get("mode", "online")
        player_count = int(data.get("player_count", 4))
        custom_id = data.get("room_id")
        open_on_one = bool(data.get("open_on_one", True))
        team_mode = bool(data.get("team_mode", False))
        two_dice_mode = bool(data.get("two_dice_mode", False))
        difficulty = str(data.get("difficulty", "hard"))
        temp_host_sid = str(uuid.uuid4())

        room = room_mgr.create_room(
            host_session_id=temp_host_sid,
            mode=mode,
            player_count=player_count,
            custom_id=custom_id,
            open_on_one=open_on_one,
            team_mode=team_mode,
            two_dice_mode=two_dice_mode,
            difficulty=difficulty
        )
        return web.json_response({
            "room_id": room.room_id,
            "mode": room.mode,
            "max_players": room.max_players,
            "open_on_one": room.open_on_one,
            "team_mode": room.team_mode,
            "two_dice_mode": room.two_dice_mode,
            "difficulty": room.difficulty
        })

    async def api_room_info(request: web.Request) -> web.Response:
        room_id = request.query.get("room_id", "").strip().upper()
        room = room_mgr.get_room(room_id)
        if not room:
            return web.json_response({"error": "Room not found"}, status=404)
        return web.json_response({
            "room_id": room.room_id,
            "status": room.status,
            "mode": room.mode,
            "player_count": len(room.players),
            "max_players": room.max_players,
            "open_on_one": room.open_on_one,
            "team_mode": room.team_mode,
            "two_dice_mode": room.two_dice_mode,
            "difficulty": room.difficulty
        })

    async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=25.0)
        await ws.prepare(request)

        session_id = str(uuid.uuid4())
        current_room_id: Optional[str] = None

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue

                    msg_type = data.get("type")

                    # Audio signaling messages
                    if msg_type and msg_type.startswith("audio_"):
                        await audio_mgr.handle_audio_message(ws, session_id, data)
                        continue

                    # Game messages
                    if msg_type == "join_room":
                        room_id = data.get("room_id", "").upper().strip()
                        name = data.get("name", "Player").strip() or "Player"
                        avatar = data.get("avatar", "lion")
                        mode = data.get("mode", "online")
                        player_count = int(data.get("player_count", 4))
                        open_on_one = bool(data.get("open_on_one", True))
                        team_mode = bool(data.get("team_mode", False))
                        two_dice_mode = bool(data.get("two_dice_mode", False))
                        difficulty = str(data.get("difficulty", "hard"))
                        preferred_color = data.get("color") or data.get("preferred_color")

                        room = room_mgr.get_room(room_id)
                        if not room:
                            room = room_mgr.create_room(
                                host_session_id=session_id,
                                mode=mode,
                                player_count=player_count,
                                custom_id=room_id,
                                open_on_one=open_on_one,
                                team_mode=team_mode,
                                two_dice_mode=two_dice_mode,
                                difficulty=difficulty
                            )
                        else:
                            is_host_or_local = (session_id == room.host_session_id or len(room.players) == 0 or room.mode in ("single", "local"))
                            if "open_on_one" in data and is_host_or_local:
                                room.open_on_one = open_on_one
                            if "team_mode" in data and is_host_or_local:
                                room.team_mode = team_mode and room.max_players == 4
                            if "two_dice_mode" in data and is_host_or_local:
                                room.two_dice_mode = two_dice_mode
                            if "difficulty" in data and is_host_or_local:
                                room.difficulty = difficulty

                        current_room_id = room.room_id
                        player = room.add_human_player(session_id, name, ws, avatar=avatar, preferred_color=preferred_color)

                        # If single player mode vs bots or pass-and-play, auto fill slots
                        if room.mode in ("single", "local") and len(room.players) == 1:
                            if room.mode == "single":
                                room.fill_remaining_with_bots()
                            elif room.mode == "local":
                                # Add local pass-and-play human seats up to max_players
                                names = [f"Player {i+1}" for i in range(8)]
                                avatars = ["lion", "fox", "bear", "dragon", "tiger", "wolf", "eagle", "phoenix"]
                                for i in range(1, room.max_players):
                                    p = room.add_human_player(f"{session_id}_seat_{i}", names[i], ws, avatar=avatars[i])
                                    p.is_ready = True

                        # Respond with joined acknowledgement
                        await ws.send_json({
                            "type": "room_joined",
                            "session_id": session_id,
                            "room_id": room.room_id,
                            "player": player.to_dict(),
                            "is_host": player.is_host
                        })
                        await room.broadcast_state()

                    elif msg_type == "start_game":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if not room:
                            continue

                        # Check if session is host or single player
                        p = room.get_player_by_session(session_id)
                        if p and (p.is_host or room.mode in ("single", "local")):
                            # Auto-fill any unfilled slots with bots
                            room.fill_remaining_with_bots()
                            room.start_game()
                            await room.broadcast({
                                "type": "game_started",
                                "room_id": room.room_id
                            })
                            await room.broadcast_state()
                            room.trigger_bot_turn_if_needed()

                    elif msg_type == "roll_dice":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if not room or not room.game or room.game.turn_state != "WAIT_ROLL":
                            continue

                        curr_color = room.game.current_player.color
                        player = room.get_player_by_color(curr_color)

                        # Verify caller has permission to roll for this color
                        can_roll = False
                        if room.mode == "local":
                            can_roll = True
                        elif player and player.session_id == session_id:
                            can_roll = True

                        if can_roll:
                            res = room.game.roll_dice()
                            await room.broadcast({
                                "type": "dice_rolled",
                                "player": res["player"],
                                "dice": res["dice"],
                                "dice_values": res.get("dice_values"),
                                "selected_die": res.get("selected_die"),
                                "valid_moves": res["valid_moves"],
                                "valid_moves_by_die": res.get("valid_moves_by_die"),
                                "auto_passed": res.get("auto_passed", False),
                                "consecutive_sixes_violation": res.get("consecutive_sixes_violation", False)
                            })
                            await room.broadcast_state()

                            if res.get("auto_passed") or res.get("consecutive_sixes_violation"):
                                # If next turn is bot, schedule bot turn
                                await asyncio.sleep(0.5)
                                room.trigger_bot_turn_if_needed()

                    elif msg_type == "select_die":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if not room or not room.game or room.game.turn_state != "WAIT_MOVE":
                            continue

                        curr_color = room.game.current_player.color
                        player = room.get_player_by_color(curr_color)

                        can_select = False
                        if room.mode == "local":
                            can_select = True
                        elif player and player.session_id == session_id:
                            can_select = True

                        if can_select:
                            try:
                                die_val = int(data.get("die_value", 0))
                                die_idx = data.get("die_index")
                                sel_res = room.game.select_die(die_val)
                                await room.broadcast({
                                    "type": "die_selected",
                                    "player": curr_color,
                                    "selected_die": sel_res["selected_die"],
                                    "die_index": die_idx,
                                    "remaining_dice": sel_res.get("remaining_dice"),
                                    "used_dice": sel_res.get("used_dice"),
                                    "valid_moves": sel_res["valid_moves"]
                                })
                                await room.broadcast_state()
                            except ValueError as e:
                                await ws.send_json({"type": "error", "message": str(e)})

                    elif msg_type == "move_token":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if not room or not room.game or room.game.turn_state != "WAIT_MOVE":
                            continue

                        token_id = int(data.get("token_id", -1))
                        selected_die = int(data["selected_die"]) if ("selected_die" in data and data["selected_die"] is not None) else None
                        curr_color = room.game.current_player.color
                        player = room.get_player_by_color(curr_color)

                        can_move = False
                        if room.mode == "local":
                            can_move = True
                        elif player and player.session_id == session_id:
                            can_move = True

                        if can_move:
                            try:
                                move_res = room.game.move_token(token_id, selected_die=selected_die)
                                await room.broadcast({
                                    "type": "token_moved",
                                    **move_res
                                })
                                await room.broadcast_state()

                                if move_res.get("game_over"):
                                    room.status = "FINISHED"
                                    await room.broadcast({
                                        "type": "game_over",
                                        "winners": move_res["winners"]
                                    })
                                else:
                                    await asyncio.sleep(0.4)
                                    room.trigger_bot_turn_if_needed()

                            except ValueError as e:
                                await ws.send_json({"type": "error", "message": str(e)})

                    elif msg_type == "pass_turn":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if not room or not room.game or room.game.turn_state != "WAIT_MOVE":
                            continue

                        curr_color = room.game.current_player.color
                        player = room.get_player_by_color(curr_color)

                        can_pass = False
                        if room.mode == "local":
                            can_pass = True
                        elif player and player.session_id == session_id:
                            can_pass = True

                        if can_pass:
                            try:
                                pass_res = room.game.pass_remaining()
                                await room.broadcast({
                                    "type": "turn_passed",
                                    **pass_res
                                })
                                await room.broadcast_state()
                                await asyncio.sleep(0.4)
                                room.trigger_bot_turn_if_needed()
                            except ValueError as e:
                                await ws.send_json({"type": "error", "message": str(e)})

                    elif msg_type == "chat_message":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if room:
                            text = data.get("text", "").strip()[:200]
                            sender = room.get_player_by_session(session_id)
                            sender_name = sender.name if sender else "Player"
                            sender_color = sender.color if sender else "gray"
                            if text:
                                await room.broadcast({
                                    "type": "chat_message",
                                    "sender": sender_name,
                                    "color": sender_color,
                                    "text": text
                                })

                    elif msg_type == "reaction":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if room:
                            emoji = data.get("emoji", "🎲")
                            sender = room.get_player_by_session(session_id)
                            await room.broadcast({
                                "type": "reaction",
                                "emoji": emoji,
                                "sender": sender.name if sender else "Player",
                                "color": sender.color if sender else "red"
                            })

                    elif msg_type == "rematch":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if room and room.status == "FINISHED":
                            room.start_game()
                            await room.broadcast({
                                "type": "rematch_started",
                                "room_id": room.room_id
                            })
                            await room.broadcast_state()
                            room.trigger_bot_turn_if_needed()

                    elif msg_type == "update_rules":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if room:
                            p = room.get_player_by_session(session_id)
                            if p and (p.is_host or room.mode in ("single", "local")):
                                if "open_on_one" in data:
                                    room.open_on_one = bool(data["open_on_one"])
                                    if room.game:
                                        room.game.open_on_one = room.open_on_one
                                if "team_mode" in data:
                                    room.team_mode = bool(data["team_mode"]) and room.max_players == 4
                                    if room.game:
                                        room.game.team_mode = room.team_mode
                                if "two_dice_mode" in data:
                                    room.two_dice_mode = bool(data["two_dice_mode"])
                                    if room.game:
                                        room.game.two_dice_mode = room.two_dice_mode
                                if "difficulty" in data:
                                    room.difficulty = str(data["difficulty"])
                                # Safety: prevent deadlock if rule changed during WAIT_MOVE
                                if room.game and room.game.turn_state == "WAIT_MOVE":
                                    valid_moves = room.game.get_valid_moves(room.game.dice_value)
                                    if not valid_moves:
                                        room.game.turn_state = "WAIT_ROLL"
                                        room.game.dice_value = None
                                        room.game.consecutive_sixes = 0
                                        room.game._advance_turn()
                                        room.trigger_bot_turn_if_needed()
                                await room.broadcast_state()

                    elif msg_type == "change_color":
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if room:
                            target_col = data.get("color")
                            if target_col and room.change_player_color(session_id, target_col):
                                await room.broadcast_state()

                    elif msg_type in ("quit_game", "leave_game"):
                        if not current_room_id:
                            continue
                        room = room_mgr.get_room(current_room_id)
                        if room:
                            res = room.player_quit(session_id)
                            if res:
                                await room.broadcast({
                                    "type": "player_left",
                                    **res
                                })
                                await room.broadcast_state()
                            current_room_id = None
                            await audio_mgr.handle_disconnect(session_id)
                            try:
                                await ws.send_json({"type": "left_game_ack"})
                            except Exception:
                                pass

                elif msg.type == WSMsgType.BINARY:
                    # WebSocket Audio Relay: binary audio packet broadcast
                    if current_room_id:
                        room_audio = audio_mgr.get_or_create_room(current_room_id)
                        await room_audio.relay_audio_bytes(session_id, msg.data)

                elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break

        finally:
            if current_room_id:
                room = room_mgr.get_room(current_room_id)
                if room:
                    room_mgr.remove_socket(session_id)
                    await room.broadcast_state()

            await audio_mgr.handle_disconnect(session_id)

        return ws

    # Routing
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_check)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/create_room", api_create_room)
    app.router.add_get("/api/room_info", api_room_info)
    app.router.add_get("/ws", websocket_handler)

    # Static assets
    if static_dir.exists():
        app.router.add_static("/static/", path=str(static_dir), name="static")

    return app
