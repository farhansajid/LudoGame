"""
Frontend DOM & Asset Integrity Test
"""
import unittest
from pathlib import Path


class TestFrontendIntegrity(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent.parent
        with open(self.root / "static" / "index.html", "r", encoding="utf-8") as f:
            self.html = f.read()

    def test_dom_elements_present(self):
        required_ids = [
            "screen-home", "screen-lobby", "screen-game",
            "modal-settings", "modal-audio", "modal-victory",
            "turn-banner", "turn-text", "dice-container",
            "chat-messages", "chat-input", "btn-chat-send",
            "floating-reactions", "btn-mic-toggle", "btn-deafen-toggle",
            "btn-audio-settings", "voice-status-badge", "ludo-canvas",
            "btn-mode-bot", "btn-mode-local", "btn-mode-host", "btn-mode-join",
            "btn-start-game", "btn-copy-room-link", "btn-leave-room",
            "btn-open-settings", "btn-close-settings", "btn-close-audio",
            "profile-name-input", "lobby-room-code", "lobby-players-list",
            "mic-test-meter-fill", "btn-test-mic", "audio-ptt-checkbox",
            "master-voice-slider", "audio-peers-list", "victory-podium",
            "btn-victory-rematch", "lan-ip-display", "count-buttons",
            "btn-format-2", "btn-format-3", "btn-format-4",
            "btn-format-team", "btn-format-6", "btn-format-8",
            "btn-dice-single", "btn-dice-double", "setting-twodice-toggle",
            "lobby-format-badge", "lobby-dice-badge", "lobby-dice-text",
            "team-scoreboard", "setting-team-mode-toggle",
            "player-card-red", "player-card-green", "player-card-yellow", "player-card-blue",
            "player-card-orange", "player-card-purple", "player-card-cyan", "player-card-pink",
            "btn-toggle-updates", "btn-quit-game", "home-color-picker", "difficulty-buttons",
            "lobby-diff-badge", "lobby-color-picker", "game-updates-corner", "btn-updates-toggle-corner",
            "game-updates-stream", "private-call-banner", "btn-use-both-dice", "modal-quit",
            "modal-incoming-call", "player-dice-red", "player-dice-green", "player-dice-yellow", "player-dice-blue"
        ]
        for id_name in required_ids:
            self.assertIn(f'id="{id_name}"', self.html, f"Missing id: {id_name}")

    def test_scripts_and_css_linked(self):
        scripts = [
            "sound_engine.js", "audio_system.js", "dice_roller.js",
            "ludo_board.js", "network_client.js", "app.js"
        ]
        for sc in scripts:
            self.assertIn(f'src="/static/js/{sc}"', self.html, f"Missing script: {sc}")

        css_files = ["/static/css/style.css", "/static/css/themes.css"]
        for cs in css_files:
            self.assertIn(f'href="{cs}"', self.html, f"Missing stylesheet: {cs}")


if __name__ == "__main__":
    unittest.main()
