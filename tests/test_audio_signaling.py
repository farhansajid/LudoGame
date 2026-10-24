"""
Unit Tests for Audio Signaling & Relay
Validates:
- Audio room creation and peer management
- Join and leave broadcasts
- WebRTC offer/answer/candidate forwarding
- Mute / deafen presence synchronization
- WebSocket binary audio relay to non-deafened peers
"""

import unittest
from unittest.mock import AsyncMock, MagicMock
from server.audio_signaling import AudioSignalingManager, AudioPeer, AudioRoom


class TestAudioSignaling(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mgr = AudioSignalingManager()
        self.room = self.mgr.get_or_create_room("TEST-ROOM")

        self.ws1 = MagicMock()
        self.ws1.closed = False
        self.ws1.send_json = AsyncMock()
        self.ws1.send_bytes = AsyncMock()

        self.ws2 = MagicMock()
        self.ws2.closed = False
        self.ws2.send_json = AsyncMock()
        self.ws2.send_bytes = AsyncMock()

        self.peer1 = AudioPeer("sess-1", "Alice", "red", self.ws1)
        self.peer2 = AudioPeer("sess-2", "Bob", "blue", self.ws2)

    async def test_add_remove_peer(self):
        self.room.add_peer(self.peer1)
        self.room.add_peer(self.peer2)
        self.assertEqual(len(self.room.peers), 2)

        roster = self.room.get_roster()
        self.assertEqual(len(roster), 2)
        self.assertEqual(roster[0]["player_name"], "Alice")

        removed = self.room.remove_peer("sess-1")
        self.assertEqual(removed.session_id, "sess-1")
        self.assertEqual(len(self.room.peers), 1)

    async def test_audio_join_message(self):
        await self.mgr.handle_audio_message(self.ws1, "sess-1", {
            "type": "audio_join",
            "room_id": "TEST-ROOM",
            "player_name": "Alice",
            "color": "red"
        })
        # ws1 should receive audio_roster
        self.ws1.send_json.assert_called_once()
        sent_msg = self.ws1.send_json.call_args[0][0]
        self.assertEqual(sent_msg["type"], "audio_roster")

    async def test_webrtc_signaling_forward(self):
        self.room.add_peer(self.peer1)
        self.room.add_peer(self.peer2)

        offer_data = {
            "type": "audio_offer",
            "room_id": "TEST-ROOM",
            "target_session_id": "sess-2",
            "sdp": "mock-sdp-offer"
        }
        await self.mgr.handle_audio_message(self.ws1, "sess-1", offer_data)

        # Peer 2 should have received the offer with sender info
        self.ws2.send_json.assert_called_once()
        received = self.ws2.send_json.call_args[0][0]
        self.assertEqual(received["type"], "audio_offer")
        self.assertEqual(received["sender_session_id"], "sess-1")
        self.assertEqual(received["sender_color"], "red")

    async def test_audio_binary_relay(self):
        self.room.add_peer(self.peer1)
        self.room.add_peer(self.peer2)

        audio_bytes = b"\x01\x02\x03\x04"
        await self.room.relay_audio_bytes("sess-1", audio_bytes)

        # ws2 should receive the bytes, ws1 should NOT
        self.ws2.send_bytes.assert_called_once_with(audio_bytes)
        self.ws1.send_bytes.assert_not_called()

    async def test_audio_binary_relay_deafened(self):
        self.room.add_peer(self.peer1)
        self.room.add_peer(self.peer2)
        self.peer2.is_deafened = True

        audio_bytes = b"\x01\x02\x03\x04"
        await self.room.relay_audio_bytes("sess-1", audio_bytes)

        # Since peer2 is deafened, no audio should be sent to peer2
        self.ws2.send_bytes.assert_not_called()

    async def test_audio_multi_party_roster_and_leave(self):
        ws3 = MagicMock()
        ws3.closed = False
        ws3.send_json = AsyncMock()

        ws4 = MagicMock()
        ws4.closed = False
        ws4.send_json = AsyncMock()

        # Add 4 peers to audio room
        peer3 = AudioPeer("sess-3", "Charlie", "yellow", ws3)
        peer4 = AudioPeer("sess-4", "David", "blue", ws4)
        self.room.add_peer(self.peer1)
        self.room.add_peer(self.peer2)
        self.room.add_peer(peer3)
        self.room.add_peer(peer4)

        roster = self.room.get_roster()
        self.assertEqual(len(roster), 4)

        # Peer 3 leaves
        await self.mgr.handle_audio_message(ws3, "sess-3", {
            "type": "audio_leave",
            "room_id": "TEST-ROOM"
        })
        self.assertIsNone(self.room.get_peer("sess-3"))
        self.assertEqual(len(self.room.get_roster()), 3)


if __name__ == "__main__":
    unittest.main()
