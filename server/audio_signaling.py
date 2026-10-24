"""
Real-Time Local Audio Calling Signaling & Relay Engine
Handles:
1. WebRTC Signaling (SDP Offer/Answer, ICE Candidates) for peer-to-peer audio over LAN/loopback.
2. Direct WebSocket Binary Audio Relay for instant fallback audio calling without STUN/TURN.
3. Voice room presence, mute/deafen synchronization, and live speaking status.
"""

import logging
from typing import Dict, Set, Any, Optional
import aiohttp
from aiohttp import web

logger = logging.getLogger("audio_signaling")


class AudioPeer:
    def __init__(self, session_id: str, player_name: str, color: str, ws: web.WebSocketResponse):
        self.session_id = session_id
        self.player_name = player_name
        self.color = color
        self.ws = ws
        self.is_muted = False
        self.is_deafened = False
        self.is_speaking = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "player_name": self.player_name,
            "color": self.color,
            "is_muted": self.is_muted,
            "is_deafened": self.is_deafened,
            "is_speaking": self.is_speaking
        }


class AudioRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.peers: Dict[str, AudioPeer] = {}
        self.private_calls: Dict[str, str] = {}  # session_id -> peer_session_id

    def add_peer(self, peer: AudioPeer) -> None:
        self.peers[peer.session_id] = peer

    def get_private_partner(self, session_id: str) -> Optional[str]:
        return self.private_calls.get(session_id)

    def remove_peer(self, session_id: str) -> Optional[AudioPeer]:
        partner_sid = self.private_calls.pop(session_id, None)
        if partner_sid:
            self.private_calls.pop(partner_sid, None)
        return self.peers.pop(session_id, None)

    def get_peer(self, session_id: str) -> Optional[AudioPeer]:
        return self.peers.get(session_id)

    async def broadcast(self, message: Dict[str, Any], exclude_session_id: Optional[str] = None) -> None:
        """Broadcasts JSON message to all peers in the voice room."""
        for sid, peer in list(self.peers.items()):
            if exclude_session_id and sid == exclude_session_id:
                continue
            if not peer.ws.closed:
                try:
                    await peer.ws.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to peer {sid}: {e}")

    async def relay_audio_bytes(self, sender_id: str, data: bytes) -> None:
        """
        Relays binary PCM/Opus audio packet from sender:
        - If sender is in an individual 1-on-1 call, ONLY relay to that specific peer.
        - If sender is in conference mode, relay to all other conference peers.
        """
        sender = self.peers.get(sender_id)
        if not sender or sender.is_muted:
            return

        # Individual 1-on-1 private call routing
        if sender_id in self.private_calls:
            target_sid = self.private_calls[sender_id]
            target_peer = self.peers.get(target_sid)
            if target_peer and not target_peer.is_deafened and not target_peer.ws.closed:
                try:
                    await target_peer.ws.send_bytes(data)
                except Exception as e:
                    logger.warning(f"Failed to relay private audio bytes to {target_sid}: {e}")
            return

        # General Conference call routing
        for sid, peer in list(self.peers.items()):
            if sid == sender_id:
                continue
            if sid in self.private_calls:
                continue  # Peer is busy on a private individual call
            if peer.is_deafened:
                continue
            if not peer.ws.closed:
                try:
                    await peer.ws.send_bytes(data)
                except Exception as e:
                    logger.warning(f"Failed to relay conference audio bytes to {sid}: {e}")

    def get_roster(self) -> list:
        res = []
        for p in self.peers.values():
            d = p.to_dict()
            d["in_private_call"] = p.session_id in self.private_calls
            d["private_partner"] = self.private_calls.get(p.session_id)
            res.append(d)
        return res


class AudioSignalingManager:
    def __init__(self):
        self.rooms: Dict[str, AudioRoom] = {}

    def get_or_create_room(self, room_id: str) -> AudioRoom:
        if room_id not in self.rooms:
            self.rooms[room_id] = AudioRoom(room_id)
        return self.rooms[room_id]

    async def handle_audio_message(self, ws: web.WebSocketResponse, session_id: str, data: Dict[str, Any]) -> None:
        """
        Handles incoming audio control and signaling messages:
        - audio_join
        - audio_leave
        - audio_offer
        - audio_answer
        - audio_candidate
        - audio_mute
        - audio_speaking
        """
        msg_type = data.get("type")
        room_id = data.get("room_id")
        if not room_id:
            return

        room = self.get_or_create_room(room_id)

        if msg_type == "audio_join":
            player_name = data.get("player_name", "Player")
            color = data.get("color", "unknown")
            peer = AudioPeer(session_id, player_name, color, ws)
            room.add_peer(peer)

            # Notify existing peers that a new peer joined
            await room.broadcast({
                "type": "audio_peer_joined",
                "room_id": room_id,
                "peer": peer.to_dict()
            }, exclude_session_id=session_id)

            # Send full roster to the joining peer
            await ws.send_json({
                "type": "audio_roster",
                "room_id": room_id,
                "peers": room.get_roster()
            })

        elif msg_type == "audio_leave":
            partner_sid = room.get_private_partner(session_id)
            if partner_sid and partner_sid in room.peers:
                partner_peer = room.peers[partner_sid]
                if not partner_peer.ws.closed:
                    await partner_peer.ws.send_json({
                        "type": "audio_call_ended",
                        "room_id": room_id
                    })
            removed = room.remove_peer(session_id)
            if removed:
                await room.broadcast({
                    "type": "audio_peer_left",
                    "room_id": room_id,
                    "session_id": session_id,
                    "color": removed.color
                })
                await room.broadcast({
                    "type": "audio_roster",
                    "room_id": room_id,
                    "peers": room.get_roster()
                })

        elif msg_type in ("audio_offer", "audio_answer", "audio_candidate"):
            target_sid = data.get("target_session_id")
            if target_sid and target_sid in room.peers:
                target_peer = room.peers[target_sid]
                data["sender_session_id"] = session_id
                sender_peer = room.peers.get(session_id)
                if sender_peer:
                    data["sender_color"] = sender_peer.color
                if not target_peer.ws.closed:
                    await target_peer.ws.send_json(data)

        elif msg_type == "audio_mute":
            peer = room.get_peer(session_id)
            if peer:
                peer.is_muted = data.get("is_muted", peer.is_muted)
                peer.is_deafened = data.get("is_deafened", peer.is_deafened)
                await room.broadcast({
                    "type": "audio_peer_state",
                    "room_id": room_id,
                    "session_id": session_id,
                    "color": peer.color,
                    "is_muted": peer.is_muted,
                    "is_deafened": peer.is_deafened
                })

        elif msg_type == "audio_speaking":
            peer = room.get_peer(session_id)
            if peer:
                peer.is_speaking = bool(data.get("is_speaking", False))
                await room.broadcast({
                    "type": "audio_peer_speaking",
                    "room_id": room_id,
                    "session_id": session_id,
                    "color": peer.color,
                    "is_speaking": peer.is_speaking
                }, exclude_session_id=session_id)

        # --- Individual 1-on-1 Private Call Signaling ---
        elif msg_type == "audio_call_request":
            target_sid = data.get("target_session_id")
            sender_peer = room.get_peer(session_id)
            target_peer = room.get_peer(target_sid) if target_sid else None
            if sender_peer and target_peer and not target_peer.ws.closed:
                await target_peer.ws.send_json({
                    "type": "audio_call_incoming",
                    "room_id": room_id,
                    "caller_session_id": session_id,
                    "caller_name": sender_peer.player_name,
                    "caller_color": sender_peer.color
                })

        elif msg_type == "audio_call_accept":
            caller_sid = data.get("caller_session_id")
            sender_peer = room.get_peer(session_id)
            caller_peer = room.get_peer(caller_sid) if caller_sid else None
            if sender_peer and caller_peer:
                room.private_calls[session_id] = caller_sid
                room.private_calls[caller_sid] = session_id
                # Notify both peers
                await sender_peer.ws.send_json({
                    "type": "audio_call_connected",
                    "room_id": room_id,
                    "peer_session_id": caller_sid,
                    "peer_name": caller_peer.player_name,
                    "peer_color": caller_peer.color
                })
                await caller_peer.ws.send_json({
                    "type": "audio_call_connected",
                    "room_id": room_id,
                    "peer_session_id": session_id,
                    "peer_name": sender_peer.player_name,
                    "peer_color": sender_peer.color
                })
                # Broadcast updated roster to room
                await room.broadcast({
                    "type": "audio_roster",
                    "room_id": room_id,
                    "peers": room.get_roster()
                })

        elif msg_type == "audio_call_decline":
            caller_sid = data.get("caller_session_id")
            caller_peer = room.get_peer(caller_sid) if caller_sid else None
            if caller_peer and not caller_peer.ws.closed:
                await caller_peer.ws.send_json({
                    "type": "audio_call_declined",
                    "room_id": room_id,
                    "target_session_id": session_id
                })

        elif msg_type == "audio_call_end":
            partner_sid = room.private_calls.pop(session_id, None)
            sender_peer = room.get_peer(session_id)
            if sender_peer and not sender_peer.ws.closed:
                await sender_peer.ws.send_json({
                    "type": "audio_call_ended",
                    "room_id": room_id
                })
            if partner_sid:
                room.private_calls.pop(partner_sid, None)
                partner_peer = room.get_peer(partner_sid)
                if partner_peer and not partner_peer.ws.closed:
                    await partner_peer.ws.send_json({
                        "type": "audio_call_ended",
                        "room_id": room_id
                    })
            await room.broadcast({
                "type": "audio_roster",
                "room_id": room_id,
                "peers": room.get_roster()
            })

    async def handle_disconnect(self, session_id: str) -> None:
        """Cleans up peer from all rooms upon disconnect."""
        for room_id, room in list(self.rooms.items()):
            partner_sid = room.get_private_partner(session_id)
            if partner_sid and partner_sid in room.peers:
                partner_peer = room.peers[partner_sid]
                if not partner_peer.ws.closed:
                    try:
                        await partner_peer.ws.send_json({
                            "type": "audio_call_ended",
                            "room_id": room_id
                        })
                    except Exception:
                        pass
            removed = room.remove_peer(session_id)
            if removed:
                await room.broadcast({
                    "type": "audio_peer_left",
                    "room_id": room_id,
                    "session_id": session_id,
                    "color": removed.color
                })
                await room.broadcast({
                    "type": "audio_roster",
                    "room_id": room_id,
                    "peers": room.get_roster()
                })
