/**
 * Ludo Master Application Controller
 * Coordinates UI views, game engine network events, 3D dice, canvas board,
 * and the real-time local audio calling system.
 */

class LudoApp {
    constructor() {
        this.net = new NetworkClient();
        this.board = null;
        this.dice = null;

        // User settings
        this.playerName = localStorage.getItem("ludo_player_name") || `Player ${Math.floor(Math.random() * 899 + 100)}`;
        this.playerAvatar = localStorage.getItem("ludo_player_avatar") || "lion";
        this.theme = localStorage.getItem("ludo_theme") || "wood";

        // Current room / game state
        this.currentRoomId = null;
        this.isHost = false;
        this.myColor = localStorage.getItem("ludo_preferred_color") || "red";
        this.difficulty = localStorage.getItem("ludo_ai_difficulty") || "hard";
        this.gameUpdatesEnabled = localStorage.getItem("ludo_game_updates") !== "false";
        this.boardSize = localStorage.getItem("ludo_board_size") || "large";
        this.sessionId = null;
        this.roomState = null;
        this.gameState = null;
        this.isMyTurn = false;
        this.selectedMode = "online";
        this.selectedPlayerCount = parseInt(localStorage.getItem("ludo_player_count") || "4", 10);
        this.openOnOne = localStorage.getItem("ludo_open_on_one") !== "false";
        this.teamMode = localStorage.getItem("ludo_team_mode") === "true";
        this.twoDiceMode = localStorage.getItem("ludo_two_dice_mode") === "true";
        this.autoMoveSingle = localStorage.getItem("ludo_auto_move") !== "false";
        this.turnTimerInterval = null;
        this.pendingCallerSid = null;
        this.personalDiceState = {};
        this.testAudioSource = null;
        this.testAudioGain = null;
        this.isTestingMicLoop = false;

        this._init();
    }

    async _init() {
        this._bindDomElements();
        this._initSubsystems();
        this._setupNetworkEvents();
        this._setupAudioEvents();
        this._setupUIListeners();

        // Apply saved theme & board size
        this.applyTheme(this.theme);
        this.applyBoardSize(this.boardSize);
        this.setGameUpdatesEnabled(this.gameUpdatesEnabled);
        this._syncColorPickerUI(this.myColor);
        this._syncDifficultyUI(this.difficulty);

        // Connect network
        this.net.connect();

        // Fetch server status to display LAN IP
        try {
            const resp = await fetch("/api/status");
            const data = await resp.json();
            if (data.local_ip) {
                this.lanIp = data.local_ip;
                const ipLabel = document.getElementById("lan-ip-display");
                if (ipLabel) ipLabel.innerText = `http://${data.local_ip}:${window.location.port || "8080"}`;
            }
        } catch (e) {
            console.log("Status API error:", e);
        }
    }

    _bindDomElements() {
        // Screens
        this.screenHome = document.getElementById("screen-home");
        this.screenLobby = document.getElementById("screen-lobby");
        this.screenGame = document.getElementById("screen-game");

        // Modals
        this.modalSettings = document.getElementById("modal-settings");
        this.modalAudio = document.getElementById("modal-audio");
        this.modalVictory = document.getElementById("modal-victory");
        this.modalQuit = document.getElementById("modal-quit");
        this.modalIncomingCall = document.getElementById("modal-incoming-call");

        // UI Displays
        this.turnBanner = document.getElementById("turn-banner");
        this.turnText = document.getElementById("turn-text");
        this.turnIcon = document.getElementById("turn-icon");
        this.turnTimerBar = document.getElementById("turn-timer-bar");
        this.diceContainer = document.getElementById("dice-container");
        this.chatMessages = document.getElementById("chat-messages");
        this.chatInput = document.getElementById("chat-input");
        this.btnChatSend = document.getElementById("btn-chat-send");
        this.floatingReactionsContainer = document.getElementById("floating-reactions");

        // Header and Quit Buttons
        this.btnToggleUpdates = document.getElementById("btn-toggle-updates");
        this.btnQuitGame = document.getElementById("btn-quit-game");
        this.btnConfirmQuit = document.getElementById("btn-confirm-quit");
        this.btnCancelQuit = document.getElementById("btn-cancel-quit");

        // Game Updates Stream (Left Corner)
        this.gameUpdatesCorner = document.getElementById("game-updates-corner");
        this.gameUpdatesStream = document.getElementById("game-updates-stream");
        this.btnUpdatesToggleCorner = document.getElementById("btn-updates-toggle-corner");
        this.settingGameUpdatesToggle = document.getElementById("setting-game-updates-toggle");

        // 2-Dice Sum Move & Pass Turn
        this.btnUseBothDice = document.getElementById("btn-use-both-dice");
        this.diceSumVal = document.getElementById("dice-sum-val");
        this.btnPassTurn = document.getElementById("btn-pass-turn");

        // Incoming Call Modal & In-Game Banner
        this.incomingCallerTitle = document.getElementById("incoming-caller-title");
        this.incomingCallerDesc = document.getElementById("incoming-caller-desc");
        this.btnAcceptCall = document.getElementById("btn-accept-call");
        this.btnDeclineCall = document.getElementById("btn-decline-call");
        this.privateCallBanner = document.getElementById("private-call-banner");
        this.privateCallStatusText = document.getElementById("private-call-status-text");
        this.btnEndPrivateCall = document.getElementById("btn-end-private-call");

        // Audio controls
        this.btnMicToggle = document.getElementById("btn-mic-toggle");
        this.btnDeafenToggle = document.getElementById("btn-deafen-toggle");
        this.btnAudioSettings = document.getElementById("btn-audio-settings");
        this.voiceStatusBadge = document.getElementById("voice-status-badge");
        this.btnCallModeConf = document.getElementById("btn-call-mode-conf");
        this.btnCallModeIndiv = document.getElementById("btn-call-mode-indiv");

        // Lobby info elements
        this.lobbyDiffBadge = document.getElementById("lobby-diff-badge");
        this.lobbyDiffText = document.getElementById("lobby-diff-text");
    }

    _initSubsystems() {
        // Init 3D Dice Roller with 2-dice selection support
        this.dice = new DiceRoller(this.diceContainer, () => {
            this.rollDice();
        }, (val, idx) => {
            this.selectDie(val, idx);
        });
        if (this.twoDiceMode) {
            this.dice.setTwoDiceMode(true);
        }

        // Init Canvas Board
        const canvas = document.getElementById("ludo-canvas");
        this.board = new LudoBoard(canvas, (tokenId) => {
            this.moveToken(tokenId);
        });
        this.board.setTheme(this.theme);
        if (this.boardSize && typeof this.board.setSizePreset === "function") {
            this.board.setSizePreset(this.boardSize);
        }

        // Connect audio system to network client
        window.audioSystem.setNetworkClient(this.net);
    }

    _setupNetworkEvents() {
        this.net.on("connect", () => {
            this._showToast("Connected to game server", "success");
        });

        this.net.on("disconnect", () => {
            this.isMovingToken = false;
            this._showToast("Connection lost. Reconnecting...", "warning");
        });

        this.net.on("error", (data) => {
            this.isMovingToken = false;
            this._showToast(data.message || "Action failed", "warning");
        });

        this.net.on("room_joined", (data) => {
            this.sessionId = data.session_id;
            this.currentRoomId = data.room_id;
            this.isHost = data.is_host;
            this.myColor = data.player.color;
            window.audioSystem.sessionId = this.sessionId;

            // Auto-join audio room
            window.audioSystem.joinCall(this.currentRoomId, this.playerName, this.myColor);

            this._syncColorPickerUI(this.myColor);
            if (data.difficulty) this._syncDifficultyUI(data.difficulty);

            this._appendGameUpdate(`Joined room ${this.currentRoomId} as ${this.playerName} (${this.myColor.toUpperCase()})`, "system");

            if (this.roomState && this.roomState.status === "PLAYING") {
                this._switchScreen("screen-game");
                if (this.btnQuitGame) this.btnQuitGame.style.display = "inline-block";
            } else {
                this._switchScreen("screen-lobby");
                if (this.btnQuitGame) this.btnQuitGame.style.display = "none";
            }
            this._updateLobbyUI();
        });

        this.net.on("game_state", (data) => {
            if (!this.currentRoomId || (data.room_id && data.room_id !== this.currentRoomId)) {
                return;
            }
            this.roomState = data;
            this.gameState = data.game;

            if (data.two_dice_mode !== undefined) {
                this.twoDiceMode = !!data.two_dice_mode;
            } else if (this.gameState && this.gameState.two_dice_mode !== undefined) {
                this.twoDiceMode = !!this.gameState.two_dice_mode;
            }
            if (this.dice) {
                this.dice.setTwoDiceMode(this.twoDiceMode);
            }

            if (data.difficulty) {
                this._syncDifficultyUI(data.difficulty);
            }

            if (data.status === "PLAYING") {
                this._switchScreen("screen-game");
                if (this.btnQuitGame) this.btnQuitGame.style.display = "inline-block";
                this._updateGameUI();
            } else if (data.status === "LOBBY") {
                if (this.btnQuitGame) this.btnQuitGame.style.display = "none";
                this._updateLobbyUI();
            }

            this._updateUseBothDiceUI();
            this._renderAllPlayerHudDice();
        });

        this.net.on("game_started", (data) => {
            if (!this.currentRoomId || (data && data.room_id && data.room_id !== this.currentRoomId)) {
                return;
            }
            this._switchScreen("screen-game");
            if (this.btnQuitGame) this.btnQuitGame.style.display = "inline-block";
            this._appendGameUpdate("Game match started! Good luck!", "system");
            if (window.soundEngine) window.soundEngine.playTurnAlert();
        });

        this.net.on("dice_rolled", (data) => {
            if (!this.currentRoomId || (data && data.room_id && data.room_id !== this.currentRoomId)) {
                return;
            }
            const playerObj = this.roomState?.players.find(p => p.color === data.player);
            const pName = playerObj ? playerObj.name : data.player.toUpperCase();
            const rolledText = Array.isArray(data.dice_values) ? data.dice_values.join(" & ") : data.dice;


            this._appendGameUpdate(`🎲 ${pName} rolled ${rolledText}`, "normal");

            if (data.consecutive_sixes_violation) {
                this._appendGameAnnouncement(`⚠️ ${pName} rolled 3 sixes in a row! Turn forfeited.`, "normal");
                this._appendGameUpdate(`⚠️ ${pName} rolled 3 sixes! Turn forfeited.`, "normal");
            } else if (data.auto_passed) {
                this._appendGameAnnouncement(`🎲 ${pName} rolled ${rolledText} (No valid moves - Turn passed)`, "normal");
                this._appendGameUpdate(`🎲 ${pName} rolled ${rolledText} (No valid moves - Turn passed)`, "normal");
            }

            // Update mini personal dice on player's card
            this._updatePlayerHudDice(data.player, (data.dice_values && data.dice_values.length > 0) ? data.dice_values : [data.dice], false);

            const isMe = (data.player === this.myColor || this.selectedMode === "local");
            const rollVals = (data.dice_values && data.dice_values.length > 0) ? data.dice_values : data.dice;

            this.dice.animateRoll(rollVals, () => {
                // In 2-dice mode, configure interactive die selection
                if (this.twoDiceMode && data.dice_values) {
                    if (data.selected_die) {
                        this.dice.selectDieValue(data.selected_die);
                    }
                    if (isMe && !data.auto_passed && !data.consecutive_sixes_violation) {
                        this.dice.setCanSelect(true, data.valid_moves_by_die);
                    }
                }

                // If this is my turn, highlight valid moves and check both-dice button
                if (isMe) {
                    this.board.updateState(this.gameState, data.valid_moves || []);
                    this._updateUseBothDiceUI();

                    // Auto-Move Single Choice feature
                    if (this.autoMoveSingle && data.valid_moves && data.valid_moves.length === 1 && !playerObj?.is_bot) {
                        setTimeout(() => {
                            if (this.gameState && this.gameState.turn_state === "WAIT_MOVE" && this.isMyTurn) {
                                this.moveToken(data.valid_moves[0]);
                            }
                        }, 350);
                    }
                }
            });
        });

        this.net.on("die_selected", (data) => {
            if (!this.currentRoomId || (data && data.room_id && data.room_id !== this.currentRoomId)) return;
            if (this.gameState) {
                this.gameState.selected_die = data.selected_die;
                this.gameState.valid_moves = data.valid_moves;
                if (data.remaining_dice !== undefined) this.gameState.remaining_dice = data.remaining_dice;
                if (data.used_dice !== undefined) this.gameState.used_dice = data.used_dice;
            }
            const isMe = (this.gameState?.current_player === this.myColor || this.selectedMode === "local");
            if (this.twoDiceMode && this.dice) {
                if (data.die_index !== undefined && data.die_index !== null) {
                    this.dice.selectDieIndex(data.die_index, false);
                } else {
                    this.dice.selectDieValue(data.selected_die);
                }
                this.dice.updateDiceStatus(
                    data.remaining_dice || this.gameState?.remaining_dice,
                    data.used_dice || this.gameState?.used_dice,
                    data.selected_die,
                    this.gameState?.valid_moves_by_die,
                    isMe
                );
            }
            if (isMe) {
                this.board.updateState(this.gameState, data.valid_moves || []);
                this._updateUseBothDiceUI();
            }
        });

        this.net.on("token_moved", (data) => {
            if (!this.currentRoomId || (data && data.room_id && data.room_id !== this.currentRoomId)) return;
            const playerObj = this.roomState?.players.find(p => p.color === data.player);

            const pName = playerObj ? playerObj.name : data.player.toUpperCase();

            // Hide both dice sum button after move
            if (this.btnUseBothDice) this.btnUseBothDice.style.display = "none";

            // Update remaining/used dice and turn completion in gameState
            if (this.gameState) {
                if (data.remaining_dice !== undefined) this.gameState.remaining_dice = data.remaining_dice;
                if (data.used_dice !== undefined) this.gameState.used_dice = data.used_dice;
                if (data.turn_complete !== undefined) this.gameState.turn_complete = data.turn_complete;
                this.gameState.selected_die = null;
            }

            // Game Action Announcements in Chat and Left Corner Stream
            if (data.is_partner_assist) {
                const partnerObj = this.roomState?.players?.find(p => p.color === data.moving_color);
                const partnerName = partnerObj ? partnerObj.name : (data.moving_color || "").toUpperCase();
                this._appendGameAnnouncement(`🤝 ${pName} assisted teammate ${partnerName} by moving their pawn!`, "team");
                this._appendGameUpdate(`🤝 ${pName} assisted teammate ${partnerName}!`, "team");
            }

            if (data.old_step === -1 && data.new_step === 0) {
                const isBoost = (data.dice === 1 || data.selected_die === 1);
                this._appendGameAnnouncement(`⚡ ${pName} rolled ${data.dice || data.selected_die} and ${isBoost ? "BOOSTED" : "released"} a pawn from yard!`, "boost");
                this._appendGameUpdate(`⚡ ${pName} ${isBoost ? "BOOSTED" : "released"} pawn from yard!`, "boost");
            } else if (data.captures && data.captures.length > 0) {
                const victim = data.captures[0].player.toUpperCase();
                this._showCenterTurnAlert("⚔️ CAPTURE BONUS! ROLL AGAIN!", "capture", data.player);
                this._appendGameAnnouncement(`⚔️ ${pName} captured ${victim}'s pawn! (+Bonus Turn)`, "capture");
                this._appendGameUpdate(`⚔️ ${pName} captured ${victim}'s pawn! (+Bonus Roll)`, "capture");
                if (window.soundEngine?.playBonusTurn) window.soundEngine.playBonusTurn();
            } else if (data.reached_goal) {
                this._showCenterTurnAlert("👑 GOAL REACHED! ROLL AGAIN!", "goal", data.player);
                this._appendGameAnnouncement(`👑 ${pName}'s pawn reached the GOAL! (+Bonus Turn)`, "goal");
                this._appendGameUpdate(`👑 ${pName}'s pawn reached the GOAL! (+Bonus Roll)`, "goal");
                if (window.soundEngine?.playBonusTurn) window.soundEngine.playBonusTurn();
            } else if (data.escaped_danger) {
                this._appendGameAnnouncement(`💨 ${pName}'s pawn narrowly escaped danger!`, "normal");
                this._appendGameUpdate(`💨 ${pName}'s pawn narrowly escaped danger!`, "normal");
            } else if (data.extra_turn && data.extra_turn_reason === "rolled_six") {
                this._showCenterTurnAlert("🎲 ROLLED A 6! ROLL AGAIN!", "normal", data.player);
                this._appendGameAnnouncement(`🎲 ${pName} rolled a 6! (+Bonus Turn)`, "normal");
                this._appendGameUpdate(`🎲 ${pName} rolled a 6! (+Bonus Roll)`, "normal");
                if (window.soundEngine?.playBonusTurn) window.soundEngine.playBonusTurn();
            }

            const isMe = (data.player === this.myColor || this.selectedMode === "local");

            this.board.animateTokenMove(
                data.moving_color || data.player,
                data.token_id,
                data.old_step,
                data.new_step,
                data.captures,
                () => {
                    this.isMovingToken = false;
                    if (data.turn_complete === false) {
                        // Sequential move in 2-dice mode: Turn is not complete, 2nd die remains!
                        const validMoves = (isMe && this.gameState && this.gameState.turn_state === "WAIT_MOVE")
                            ? (this.gameState.valid_moves || [])
                            : [];
                        this.board.updateState(this.gameState, validMoves);

                        if (this.twoDiceMode && this.dice) {
                            this.dice.updateDiceStatus(
                                data.remaining_dice || this.gameState?.remaining_dice,
                                data.used_dice || this.gameState?.used_dice,
                                this.gameState?.selected_die,
                                this.gameState?.valid_moves_by_die,
                                isMe
                            );
                        }

                        if (this.btnPassTurn) {
                            this.btnPassTurn.style.display = isMe ? "inline-flex" : "none";
                        }

                        if (this.turnBanner && this.turnText && data.remaining_dice && data.remaining_dice.length > 0) {
                            const remDie = data.remaining_dice[0];
                            if (isMe) {
                                this.turnText.innerText = (this.selectedMode === "local")
                                    ? `${pName}: Move 2nd Die (${remDie})`
                                    : `Your Turn: Move 2nd Die (${remDie})`;
                            } else {
                                this.turnText.innerText = `${pName}: Moving 2nd Die (${remDie})...`;
                            }
                        }

                        // Auto-Move Single Choice for 2nd die if enabled
                        if (isMe && this.autoMoveSingle && validMoves.length === 1 && !playerObj?.is_bot) {
                            setTimeout(() => {
                                if (this.gameState && this.gameState.turn_state === "WAIT_MOVE" && this.isMyTurn) {
                                    this.moveToken(validMoves[0]);
                                }
                            }, 350);
                        }
                    } else {
                        if (this.btnPassTurn) this.btnPassTurn.style.display = "none";
                        this.board.updateState(this.gameState, []);
                    }
                },
                Boolean(data.escaped_danger),
                data.dice || data.selected_die
            );
        });

        this.net.on("turn_passed", (data) => {
            if (!this.currentRoomId || (data && data.room_id && data.room_id !== this.currentRoomId)) return;
            const playerObj = this.roomState?.players.find(p => p.color === data.player);
            const pName = playerObj ? playerObj.name : (data.player || "").toUpperCase();
            this._appendGameAnnouncement(`⏭️ ${pName} passed remaining dice move.`, "normal");
            this._appendGameUpdate(`⏭️ ${pName} passed remaining dice.`, "normal");
            if (this.btnPassTurn) this.btnPassTurn.style.display = "none";
            this.board.updateState(this.gameState, []);
        });

        this.net.on("player_left", (data) => {
            if (data.action === "replaced_by_bot") {
                this._appendGameAnnouncement(`🤖 ${data.name} took over seat for ${data.player.toUpperCase()}`, "normal");
                this._appendGameUpdate(`🤖 ${data.name} took over seat for ${data.player.toUpperCase()}`, "system");
            } else {
                this._appendGameAnnouncement(`🚪 ${data.name} left the room.`, "normal");
                this._appendGameUpdate(`🚪 ${data.name} left the room.`, "system");
            }
            if (data.match_ended) {
                this._appendGameAnnouncement("Match ended: All human players have left.", "normal");
                this._appendGameUpdate("Match ended: All human players have left.", "system");
            }
        });

        this.net.on("left_game_ack", () => {
            this._resetGameToHome();
        });

        this.net.on("game_over", (data) => {
            setTimeout(() => {
                this._showVictoryModal(data.winners);
            }, 1200);
        });

        this.net.on("rematch_started", () => {
            if (this.modalVictory) {
                this.modalVictory.classList.remove("open");
            }
            this._showToast("Rematch started! Good luck!", "info");
        });

        this.net.on("chat_message", (data) => {
            this._appendChatMessage(data.sender, data.color, data.text);
        });

        this.net.on("reaction", (data) => {
            this._spawnFloatingReaction(data.emoji, data.color);
        });

        // Forward audio signaling events to audio system
        this.net.on("message", (data) => {
            if (data.type && data.type.startsWith("audio_")) {
                window.audioSystem.handleSignalingMessage(data);
            }
        });
    }

    _setupAudioEvents() {
        // Speaking status (glow avatar and voice wave)
        window.audioSystem.onSpeakingChange = (sessionId, isSpeaking, level) => {
            const playerColor = this._getColorBySessionId(sessionId);
            if (playerColor) {
                this._updatePlayerSpeakingUI(playerColor, isSpeaking, level);
            }
        };

        // Peer mute / deafen updates
        window.audioSystem.onPeerStateChange = (sessionId, state) => {
            const playerColor = this._getColorBySessionId(sessionId);
            if (playerColor) {
                this._updatePlayerAudioStateUI(playerColor, state);
            }
        };

        // Roster updates
        window.audioSystem.onRosterUpdate = (peers) => {
            if (this.voiceStatusBadge) {
                this.voiceStatusBadge.innerHTML = `<span class="voice-dot online"></span> Voice: ${peers.length} in Call`;
            }
            this._refreshAudioPeersList(peers);
        };

        // 1-on-1 Individual Voice Call Callbacks
        window.audioSystem.onIncomingCall = (callerSid, callerName, callerColor) => {
            this.pendingCallerSid = callerSid;
            if (this.incomingCallerTitle) this.incomingCallerTitle.innerText = "Incoming Private Call";
            if (this.incomingCallerDesc) {
                this.incomingCallerDesc.innerText = `${callerName} (${(callerColor || "").toUpperCase()}) is calling you for a 1-on-1 private voice call.`;
            }
            if (this.modalIncomingCall) this.modalIncomingCall.classList.add("open");
            if (window.soundEngine?.playTurnAlert) window.soundEngine.playTurnAlert();
        };

        window.audioSystem.onPrivateCallConnected = (peerSid, peerName, peerColor) => {
            if (this.modalIncomingCall) this.modalIncomingCall.classList.remove("open");
            if (this.privateCallBanner) {
                this.privateCallBanner.style.display = "flex";
                if (this.privateCallStatusText) {
                    this.privateCallStatusText.innerText = `🔒 In 1-on-1 Call with ${peerName}`;
                }
            }
            this._syncCallModeUI("individual");
            this._showToast(`Connected to private call with ${peerName}`, "success");
        };

        window.audioSystem.onCallDeclined = (targetSid) => {
            this._showToast("1-on-1 private call was declined.", "warning");
        };

        window.audioSystem.onPrivateCallEnded = () => {
            if (this.privateCallBanner) this.privateCallBanner.style.display = "none";
            this._syncCallModeUI("conference");
            this._showToast("Private call ended. Switched back to Conference.", "info");
        };

        window.audioSystem.onError = (msg) => {
            this._showToast(msg, "warning");
        };
    }

    _setupUIListeners() {
        // Home Screen Buttons
        document.getElementById("btn-mode-bot").addEventListener("click", () => {
            this.startSinglePlayerGame();
        });

        document.getElementById("btn-mode-local").addEventListener("click", () => {
            this.startLocalGame();
        });

        document.getElementById("btn-mode-host").addEventListener("click", () => {
            this.hostLanGame();
        });

        document.getElementById("btn-mode-join").addEventListener("click", () => {
            const code = prompt("Enter Room Code (e.g. ABCD or LUDO-ABCD):");
            if (code && code.trim()) {
                this.joinOnlineGame(code.trim().toUpperCase());
            }
        });

        // Lobby Buttons
        document.getElementById("btn-start-game").addEventListener("click", () => {
            this.net.send({ type: "start_game" });
        });

        document.getElementById("btn-copy-room-link").addEventListener("click", () => {
            const code = this.currentRoomId || "";
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(code).then(() => {
                    this._showToast(`Copied room code: ${code}`, "success");
                }).catch(() => {
                    this._copyFallback(code);
                });
            } else {
                this._copyFallback(code);
            }
        });

        document.getElementById("btn-leave-room").addEventListener("click", () => {
            this.quitCurrentGame();
        });

        // Quit Match Modal Listeners
        if (this.btnQuitGame) {
            this.btnQuitGame.addEventListener("click", () => {
                if (this.modalQuit) this.modalQuit.classList.add("open");
            });
        }

        if (this.btnCancelQuit) {
            this.btnCancelQuit.addEventListener("click", () => {
                if (this.modalQuit) this.modalQuit.classList.remove("open");
            });
        }

        if (this.btnConfirmQuit) {
            this.btnConfirmQuit.addEventListener("click", () => {
                if (this.modalQuit) this.modalQuit.classList.remove("open");
                this.quitCurrentGame();
            });
        }

        // Live Game Updates Stream Toggles
        if (this.btnToggleUpdates) {
            this.btnToggleUpdates.addEventListener("click", () => {
                this.toggleGameUpdates();
            });
        }

        if (this.btnUpdatesToggleCorner) {
            this.btnUpdatesToggleCorner.addEventListener("click", () => {
                this.toggleGameUpdates();
            });
        }

        if (this.settingGameUpdatesToggle) {
            this.settingGameUpdatesToggle.checked = this.gameUpdatesEnabled;
            this.settingGameUpdatesToggle.addEventListener("change", (e) => {
                this.setGameUpdatesEnabled(e.target.checked);
            });
        }

        // Board Size Presets
        document.querySelectorAll("#board-size-buttons .rule-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                this.applyBoardSize(btn.dataset.size);
            });
        });

        // Choose Your Color (Home Screen)
        document.querySelectorAll("#home-color-picker .color-select-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                this.setColor(btn.dataset.color);
            });
        });

        // Switch Color in Lobby
        document.querySelectorAll("#lobby-color-picker .color-select-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                this.changeLobbyColor(btn.dataset.color);
            });
        });

        // AI Difficulty Level Selector (Home & Settings)
        document.querySelectorAll("#difficulty-buttons .rule-btn, #setting-difficulty-buttons .rule-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                this.setDifficulty(btn.dataset.diff);
            });
        });

        // 2-Dice Sum Move Button
        if (this.btnUseBothDice) {
            this.btnUseBothDice.addEventListener("click", () => {
                this.useBothDiceSum();
            });
        }

        // Pass Remaining Turn Button
        if (this.btnPassTurn) {
            this.btnPassTurn.addEventListener("click", () => {
                this.passTurn();
            });
        }

        // Personal Dice HUD Click to Roll
        document.querySelectorAll(".player-hud-dice").forEach(diceEl => {
            diceEl.addEventListener("click", (e) => {
                e.stopPropagation();
                const card = diceEl.closest(".player-hud-card");
                const cardColor = card ? card.id.replace("player-card-", "") : null;
                const isCurrent = cardColor && (cardColor === this.gameState?.current_player);
                const canRoll = this.isMyTurn && isCurrent && (this.gameState?.turn_state === "WAIT_ROLL");
                if (canRoll) {
                    this.rollDice();
                }
            });
        });

        // 1-on-1 Individual Audio Call Buttons on HUD Cards
        document.querySelectorAll(".btn-private-call").forEach(btn => {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                const targetColor = btn.dataset.color;
                const targetPlayer = this.roomState?.players?.find(p => p.color === targetColor);
                if (!targetPlayer) return;
                if (targetPlayer.color === this.myColor) {
                    this._showToast("You cannot call yourself.", "warning");
                    return;
                }
                if (targetPlayer.is_bot) {
                    this._showToast("Cannot start a voice call with an AI bot.", "warning");
                    return;
                }
                if (!targetPlayer.session_id) {
                    this._showToast("Player is not connected to voice.", "warning");
                    return;
                }
                window.audioSystem.requestIndividualCall(targetPlayer.session_id);
                this._showToast(`Calling ${targetPlayer.name} privately...`, "info");
            });
        });

        // Incoming Call Modal Actions
        if (this.btnAcceptCall) {
            this.btnAcceptCall.addEventListener("click", () => {
                if (this.pendingCallerSid) {
                    window.audioSystem.acceptIndividualCall(this.pendingCallerSid);
                }
                if (this.modalIncomingCall) this.modalIncomingCall.classList.remove("open");
            });
        }

        if (this.btnDeclineCall) {
            this.btnDeclineCall.addEventListener("click", () => {
                if (this.pendingCallerSid) {
                    window.audioSystem.declineIndividualCall(this.pendingCallerSid);
                }
                if (this.modalIncomingCall) this.modalIncomingCall.classList.remove("open");
            });
        }

        // Active Private Call Banner End Button
        if (this.btnEndPrivateCall) {
            this.btnEndPrivateCall.addEventListener("click", () => {
                window.audioSystem.endIndividualCall();
            });
        }

        // Call Mode Selection in Voice Modal
        if (this.btnCallModeConf) {
            this.btnCallModeConf.addEventListener("click", () => {
                window.audioSystem.setCallMode("conference");
                this._syncCallModeUI("conference");
                this._showToast("Voice Mode: Conference (All players)", "info");
            });
        }

        if (this.btnCallModeIndiv) {
            this.btnCallModeIndiv.addEventListener("click", () => {
                this._syncCallModeUI("individual");
                this._showToast("Click the 📞 button on any player's card to start a 1-on-1 call.", "info");
            });
        }

        // Chat & Reactions
        this.btnChatSend.addEventListener("click", () => this._sendChatMessage());
        this.chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") this._sendChatMessage();
        });

        document.querySelectorAll(".reaction-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const emoji = btn.innerText;
                this.net.send({ type: "reaction", emoji: emoji });
            });
        });

        // Voice Toolbar Controls
        this.btnMicToggle.addEventListener("click", () => {
            const isMuted = window.audioSystem.toggleMute();
            this._updateMicButtonUI(isMuted);
        });

        this.btnDeafenToggle.addEventListener("click", () => {
            const isDeafened = window.audioSystem.toggleDeafen();
            this._updateDeafenButtonUI(isDeafened);
        });

        this.btnAudioSettings.addEventListener("click", () => {
            this._openAudioSettingsModal();
        });

        // Settings Modal
        document.getElementById("btn-open-settings").addEventListener("click", () => {
            this.modalSettings.classList.add("open");
        });

        document.getElementById("btn-close-settings").addEventListener("click", () => {
            this.modalSettings.classList.remove("open");
        });

        document.getElementById("btn-close-audio").addEventListener("click", () => {
            this.modalAudio.classList.remove("open");
            this._stopMicLoopbackTest();
        });

        // Theme Selectors
        document.querySelectorAll(".theme-option").forEach(el => {
            el.addEventListener("click", () => {
                const th = el.dataset.theme;
                this.applyTheme(th);
            });
        });

        // Profile Inputs
        const nameInput = document.getElementById("profile-name-input");
        if (nameInput) {
            nameInput.value = this.playerName;
            nameInput.addEventListener("change", (e) => {
                this.playerName = e.target.value.trim() || "Player";
                localStorage.setItem("ludo_player_name", this.playerName);
            });
        }

        // Player Count Selection Buttons
        document.querySelectorAll(".count-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".count-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                if (btn.dataset.count === "team") {
                    this.teamMode = true;
                    this.selectedPlayerCount = 4;
                    localStorage.setItem("ludo_team_mode", "true");
                } else {
                    this.teamMode = false;
                    this.selectedPlayerCount = parseInt(btn.dataset.count, 10);
                    localStorage.setItem("ludo_player_count", this.selectedPlayerCount);
                    localStorage.setItem("ludo_team_mode", "false");
                }
                const settingTeam = document.getElementById("setting-team-mode-toggle");
                if (settingTeam) settingTeam.checked = this.teamMode;
                this._updateVisibleColors(this.selectedPlayerCount);
            });
        });

        // Initialize active format button based on saved state
        if (this.teamMode) {
            const btnTeam = document.getElementById("btn-format-team");
            if (btnTeam) {
                document.querySelectorAll(".count-btn").forEach(b => b.classList.remove("active"));
                btnTeam.classList.add("active");
            }
        } else if (this.selectedPlayerCount) {
            const btnCount = document.querySelector(`.count-btn[data-count="${this.selectedPlayerCount}"]`);
            if (btnCount) {
                document.querySelectorAll(".count-btn").forEach(b => b.classList.remove("active"));
                btnCount.classList.add("active");
            }
        }
        this._updateVisibleColors(this.selectedPlayerCount);

        // Opening Rule Pickers & Settings
        const btnRuleFast = document.getElementById("btn-rule-fast");
        const btnRuleClassic = document.getElementById("btn-rule-classic");
        const settingRuleToggle = document.getElementById("setting-open-one-toggle");
        const settingTeamToggle = document.getElementById("setting-team-mode-toggle");
        const settingAutoMoveToggle = document.getElementById("setting-automove-toggle");
        const settingSfxSlider = document.getElementById("setting-sfx-slider");
        const settingSfxVal = document.getElementById("setting-sfx-val");

        // 2-Dice Mode Pickers & Settings
        const btnDiceSingle = document.getElementById("btn-dice-single");
        const btnDiceDouble = document.getElementById("btn-dice-double");
        const settingTwoDiceToggle = document.getElementById("setting-twodice-toggle");

        const updateDiceModeUI = (twoDice) => {
            this.twoDiceMode = !!twoDice;
            localStorage.setItem("ludo_two_dice_mode", this.twoDiceMode ? "true" : "false");
            if (btnDiceSingle) btnDiceSingle.classList.toggle("active", !this.twoDiceMode);
            if (btnDiceDouble) btnDiceDouble.classList.toggle("active", this.twoDiceMode);
            if (settingTwoDiceToggle) settingTwoDiceToggle.checked = this.twoDiceMode;
            if (this.dice) this.dice.setTwoDiceMode(this.twoDiceMode);
            if (this.currentRoomId && this.isHost) {
                this.net.send({ type: "update_rules", two_dice_mode: this.twoDiceMode });
            }
        };

        if (btnDiceSingle) btnDiceSingle.onclick = () => updateDiceModeUI(false);
        if (btnDiceDouble) btnDiceDouble.onclick = () => updateDiceModeUI(true);
        if (settingTwoDiceToggle) {
            settingTwoDiceToggle.checked = this.twoDiceMode;
            settingTwoDiceToggle.onchange = (e) => updateDiceModeUI(e.target.checked);
        }
        if (this.twoDiceMode) {
            if (btnDiceSingle) btnDiceSingle.classList.remove("active");
            if (btnDiceDouble) btnDiceDouble.classList.add("active");
        }

        const updateRuleUI = (openOnOne) => {
            this.openOnOne = openOnOne;
            localStorage.setItem("ludo_open_on_one", openOnOne);
            if (btnRuleFast) btnRuleFast.classList.toggle("active", openOnOne);
            if (btnRuleClassic) btnRuleClassic.classList.toggle("active", !openOnOne);
            if (settingRuleToggle) settingRuleToggle.checked = openOnOne;
            if (this.currentRoomId && this.isHost) {
                this.net.send({ type: "update_rules", open_on_one: openOnOne });
            }
        };

        if (btnRuleFast) btnRuleFast.onclick = () => updateRuleUI(true);
        if (btnRuleClassic) btnRuleClassic.onclick = () => updateRuleUI(false);
        if (settingRuleToggle) {
            settingRuleToggle.checked = this.openOnOne;
            settingRuleToggle.onchange = (e) => updateRuleUI(e.target.checked);
        }

        if (settingTeamToggle) {
            settingTeamToggle.checked = this.teamMode;
            settingTeamToggle.onchange = (e) => {
                this.teamMode = e.target.checked;
                localStorage.setItem("ludo_team_mode", this.teamMode ? "true" : "false");
                document.querySelectorAll(".count-btn").forEach(b => b.classList.remove("active"));
                if (this.teamMode) {
                    const btnTeam = document.getElementById("btn-format-team");
                    if (btnTeam) btnTeam.classList.add("active");
                    this.selectedPlayerCount = 4;
                } else {
                    const btn4 = document.querySelector('.count-btn[data-count="4"]');
                    if (btn4) btn4.classList.add("active");
                }
                if (this.currentRoomId && this.isHost) {
                    this.net.send({ type: "update_rules", team_mode: this.teamMode });
                }
            };
        }

        if (settingAutoMoveToggle) {
            settingAutoMoveToggle.checked = this.autoMoveSingle;
            settingAutoMoveToggle.onchange = (e) => {
                this.autoMoveSingle = e.target.checked;
                localStorage.setItem("ludo_auto_move", this.autoMoveSingle);
            };
        }

        if (settingSfxSlider) {
            settingSfxSlider.oninput = (e) => {
                const vol = parseInt(e.target.value, 10);
                if (settingSfxVal) settingSfxVal.innerText = `${vol}%`;
                if (window.soundEngine) window.soundEngine.setVolume(vol / 100);
            };
        }
    }

    // --- Game Actions ---
    rollDice() {
        if (!this.gameState || this.gameState.turn_state !== "WAIT_ROLL") return;
        this.net.send({ type: "roll_dice" });
    }

    selectDie(dieVal, dieIdx = null) {
        if (!this.gameState || this.gameState.turn_state !== "WAIT_MOVE") return;
        this.gameState.selected_die = dieVal;
        const payload = { type: "select_die", die_value: dieVal };
        if (dieIdx !== null && dieIdx !== undefined) {
            payload.die_index = dieIdx;
        }
        this.net.send(payload);
    }

    moveToken(tokenId) {
        if (!this.gameState || this.gameState.turn_state !== "WAIT_MOVE" || this.isMovingToken) return;
        this.isMovingToken = true;
        const payload = { type: "move_token", token_id: tokenId };
        if (this.twoDiceMode && this.gameState.selected_die) {
            payload.selected_die = this.gameState.selected_die;
        }
        this.net.send(payload);
    }

    passTurn() {
        if (!this.gameState || this.gameState.turn_state !== "WAIT_MOVE" || !this.isMyTurn) return;
        this.net.send({ type: "pass_turn" });
    }

    startSinglePlayerGame() {
        this.selectedMode = "single";
        const code = `BOT-${Math.floor(Math.random() * 8999 + 1000)}`;
        this.net.send({
            type: "join_room",
            room_id: code,
            name: this.playerName,
            avatar: this.playerAvatar,
            color: this.myColor,
            preferred_color: this.myColor,
            difficulty: this.difficulty,
            mode: "single",
            player_count: this.selectedPlayerCount,
            open_on_one: this.openOnOne,
            team_mode: this.teamMode,
            two_dice_mode: this.twoDiceMode
        });
    }

    startLocalGame() {
        this.selectedMode = "local";
        const code = `LOCAL-${Math.floor(Math.random() * 8999 + 1000)}`;
        this.net.send({
            type: "join_room",
            room_id: code,
            name: this.playerName,
            avatar: this.playerAvatar,
            color: this.myColor,
            preferred_color: this.myColor,
            difficulty: this.difficulty,
            mode: "local",
            player_count: this.selectedPlayerCount,
            open_on_one: this.openOnOne,
            team_mode: this.teamMode,
            two_dice_mode: this.twoDiceMode
        });
    }

    hostLanGame() {
        this.selectedMode = "online";
        const code = `LUDO-${Math.floor(Math.random() * 8999 + 1000)}`;
        this.net.send({
            type: "join_room",
            room_id: code,
            name: this.playerName,
            avatar: this.playerAvatar,
            color: this.myColor,
            preferred_color: this.myColor,
            difficulty: this.difficulty,
            mode: "online",
            player_count: this.selectedPlayerCount,
            open_on_one: this.openOnOne,
            team_mode: this.teamMode,
            two_dice_mode: this.twoDiceMode
        });
    }

    joinOnlineGame(roomCode) {
        this.selectedMode = "online";
        let code = (roomCode || "").trim().toUpperCase();
        if (code && !code.startsWith("LUDO-") && !code.startsWith("BOT-") && !code.startsWith("LOCAL-")) {
            code = `LUDO-${code}`;
        }
        this.net.send({
            type: "join_room",
            room_id: code,
            name: this.playerName,
            avatar: this.playerAvatar,
            color: this.myColor,
            preferred_color: this.myColor,
            difficulty: this.difficulty,
            mode: "online",
            player_count: this.selectedPlayerCount,
            open_on_one: this.openOnOne,
            team_mode: this.teamMode,
            two_dice_mode: this.twoDiceMode
        });
    }

    // --- UI Renderers & State Updates ---
    _switchScreen(screenId) {
        [this.screenHome, this.screenLobby, this.screenGame].forEach(sc => {
            if (sc) sc.classList.remove("active");
        });
        const target = document.getElementById(screenId);
        if (target) target.classList.add("active");

        if (screenId === "screen-game") {
            requestAnimationFrame(() => {
                if (this.board && typeof this.board.resize === "function") {
                    this.board.resize();
                } else {
                    window.dispatchEvent(new Event("resize"));
                }
            });
            setTimeout(() => {
                if (this.board && typeof this.board.resize === "function") {
                    this.board.resize();
                }
            }, 60);
        }
    }

    _updateLobbyUI() {
        if (!this.roomState) return;

        const codeEl = document.getElementById("lobby-room-code");
        if (codeEl) codeEl.innerText = this.currentRoomId;

        const playersList = document.getElementById("lobby-players-list");
        if (playersList) {
            playersList.innerHTML = "";
            this.roomState.players.forEach(p => {
                const item = document.createElement("div");
                item.className = `lobby-player-card color-${p.color}`;
                const teamTag = this.roomState.team_mode
                    ? (p.color === "red" || p.color === "yellow"
                        ? '<span style="font-size:11px; font-weight:700; color:#ffd700; margin-left:6px;">[Team Alpha]</span>'
                        : '<span style="font-size:11px; font-weight:700; color:#00f0ff; margin-left:6px;">[Team Bravo]</span>')
                    : "";

                item.innerHTML = `
                    <div class="player-avatar-wrap">
                        <span class="player-avatar-icon">${this._getAvatarEmoji(p.avatar)}</span>
                    </div>
                    <div class="player-details">
                        <div class="player-name">${p.name} ${teamTag} ${p.is_host ? "👑" : ""}</div>
                        <div class="player-role">${p.is_bot ? "🤖 Smart AI Bot" : "🎮 Human Player"}</div>
                    </div>
                    <div class="player-status ${p.is_ready ? "ready" : "waiting"}">
                        ${p.is_ready ? "Ready" : "Waiting"}
                    </div>
                `;
                playersList.appendChild(item);
            });
        }

        const rulesText = document.getElementById("lobby-rules-text");
        if (rulesText && this.roomState) {
            rulesText.innerText = (this.roomState.open_on_one !== false) ? "⚡ Fast Boost (1 or 6)" : "🎯 Classic (6 Only)";
        }

        const formatText = document.getElementById("lobby-format-text");
        if (formatText && this.roomState) {
            const maxP = this.roomState.max_players;
            if (this.roomState.team_mode) {
                formatText.innerText = "🤝 2v2 Teamwork [Preview]";
            } else if (maxP === 2) {
                formatText.innerText = "⚔️ 2 Players (Duel)";
            } else if (maxP === 3) {
                formatText.innerText = "🎯 3 Players";
            } else if (maxP === 6) {
                formatText.innerText = "🌟 6 Players (Hexagon)";
            } else if (maxP === 8) {
                formatText.innerText = "💥 8 Players (Octagon)";
            } else {
                formatText.innerText = "👑 4 Players (Classic)";
            }
        }

        const diceText = document.getElementById("lobby-dice-text");
        if (diceText && this.roomState) {
            const is2Dice = (this.roomState.two_dice_mode !== undefined) ? this.roomState.two_dice_mode : this.twoDiceMode;
            diceText.innerText = is2Dice ? "🎲🎲 2-Dice (Choice)" : "🎲 1-Die (Standard)";
        }

        const diffText = document.getElementById("lobby-diff-text");
        if (diffText && this.roomState && this.roomState.difficulty) {
            const label = this.roomState.difficulty === "easy" ? "🟢 Easy (Casual)" : this.roomState.difficulty === "medium" ? "🟡 Medium (Standard)" : "🔴 Hard (Master AI)";
            diffText.innerText = label;
        }

        const btnStart = document.getElementById("btn-start-game");
        if (btnStart) {
            btnStart.style.display = (this.isHost || this.selectedMode !== "online") ? "block" : "none";
        }

        this._syncColorPickerUI(this.myColor);
    }

    _updateGameUI() {
        if (!this.gameState) return;

        // Update Board State
        const validMoves = (this.gameState.turn_state === "WAIT_MOVE" && (this.gameState.current_player === this.myColor || this.selectedMode === "local"))
            ? this.gameState.valid_moves : [];

        this.board.updateState(this.gameState, validMoves);
        if (this.board && this.board.canvas && (this.board.canvas.width === 0 || this.board.canvas.height === 0)) {
            this.board.resize();
        }

        // Update Team Scoreboard in 2v2 mode
        const teamScoreboard = document.getElementById("team-scoreboard");
        if (teamScoreboard) {
            if (this.gameState.team_mode) {
                teamScoreboard.style.display = "flex";
                let alphaGoals = 0;
                let bravoGoals = 0;
                this.gameState.players.forEach(p => {
                    const count = p.tokens ? p.tokens.filter(t => t.step === 56).length : 0;
                    if (p.color === "red" || p.color === "yellow") alphaGoals += count;
                    else bravoGoals += count;
                });
                const elA = document.getElementById("score-team-alpha");
                const elB = document.getElementById("score-team-bravo");
                if (elA) elA.innerText = `${alphaGoals}/8`;
                if (elB) elB.innerText = `${bravoGoals}/8`;
            } else {
                teamScoreboard.style.display = "none";
            }
        }

        // Turn Management
        const currColor = this.gameState.current_player;
        const currPlayer = this.roomState.players.find(p => p.color === currColor);
        const currName = currPlayer ? currPlayer.name : currColor.toUpperCase();

        this.isMyTurn = (currColor === this.myColor || this.selectedMode === "local");

        // Turn Timer
        if (this.lastTurnPlayerColor !== currColor || this.lastTurnState !== this.gameState.turn_state) {
            this.lastTurnPlayerColor = currColor;
            this.lastTurnState = this.gameState.turn_state;
            this._resetTurnTimer();
        }

        // Update Turn Banner with prominent center positioning and icons
        if (this.turnBanner && this.turnText) {
            this.turnBanner.className = `turn-banner color-${currColor} center-turn-banner ${this.isMyTurn ? "my-turn-pulse" : ""}`;
            const gamePlayer = this.gameState.players?.find(p => p.color === currColor);
            const isAssisting = this.gameState.team_mode && (gamePlayer?.has_won || (gamePlayer?.tokens && gamePlayer.tokens.every(t => t.step === 56 || t.is_in_goal)));
            const partnerColor = { red: "yellow", yellow: "red", green: "blue", blue: "green" }[currColor];
            const partnerPlayer = this.roomState?.players?.find(p => p.color === partnerColor);
            const partnerName = partnerPlayer ? partnerPlayer.name : (partnerColor ? partnerColor.toUpperCase() : "Partner");

            if (this.turnIcon) {
                if (isAssisting) {
                    this.turnIcon.innerText = "🤝";
                } else if (this.isMyTurn) {
                    this.turnIcon.innerText = this.gameState.turn_state === "WAIT_ROLL" ? "🎲" : "🎯";
                } else if (currPlayer?.is_bot) {
                    this.turnIcon.innerText = "🤖";
                } else {
                    this.turnIcon.innerText = "⏳";
                }
            }

            if (this.selectedMode === "local") {
                if (isAssisting) {
                    this.turnText.innerText = `${currName} (Finished) - Rolling to ASSIST ${partnerName}!`;
                } else if (this.gameState.turn_state === "WAIT_ROLL") {
                    this.turnText.innerText = `${currName}'s Turn! Roll the Dice`;
                } else if (this.twoDiceMode) {
                    if (this.gameState.used_dice && this.gameState.used_dice.length > 0 && this.gameState.remaining_dice && this.gameState.remaining_dice.length > 0) {
                        this.turnText.innerText = `${currName}: Move 2nd Die (${this.gameState.remaining_dice[0]})`;
                    } else {
                        this.turnText.innerText = `${currName}: Select a Die, Use Both, or Move Token`;
                    }
                } else {
                    this.turnText.innerText = `${currName}: Choose a Token to Move`;
                }
            } else if (this.isMyTurn) {
                if (isAssisting) {
                    this.turnText.innerText = `You finished! Rolling to ASSIST teammate ${partnerName}!`;
                } else if (this.gameState.turn_state === "WAIT_ROLL") {
                    this.turnText.innerText = "Your Turn! Roll the Dice";
                } else if (this.twoDiceMode) {
                    if (this.gameState.used_dice && this.gameState.used_dice.length > 0 && this.gameState.remaining_dice && this.gameState.remaining_dice.length > 0) {
                        this.turnText.innerText = `Your Turn: Move 2nd Die (${this.gameState.remaining_dice[0]})`;
                    } else {
                        this.turnText.innerText = "Select a Die, Use Both, or Move Token";
                    }
                } else {
                    this.turnText.innerText = "Your Turn: Choose a Token to Move";
                }
            } else {
                if (isAssisting) {
                    this.turnText.innerText = `${currName} is assisting teammate ${partnerName}...`;
                } else if (this.twoDiceMode && this.gameState.used_dice && this.gameState.used_dice.length > 0 && this.gameState.remaining_dice && this.gameState.remaining_dice.length > 0) {
                    this.turnText.innerText = `${currName}: Moving 2nd Die (${this.gameState.remaining_dice[0]})...`;
                } else {
                    this.turnText.innerText = `${currName}'s Turn...`;
                }
            }
        }

        // Dice Can Roll & Selection State
        if (this.isMyTurn && this.gameState.turn_state === "WAIT_ROLL") {
            this.dice.setCanRoll(true, "ROLL");
            if (window.soundEngine && !currPlayer?.is_bot && this.lastAlertPlayerColor !== currColor) {
                window.soundEngine.playTurnAlert();
                this.lastAlertPlayerColor = currColor;
            }
        } else {
            this.dice.setCanRoll(false);
            if (this.twoDiceMode) {
                if (this.gameState.dice_values) {
                    this.dice.showValues(this.gameState.dice_values);
                } else if (this.gameState.dice_value) {
                    this.dice.showValues([this.gameState.dice_value, 1]);
                }
                const canSelect = this.isMyTurn && this.gameState.turn_state === "WAIT_MOVE";
                this.dice.updateDiceStatus(
                    this.gameState.remaining_dice,
                    this.gameState.used_dice,
                    this.gameState.selected_die,
                    this.gameState.valid_moves_by_die,
                    canSelect
                );
            } else if (this.gameState.dice_value) {
                this.dice.showValue(this.gameState.dice_value);
            }
        }
        if (currColor !== this.lastAlertPlayerColor && this.gameState.turn_state !== "WAIT_ROLL") {
            this.lastAlertPlayerColor = null;
        }

        // Update Use Both Dice & Pass Turn Buttons
        this._updateUseBothDiceUI();
        if (this.btnPassTurn) {
            const canPass = this.isMyTurn && this.twoDiceMode && this.gameState.turn_state === "WAIT_MOVE" && this.gameState.used_dice && this.gameState.used_dice.length > 0;
            this.btnPassTurn.style.display = canPass ? "inline-flex" : "none";
        }

        // Update Player Side Cards
        this._updatePlayerCards();
        this._renderAllPlayerHudDice();
    }

    _updatePlayerCards() {
        if (!this.roomState) return;

        const currColor = this.gameState ? this.gameState.current_player : null;
        const activeColors = new Set(this.roomState.players.map(p => p.color));

        // Hide cards for inactive colors in 2, 3, 4, or 6 player games
        ["red", "green", "yellow", "blue", "orange", "purple", "cyan", "pink"].forEach(col => {
            const card = document.getElementById(`player-card-${col}`);
            if (card) {
                card.style.display = activeColors.has(col) ? "" : "none";
            }
        });

        this.roomState.players.forEach(p => {
            const card = document.getElementById(`player-card-${p.color}`);
            if (!card) return;

            card.className = `player-hud-card color-${p.color} ${p.color === currColor ? "active-turn" : ""}`;

            const nameEl = card.querySelector(".hud-name");
            if (nameEl) nameEl.innerText = p.name;

            const gp = this.gameState?.players?.find(g => g.color === p.color);
            const goalStep = this.gameState?.step_goal || 56;
            const goalCount = gp ? (gp.tokens_in_goal ?? (gp.tokens ? gp.tokens.filter(t => t.is_in_goal || t.step === goalStep).length : 0)) : 0;
            const goalEl = card.querySelector(".hud-goal-counter");
            if (goalEl) goalEl.innerText = `Goal: ${goalCount}/4`;

            // Individual Private Call Button visibility
            const callBtn = card.querySelector(".btn-private-call");
            if (callBtn) {
                const canCall = !p.is_bot && (p.color !== this.myColor) && (this.selectedMode === "online") && Boolean(p.session_id);
                callBtn.style.display = canCall ? "flex" : "none";
            }
        });
    }

    _updatePlayerSpeakingUI(color, isSpeaking, level) {
        const card = document.getElementById(`player-card-${color}`);
        if (!card) return;

        const avatarWrap = card.querySelector(".hud-avatar-wrap");
        if (avatarWrap) {
            if (isSpeaking) {
                avatarWrap.classList.add("speaking");
                avatarWrap.style.boxShadow = `0 0 ${10 + level * 25}px #00ff88`;
            } else {
                avatarWrap.classList.remove("speaking");
                avatarWrap.style.boxShadow = "none";
            }
        }
    }

    _updatePlayerAudioStateUI(color, state) {
        const card = document.getElementById(`player-card-${color}`);
        if (!card) return;

        const micIcon = card.querySelector(".hud-mic-indicator");
        if (micIcon) {
            micIcon.innerText = state.is_muted ? "🔇" : "🎙️";
            micIcon.style.opacity = state.is_muted ? "0.6" : "1.0";
        }
    }

    _updateMicButtonUI(isMuted) {
        if (this.btnMicToggle) {
            this.btnMicToggle.className = `voice-btn ${isMuted ? "muted" : "active"}`;
            this.btnMicToggle.innerHTML = isMuted ? "<span>🔇</span> Mic Off" : "<span>🎙️</span> Mic On";
        }
    }

    _updateDeafenButtonUI(isDeafened) {
        if (this.btnDeafenToggle) {
            this.btnDeafenToggle.className = `voice-btn ${isDeafened ? "deafened" : ""}`;
            this.btnDeafenToggle.innerHTML = isDeafened ? "<span>🔇</span> Deafened" : "<span>🎧</span> Audio";
        }
    }

    _stopMicLoopbackTest() {
        if (this.testAudioSource) {
            try { this.testAudioSource.disconnect(); } catch (e) {}
            this.testAudioSource = null;
        }
        if (this.testAudioGain) {
            try { this.testAudioGain.disconnect(); } catch (e) {}
            this.testAudioGain = null;
        }
        this.isTestingMicLoop = false;
        const btnTestLoop = document.getElementById("btn-test-mic");
        if (btnTestLoop) {
            btnTestLoop.innerText = "Test Microphone (Hear Yourself)";
        }
    }

    _copyFallback(text) {
        try {
            const temp = document.createElement("input");
            temp.value = text;
            document.body.appendChild(temp);
            temp.select();
            document.execCommand("copy");
            temp.remove();
            this._showToast(`Copied room code: ${text}`, "success");
        } catch (e) {
            this._showToast(`Room code: ${text}`, "info");
        }
    }

    _openAudioSettingsModal() {
        this.modalAudio.classList.add("open");

        // Mic loopback test setup
        const btnTestLoop = document.getElementById("btn-test-mic");

        if (btnTestLoop) {
            btnTestLoop.innerText = this.isTestingMicLoop ? "Stop Loopback Test" : "Test Microphone (Hear Yourself)";
            btnTestLoop.onclick = async () => {
                const audioSys = window.audioSystem;
                if (!audioSys.localStream) {
                    btnTestLoop.innerText = "Requesting Mic Access...";
                    const ok = await audioSys.joinCall(this.currentRoomId || "TEST-MIC", this.playerName, this.myColor);
                    if (!ok || !audioSys.localStream) {
                        btnTestLoop.innerText = "Test Microphone (Hear Yourself)";
                        this._showToast("Microphone access could not be acquired.", "warning");
                        return;
                    }
                }

                if (this.isTestingMicLoop) {
                    this._stopMicLoopbackTest();
                } else {
                    if (!audioSys.audioCtx || !audioSys.localStream) return;
                    try {
                        this.testAudioSource = audioSys.audioCtx.createMediaStreamSource(audioSys.localStream);
                        this.testAudioGain = audioSys.audioCtx.createGain();
                        this.testAudioGain.gain.value = 0.8;
                        this.testAudioSource.connect(this.testAudioGain);
                        this.testAudioGain.connect(audioSys.audioCtx.destination);
                        this.isTestingMicLoop = true;
                        btnTestLoop.innerText = "Stop Loopback Test";
                    } catch (err) {
                        console.warn("Loopback test error:", err);
                        this._stopMicLoopbackTest();
                    }
                }
            };
        }

        // PTT toggle checkbox
        const pttCheck = document.getElementById("audio-ptt-checkbox");
        if (pttCheck) {
            pttCheck.checked = window.audioSystem.isPushToTalk;
            pttCheck.onchange = (e) => {
                window.audioSystem.setPushToTalk(e.target.checked);
            };
        }

        // Master Voice Volume slider
        const volSlider = document.getElementById("master-voice-slider");
        if (volSlider) {
            volSlider.value = window.audioSystem.masterVolume * 100;
            volSlider.oninput = (e) => {
                window.audioSystem.setMasterVolume(e.target.value / 100);
            };
        }
    }

    _refreshAudioPeersList(peers) {
        const list = document.getElementById("audio-peers-list");
        if (!list) return;
        list.innerHTML = "";

        peers.forEach(peer => {
            const item = document.createElement("div");
            item.className = "peer-audio-row";
            item.innerHTML = `
                <div class="peer-info">
                    <span class="peer-dot color-${peer.color}"></span>
                    <span>${peer.player_name}</span>
                </div>
                <div class="peer-vol-wrap">
                    <span>Vol</span>
                    <input type="range" min="0" max="200" value="100" class="peer-vol-slider" data-sid="${peer.session_id}">
                </div>
            `;
            const slider = item.querySelector(".peer-vol-slider");
            slider.addEventListener("input", (e) => {
                window.audioSystem.setPeerVolume(peer.session_id, e.target.value / 100);
            });
            list.appendChild(item);
        });
    }

    _getColorBySessionId(sessionId) {
        if (sessionId === "local") return this.myColor;
        if (!this.roomState) return null;
        const player = this.roomState.players.find(p => p.session_id === sessionId);
        return player ? player.color : null;
    }

    _sendChatMessage() {
        const text = this.chatInput.value.trim();
        if (!text) return;
        this.chatInput.value = "";

        // Slash command processing (case-insensitive for mobile virtual keyboards)
        const lowerCmd = text.toLowerCase();
        if (lowerCmd.startsWith("/boost")) {
            const parts = text.split(" ");
            let targetState = !this.openOnOne;
            if (parts.length > 1) {
                const arg = parts[1].toLowerCase();
                if (arg === "off" || arg === "0" || arg === "false") targetState = false;
                else if (arg === "on" || arg === "1" || arg === "true") targetState = true;
            }
            this.openOnOne = targetState;
            localStorage.setItem("ludo_open_on_one", targetState);
            const btnFast = document.getElementById("btn-rule-fast");
            const btnClassic = document.getElementById("btn-rule-classic");
            const toggle = document.getElementById("setting-open-one-toggle");
            if (btnFast) btnFast.classList.toggle("active", targetState);
            if (btnClassic) btnClassic.classList.toggle("active", !targetState);
            if (toggle) toggle.checked = targetState;

            if (this.currentRoomId) {
                this.net.send({ type: "update_rules", open_on_one: targetState });
            }
            this._appendGameAnnouncement(`⚡ Fast Boost Rule (Open on 1 or 6) is now ${targetState ? "ENABLED" : "DISABLED"}`, "boost");
            return;
        }

        if (lowerCmd.startsWith("/teamwork") || lowerCmd.startsWith("/team")) {
            const parts = text.split(" ");
            let targetState = !this.teamMode;
            if (parts.length > 1) {
                const arg = parts[1].toLowerCase();
                if (arg === "off" || arg === "0" || arg === "false") targetState = false;
                else if (arg === "on" || arg === "1" || arg === "true") targetState = true;
            }
            this.teamMode = targetState;
            localStorage.setItem("ludo_team_mode", targetState ? "true" : "false");
            const teamToggle = document.getElementById("setting-team-mode-toggle");
            if (teamToggle) teamToggle.checked = targetState;
            document.querySelectorAll(".count-btn").forEach(b => b.classList.remove("active"));
            if (targetState) {
                const btnTeam = document.getElementById("btn-format-team");
                if (btnTeam) btnTeam.classList.add("active");
                this.selectedPlayerCount = 4;
            } else {
                const btn4 = document.querySelector('.count-btn[data-count="4"]');
                if (btn4) btn4.classList.add("active");
            }

            if (this.currentRoomId) {
                this.net.send({ type: "update_rules", team_mode: targetState });
            }
            this._appendGameAnnouncement(`🤝 2v2 Teamwork Mode [Preview] is now ${targetState ? "ENABLED (Red+Yellow vs Green+Blue)" : "DISABLED"}`, "team");
            return;
        }

        if (lowerCmd.startsWith("/dice") || lowerCmd.startsWith("/twodice")) {
            const parts = text.split(" ");
            let targetState = !this.twoDiceMode;
            if (parts.length > 1) {
                const arg = parts[1].toLowerCase();
                if (arg === "1" || arg === "single" || arg === "off" || arg === "false") targetState = false;
                else if (arg === "2" || arg === "double" || arg === "two" || arg === "on" || arg === "true") targetState = true;
            }
            this.twoDiceMode = targetState;
            localStorage.setItem("ludo_two_dice_mode", this.twoDiceMode ? "true" : "false");
            const btnDiceSingle = document.getElementById("btn-dice-single");
            const btnDiceDouble = document.getElementById("btn-dice-double");
            const settingTwoDiceToggle = document.getElementById("setting-twodice-toggle");
            if (btnDiceSingle) btnDiceSingle.classList.toggle("active", !this.twoDiceMode);
            if (btnDiceDouble) btnDiceDouble.classList.toggle("active", this.twoDiceMode);
            if (settingTwoDiceToggle) settingTwoDiceToggle.checked = this.twoDiceMode;
            if (this.dice) this.dice.setTwoDiceMode(this.twoDiceMode);

            if (this.currentRoomId && this.isHost) {
                this.net.send({ type: "update_rules", two_dice_mode: this.twoDiceMode });
            }
            this._appendGameAnnouncement(`🎲 Dice Mode set to ${targetState ? "2 DICE (Choose Die)" : "1 DIE (Standard)"}`, "normal");
            return;
        }

        if (lowerCmd === "/help") {
            this._appendGameAnnouncement("Commands: /boost [on/off], /teamwork [on/off], /dice [1/2], /help", "normal");
            return;
        }

        this.net.send({ type: "chat_message", text: text });
    }

    _appendChatMessage(sender, color, text) {
        if (!this.chatMessages) return;
        const msgEl = document.createElement("div");
        msgEl.className = "chat-item";
        msgEl.innerHTML = `
            <span class="chat-sender color-${color}">${sender}:</span>
            <span class="chat-text">${escapeHtml(text)}</span>
        `;
        this.chatMessages.appendChild(msgEl);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;

        function escapeHtml(str) {
            return str.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
        }
    }

    _appendGameAnnouncement(text, type = "normal") {
        if (!this.chatMessages) return;
        const msgEl = document.createElement("div");
        msgEl.className = `chat-item game-announcement game-${type}`;
        msgEl.innerHTML = `<span>${text}</span>`;
        this.chatMessages.appendChild(msgEl);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    _resetTurnTimer() {
        if (this.turnTimerInterval) {
            clearInterval(this.turnTimerInterval);
            this.turnTimerInterval = null;
        }
        if (!this.turnTimerBar) return;

        this.turnTimerBar.style.transition = "none";
        this.turnTimerBar.style.width = "100%";

        const duration = 20; // 20s turn time
        let remaining = duration;
        setTimeout(() => {
            if (this.turnTimerBar) {
                this.turnTimerBar.style.transition = `width ${duration}s linear`;
                this.turnTimerBar.style.width = "0%";
            }
        }, 30);

        this.turnTimerInterval = setInterval(() => {
            remaining -= 1;
            if (remaining <= 0) {
                clearInterval(this.turnTimerInterval);
                this.turnTimerInterval = null;
                // If it's my turn, perform automated action so match doesn't freeze
                if (this.isMyTurn && this.gameState) {
                    if (this.gameState.turn_state === "WAIT_ROLL") {
                        this.rollDice();
                    } else if (this.gameState.turn_state === "WAIT_MOVE" && this.gameState.valid_moves?.length > 0) {
                        this.moveToken(this.gameState.valid_moves[0]);
                    }
                }
            }
        }, 1000);
    }

    _spawnFloatingReaction(emoji, color) {
        if (!this.floatingReactionsContainer) return;

        const react = document.createElement("div");
        react.className = "floating-emoji";
        react.innerText = emoji;
        react.style.left = `${30 + Math.random() * 40}%`;
        react.style.bottom = "15%";

        this.floatingReactionsContainer.appendChild(react);
        setTimeout(() => react.remove(), 2500);
    }

    _showVictoryModal(winners) {
        if (!this.modalVictory) return;
        if (window.soundEngine) window.soundEngine.playVictory();

        const podium = document.getElementById("victory-podium");
        const modalHeader = this.modalVictory.querySelector("h2");
        if (modalHeader) {
            if (this.gameState && this.gameState.team_mode) {
                const isAlpha = (winners[0] === "red" || winners[0] === "yellow");
                modalHeader.innerText = isAlpha ? "🏆 TEAM ALPHA WINS! (🔴+🟡)" : "🏆 TEAM BRAVO WINS! (🟢+🔵)";
            } else {
                modalHeader.innerText = "🏆 Victory Championship Podium";
            }
        }

        if (podium) {
            podium.innerHTML = "";
            winners.forEach((color, idx) => {
                const player = this.roomState ? this.roomState.players.find(p => p.color === color) : null;
                const name = player ? player.name : color.toUpperCase();
                const col = document.createElement("div");
                col.className = `podium-rank rank-${idx + 1} color-${color}`;
                col.innerHTML = `
                    <div class="podium-crown">${idx === 0 ? "👑" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : "🎖️"}</div>
                    <div class="podium-name">${name}</div>
                    <div class="podium-pillar">#${idx + 1}</div>
                `;
                podium.appendChild(col);
            });
        }

        this.modalVictory.classList.add("open");

        const btnRematch = document.getElementById("btn-victory-rematch");
        if (btnRematch) {
            btnRematch.onclick = () => {
                this.modalVictory.classList.remove("open");
                this.net.send({ type: "rematch" });
            };
        }
    }

    applyTheme(themeName) {
        this.theme = themeName;
        localStorage.setItem("ludo_theme", themeName);
        document.body.className = `theme-${themeName}`;
        if (this.board) {
            this.board.setTheme(themeName);
        }
        document.querySelectorAll(".theme-option").forEach(opt => {
            opt.classList.toggle("selected", opt.dataset.theme === themeName);
        });
    }

    // --- Live Game Updates Stream (Left Corner) ---
    _appendGameUpdate(text, type = "normal") {

        if (!this.gameUpdatesEnabled || !this.gameUpdatesStream) return;
        const entry = document.createElement("div");
        entry.className = `update-entry ${type}`;
        const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        entry.innerHTML = `<span style="opacity: 0.6; font-size: 10px; margin-right: 4px;">[${time}]</span> ${text}`;
        this.gameUpdatesStream.appendChild(entry);

        // Cap updates stream to 50 items to keep memory clean
        while (this.gameUpdatesStream.children.length > 50) {
            this.gameUpdatesStream.removeChild(this.gameUpdatesStream.firstChild);
        }
        this.gameUpdatesStream.scrollTop = this.gameUpdatesStream.scrollHeight;
    }

    toggleGameUpdates() {
        this.setGameUpdatesEnabled(!this.gameUpdatesEnabled);
    }

    setGameUpdatesEnabled(enabled) {
        this.gameUpdatesEnabled = !!enabled;
        localStorage.setItem("ludo_game_updates", this.gameUpdatesEnabled ? "true" : "false");

        if (this.gameUpdatesCorner) {
            this.gameUpdatesCorner.classList.toggle("hidden", !this.gameUpdatesEnabled);
        }
        if (this.btnUpdatesToggleCorner) {
            this.btnUpdatesToggleCorner.innerText = this.gameUpdatesEnabled ? "ON" : "OFF";
            this.btnUpdatesToggleCorner.className = `updates-toggle-btn ${this.gameUpdatesEnabled ? "active" : "off"}`;
        }
        if (this.btnToggleUpdates) {
            this.btnToggleUpdates.style.opacity = this.gameUpdatesEnabled ? "1.0" : "0.5";
            this.btnToggleUpdates.title = this.gameUpdatesEnabled ? "Game Updates: ON (Click to disable)" : "Game Updates: OFF (Click to enable)";
        }
        if (this.settingGameUpdatesToggle) {
            this.settingGameUpdatesToggle.checked = this.gameUpdatesEnabled;
        }
    }

    // --- Board Size Presets ---
    applyBoardSize(size) {
        const validSizes = ["standard", "large", "xlarge"];
        const targetSize = validSizes.includes(size) ? size : "large";
        this.boardSize = targetSize;
        localStorage.setItem("ludo_board_size", targetSize);

        const container = document.querySelector(".canvas-container");
        if (container) {
            container.classList.remove("size-standard", "size-large", "size-xlarge");
            container.classList.add(`size-${targetSize}`);
        }

        document.querySelectorAll("#board-size-buttons .rule-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.size === targetSize);
        });

        if (this.board && typeof this.board.setSizePreset === "function") {
            this.board.setSizePreset(targetSize);
        }

        // Trigger canvas resize immediately and after transition completes
        setTimeout(() => {
            window.dispatchEvent(new Event("resize"));
        }, 50);
        setTimeout(() => {
            window.dispatchEvent(new Event("resize"));
        }, 320);
    }

    // --- Color Selection ---
    _updateVisibleColors(playerCount) {
        const count = playerCount || (this.roomState ? this.roomState.max_players : null) || this.selectedPlayerCount || 4;
        const validColors = count >= 8 ? ["red", "green", "yellow", "blue", "orange", "purple", "cyan", "pink"] :
                            count >= 6 ? ["red", "green", "yellow", "blue", "orange", "purple"] :
                            ["red", "green", "yellow", "blue"];

        document.querySelectorAll("#home-color-picker .color-select-btn, #lobby-color-picker .color-select-btn").forEach(btn => {
            const col = btn.dataset.color;
            btn.style.display = validColors.includes(col) ? "inline-flex" : "none";
        });

        if (!validColors.includes(this.myColor)) {
            this.myColor = "red";
        }
    }

    _syncColorPickerUI(color) {
        this.myColor = color || "red";
        this._updateVisibleColors(this.roomState ? (this.roomState.max_players || this.roomState.player_count) : this.selectedPlayerCount);
        document.querySelectorAll("#home-color-picker .color-select-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.color === this.myColor);
        });
        document.querySelectorAll("#lobby-color-picker .color-select-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.color === this.myColor);
        });
    }

    setColor(color) {
        if (!color) return;
        this.myColor = color;
        localStorage.setItem("ludo_preferred_color", color);
        this._syncColorPickerUI(color);
        this._showToast(`Preferred color set to ${color.toUpperCase()}`, "info");
    }

    changeLobbyColor(newColor) {
        if (!newColor) return;
        this.myColor = newColor;
        localStorage.setItem("ludo_preferred_color", newColor);
        this._syncColorPickerUI(newColor);
        if (this.currentRoomId && this.net && this.net.isOpen()) {
            this.net.send({ type: "change_color", color: newColor });
        }
    }

    // --- AI Difficulty Selection ---
    _syncDifficultyUI(diff) {
        this.difficulty = diff || "hard";
        document.querySelectorAll("#difficulty-buttons .rule-btn, #setting-difficulty-buttons .rule-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.diff === this.difficulty);
        });
        if (this.lobbyDiffText) {
            const label = this.difficulty === "easy" ? "🟢 Easy (Casual)" : this.difficulty === "medium" ? "🟡 Medium (Standard)" : "🔴 Hard (Master AI)";
            this.lobbyDiffText.innerText = label;
        }
    }

    setDifficulty(diff) {
        if (!["easy", "medium", "hard"].includes(diff)) return;
        this.difficulty = diff;
        localStorage.setItem("ludo_ai_difficulty", diff);
        this._syncDifficultyUI(diff);
        if (this.currentRoomId && this.isHost && this.net && this.net.isOpen()) {
            this.net.send({ type: "update_rules", difficulty: diff });
        }
        this._showToast(`AI Difficulty set to ${diff.toUpperCase()}`, "info");
    }

    // --- Voice Call Mode UI Sync ---
    _syncCallModeUI(mode) {
        if (this.btnCallModeConf) this.btnCallModeConf.classList.toggle("active", mode === "conference");
        if (this.btnCallModeIndiv) this.btnCallModeIndiv.classList.toggle("active", mode === "individual");
    }

    // --- 2-Dice Sum Move ---
    _updateUseBothDiceUI() {
        if (!this.btnUseBothDice) return;
        if (!this.twoDiceMode || !this.gameState || this.gameState.turn_state !== "WAIT_MOVE" || !this.isMyTurn || (this.gameState.remaining_dice && this.gameState.remaining_dice.length < 2) || (this.gameState.used_dice && this.gameState.used_dice.length > 0)) {
            this.btnUseBothDice.style.display = "none";
            this.btnUseBothDice.classList.remove("active");
            return;
        }

        const sumVal = this.gameState.dice_sum || (this.gameState.dice_values && this.gameState.dice_values.length >= 2 ? (this.gameState.dice_values[0] + this.gameState.dice_values[1]) : null);
        const validMovesSum = this.gameState.valid_moves_sum || [];

        if (sumVal && validMovesSum.length > 0) {
            this.btnUseBothDice.style.display = "inline-flex";
            if (this.diceSumVal) this.diceSumVal.innerText = sumVal;
            this.btnUseBothDice.disabled = false;
            this.btnUseBothDice.classList.toggle("active", this.gameState.selected_die === sumVal);
        } else {
            this.btnUseBothDice.style.display = "none";
            this.btnUseBothDice.classList.remove("active");
        }
    }

    useBothDiceSum() {
        if (!this.gameState || !this.isMyTurn) return;
        const sumVal = this.gameState.dice_sum || (this.gameState.dice_values && this.gameState.dice_values.length >= 2 ? (this.gameState.dice_values[0] + this.gameState.dice_values[1]) : null);
        if (!sumVal) return;

        this.gameState.selected_die = sumVal;
        if (this.btnUseBothDice) {
            this.btnUseBothDice.classList.add("active");
        }

        // Select the sum die value
        this.selectDie(sumVal);

        const validMovesSum = this.gameState.valid_moves_sum || [];
        if (validMovesSum.length === 1) {
            // Auto move if single choice
            setTimeout(() => {
                this.moveToken(validMovesSum[0]);
            }, 180);
        } else if (validMovesSum.length > 0) {
            this.board.updateState(this.gameState, validMovesSum);
            this._showToast(`Move with combined sum ${sumVal}: Click a highlighted token!`, "info");
        }
    }

    // --- Personal Dice Rendering ---
    _renderAllPlayerHudDice() {
        if (!this.roomState) return;
        const currColor = this.gameState?.current_player;
        const turnState = this.gameState?.turn_state;

        this.roomState.players.forEach(p => {
            const isTurn = (p.color === currColor);
            const isWaitingRoll = isTurn && (turnState === "WAIT_ROLL");
            const cachedValues = this.personalDiceState[p.color] || null;

            this._updatePlayerHudDice(p.color, cachedValues, isWaitingRoll);
        });
    }

    _updatePlayerHudDice(color, diceValues, isRolling = false) {
        const diceWrap = document.getElementById(`player-dice-${color}`);
        if (!diceWrap) return;

        if (diceValues && Array.isArray(diceValues)) {
            this.personalDiceState[color] = diceValues;
        }

        diceWrap.innerHTML = "";
        const dieCount = this.twoDiceMode ? 2 : 1;

        if (isRolling) {
            for (let i = 0; i < dieCount; i++) {
                const rollEl = document.createElement("span");
                rollEl.className = "hud-mini-die";
                rollEl.innerHTML = "🎲";
                rollEl.title = "Rolling dice...";
                diceWrap.appendChild(rollEl);
            }
            return;
        }

        const values = diceValues || this.personalDiceState[color] || [];
        if (values.length === 0) {
            for (let i = 0; i < dieCount; i++) {
                const emptyEl = document.createElement("span");
                emptyEl.className = "hud-mini-die";
                emptyEl.style.opacity = "0.35";
                emptyEl.innerText = "-";
                diceWrap.appendChild(emptyEl);
            }
            return;
        }

        values.forEach(v => {
            const dieEl = document.createElement("span");
            dieEl.className = `hud-mini-die val-${v}`;
            dieEl.innerText = v;
            diceWrap.appendChild(dieEl);
        });
    }

    // --- Prominent Center Turn Announcements ---
    _showCenterTurnAlert(message, type = "normal", playerColor = null) {
        if (!this.turnBanner || !this.turnText) return;
        const col = playerColor || this.gameState?.current_player || this.myColor;
        this.turnBanner.className = `turn-banner color-${col} center-turn-banner bonus-pulse my-turn-pulse`;

        if (this.turnIcon) {
            if (type === "capture") this.turnIcon.innerText = "⚔️";
            else if (type === "goal") this.turnIcon.innerText = "👑";
            else if (type === "boost") this.turnIcon.innerText = "⚡";
            else this.turnIcon.innerText = "🎲";
        }
        this.turnText.innerText = message;

        setTimeout(() => {
            if (this.turnBanner) {
                this.turnBanner.classList.remove("bonus-pulse");
            }
        }, 2200);
    }

    // --- Clean Quit & State Reset ---
    quitCurrentGame() {
        if (this.net && this.net.isOpen() && this.currentRoomId) {
            this.net.send({ type: "quit_game" });
        }
        if (window.audioSystem) {
            window.audioSystem.leaveCall();
        }
        this._resetGameToHome();
        this._showToast("You left the game. An AI bot has taken over your seat.", "info");
    }

    _resetGameToHome() {
        if (this.turnTimerInterval) {
            clearInterval(this.turnTimerInterval);
            this.turnTimerInterval = null;
        }
        this.currentRoomId = null;
        this.roomState = null;
        this.gameState = null;
        this.isMyTurn = false;
        this.pendingCallerSid = null;
        this.personalDiceState = {};

        if (this.btnQuitGame) this.btnQuitGame.style.display = "none";
        if (this.privateCallBanner) this.privateCallBanner.style.display = "none";
        if (this.btnUseBothDice) this.btnUseBothDice.style.display = "none";
        if (this.modalQuit) this.modalQuit.classList.remove("open");
        if (this.modalIncomingCall) this.modalIncomingCall.classList.remove("open");
        if (this.modalVictory) this.modalVictory.classList.remove("open");
        this._stopMicLoopbackTest();

        this._switchScreen("screen-home");
    }

    _getAvatarEmoji(avatar) {
        const map = {
            lion: "🦁", fox: "🦊", bear: "🐻", dragon: "🐲",
            alien: "👽", robot: "🤖", tiger: "🐯", wolf: "🐺",
            eagle: "🦅", phoenix: "🦩", default: "👑"
        };
        return map[avatar] || "👑";
    }

    _showToast(msg, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerText = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add("show"), 20);
        setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 400);
        }, 3000);
    }
}

window.addEventListener("DOMContentLoaded", () => {
    window.app = new LudoApp();
});
