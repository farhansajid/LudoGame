/**
 * Ludo Board Canvas Renderer & Animation Engine
 * Supports 4-Player (Classic), 6-Player (Hexagonal), and 8-Player (Octagonal) matches.
 * Delivers:
 * - High-DPI crisp retina rendering with automatic resizing
 * - 3 Luxury Themes (Mahogany Wood & Brass, Cyber Neon Glow, Emerald Marble)
 * - 3D token styling with specular gleams and stacking physics
 * - Parabolic hopping physics animations for token movement
 * - High-impact particle systems:
 *   1. Capturing opponent pieces (intense fiery knockout blast & shockwaves)
 *   2. Reaching the goal (grand confetti celebration & golden starbursts)
 *   3. Releasing pieces on 6 (fiery/golden power surge & radial energy rays)
 *   4. Escaping danger (emerald & cyan protective shield barrier wave & wind trails)
 */

class LudoBoard {
    constructor(canvasElement, onTokenClick) {
        this.canvas = canvasElement;
        this.ctx = this.canvas.getContext("2d");
        this.onTokenClick = onTokenClick;

        this.theme = "wood"; // "wood", "cyber", "emerald"
        this.boardSize = 750; // virtual resolution
        this.cellSize = this.boardSize / 15;
        this.boardType = 4; // 4, 6, or 8

        // Current game state
        this.gameState = null;
        this.validMoves = [];
        this.animatingToken = null; // Currently hopping token
        this.activeParticles = [];
        this.hoveredToken = null;

        // Board geometry properties
        this.trackLength = 52;
        this.stepTrackMax = 50;
        this.stepHomeStart = 51;
        this.stepGoal = 56;
        this.startOffsets = { red: 0, green: 13, yellow: 26, blue: 39 };
        this.safeIndices = new Set([0, 8, 13, 21, 26, 34, 39, 47]);

        // Coordinates maps: indexed by global index or color
        this.trackCoords = [];
        this.homeRunCoords = {};
        this.yardCoords = {};

        this._initCoordinates(4);
        this._setupResize();
        this._setupInteraction();
        this._startRenderLoop();
    }

    setTheme(themeName) {
        this.theme = themeName;
    }

    _initCoordinates(boardType = 4) {
        this.boardType = boardType;

        if (boardType === 6) {
            this._initCoordinates6();
        } else if (boardType === 8) {
            this._initCoordinates8();
        } else {
            this._initCoordinates4();
        }
    }

    // --- 4-Player Classic Board Coordinates (15x15 Grid) ---
    _initCoordinates4() {
        this.trackLength = 52;
        this.stepTrackMax = 50;
        this.stepHomeStart = 51;
        this.stepGoal = 56;
        this.startOffsets = { red: 0, green: 13, yellow: 26, blue: 39 };
        this.safeIndices = new Set([0, 8, 13, 21, 26, 34, 39, 47]);

        const cs = this.cellSize;

        const gridTrack = [
            // Red horizontal arm
            { r: 6, c: 1 }, { r: 6, c: 2 }, { r: 6, c: 3 }, { r: 6, c: 4 }, { r: 6, c: 5 },
            // Green vertical arm
            { r: 5, c: 6 }, { r: 4, c: 6 }, { r: 3, c: 6 }, { r: 2, c: 6 }, { r: 1, c: 6 }, { r: 0, c: 6 },
            { r: 0, c: 7 },
            { r: 0, c: 8 }, { r: 1, c: 8 }, { r: 2, c: 8 }, { r: 3, c: 8 }, { r: 4, c: 8 }, { r: 5, c: 8 },
            // Yellow horizontal arm
            { r: 6, c: 9 }, { r: 6, c: 10 }, { r: 6, c: 11 }, { r: 6, c: 12 }, { r: 6, c: 13 }, { r: 6, c: 14 },
            { r: 7, c: 14 },
            { r: 8, c: 14 }, { r: 8, c: 13 }, { r: 8, c: 12 }, { r: 8, c: 11 }, { r: 8, c: 10 }, { r: 8, c: 9 },
            // Blue vertical arm
            { r: 9, c: 8 }, { r: 10, c: 8 }, { r: 11, c: 8 }, { r: 12, c: 8 }, { r: 13, c: 8 }, { r: 14, c: 8 },
            { r: 14, c: 7 },
            { r: 14, c: 6 }, { r: 13, c: 6 }, { r: 12, c: 6 }, { r: 11, c: 6 }, { r: 10, c: 6 }, { r: 9, c: 6 },
            // Return to Red arm
            { r: 8, c: 5 }, { r: 8, c: 4 }, { r: 8, c: 3 }, { r: 8, c: 2 }, { r: 8, c: 1 }, { r: 8, c: 0 },
            { r: 7, c: 0 },
            { r: 6, c: 0 }
        ];

        this.trackCoords = gridTrack.map(g => ({
            x: (g.c + 0.5) * cs,
            y: (g.r + 0.5) * cs,
            r: g.r,
            c: g.c
        }));

        const gridHome = {
            red: [{ r: 7, c: 1 }, { r: 7, c: 2 }, { r: 7, c: 3 }, { r: 7, c: 4 }, { r: 7, c: 5 }, { r: 7, c: 6.2 }],
            green: [{ r: 1, c: 7 }, { r: 2, c: 7 }, { r: 3, c: 7 }, { r: 4, c: 7 }, { r: 5, c: 7 }, { r: 6.2, c: 7 }],
            yellow: [{ r: 7, c: 13 }, { r: 7, c: 12 }, { r: 7, c: 11 }, { r: 7, c: 10 }, { r: 7, c: 9 }, { r: 7, c: 7.8 }],
            blue: [{ r: 13, c: 7 }, { r: 12, c: 7 }, { r: 11, c: 7 }, { r: 10, c: 7 }, { r: 9, c: 7 }, { r: 7.8, c: 7 }]
        };

        this.homeRunCoords = {};
        for (const col of Object.keys(gridHome)) {
            this.homeRunCoords[col] = gridHome[col].map(g => ({
                x: (g.c + 0.5) * cs,
                y: (g.r + 0.5) * cs,
                r: g.r,
                c: g.c
            }));
        }

        const gridYards = {
            red: [{ r: 2, c: 2 }, { r: 2, c: 3.5 }, { r: 3.5, c: 2 }, { r: 3.5, c: 3.5 }],
            green: [{ r: 2, c: 11 }, { r: 2, c: 12.5 }, { r: 3.5, c: 11 }, { r: 3.5, c: 12.5 }],
            yellow: [{ r: 11, c: 11 }, { r: 11, c: 12.5 }, { r: 12.5, c: 11 }, { r: 12.5, c: 12.5 }],
            blue: [{ r: 11, c: 2 }, { r: 11, c: 3.5 }, { r: 12.5, c: 2 }, { r: 12.5, c: 3.5 }]
        };

        this.yardCoords = {};
        for (const col of Object.keys(gridYards)) {
            this.yardCoords[col] = gridYards[col].map(g => ({
                x: (g.c + 0.5) * cs,
                y: (g.r + 0.5) * cs,
                r: g.r,
                c: g.c
            }));
        }
    }

    // --- 6-Player Hexagonal Board Coordinates ---
    _initCoordinates6() {
        this.trackLength = 78;
        this.stepTrackMax = 76;
        this.stepHomeStart = 77;
        this.stepGoal = 82;

        const colors6 = ["red", "green", "yellow", "blue", "orange", "purple"];
        this.startOffsets = {};
        this.safeIndices = new Set();
        colors6.forEach((c, i) => {
            const start = i * 13;
            this.startOffsets[c] = start;
            this.safeIndices.add(start);
            this.safeIndices.add((start + 8) % 78);
        });

        const cx = 375;
        const cy = 375;
        const R_goal = 50;
        const R_tip = 240;
        const R_valley = 110;

        this.trackCoords = new Array(78);
        this.homeRunCoords = {};
        this.yardCoords = {};

        for (let k = 0; k < 6; k++) {
            const theta = (k * 2 * Math.PI) / 6 - Math.PI / 2;
            const nextTheta = ((k + 1) * 2 * Math.PI) / 6 - Math.PI / 2;
            const valleyTheta = theta + (Math.PI / 6);
            const baseIdx = k * 13;

            const tipX = cx + Math.cos(theta) * R_tip;
            const tipY = cy + Math.sin(theta) * R_tip;

            const valX = cx + Math.cos(valleyTheta) * R_valley;
            const valY = cy + Math.sin(valleyTheta) * R_valley;

            const nextTipX = cx + Math.cos(nextTheta) * R_tip;
            const nextTipY = cy + Math.sin(nextTheta) * R_tip;

            // Right edge of arm k: from near tip to valley (tiles 0..5)
            for (let i = 0; i < 6; i++) {
                const frac = (i + 0.6) / 6.5;
                this.trackCoords[baseIdx + i] = {
                    x: tipX + (valX - tipX) * frac,
                    y: tipY + (valY - tipY) * frac
                };
            }

            // Valley tile: tile 6
            this.trackCoords[baseIdx + 6] = {
                x: valX,
                y: valY
            };

            // Left edge of arm k+1: from valley to near next tip (tiles 7..12)
            for (let i = 0; i < 6; i++) {
                const frac = (i + 0.7) / 6.5;
                this.trackCoords[baseIdx + 7 + i] = {
                    x: valX + (nextTipX - valX) * frac,
                    y: valY + (nextTipY - valY) * frac
                };
            }

            // Home run for player k: from tip straight down to center goal (5 steps + goal)
            const col = colors6[k];
            this.homeRunCoords[col] = [];
            for (let h = 0; h < 5; h++) {
                const dist = R_tip - (h + 1) * ((R_tip - R_goal) / 6.0);
                this.homeRunCoords[col].push({
                    x: cx + Math.cos(theta) * dist,
                    y: cy + Math.sin(theta) * dist
                });
            }
            // Goal at center entrance
            this.homeRunCoords[col].push({
                x: cx + Math.cos(theta) * (R_goal * 0.45),
                y: cy + Math.sin(theta) * (R_goal * 0.45)
            });

            // 6 Yards nestled outside each valley
            const yardAngle = valleyTheta;
            const yardR = 295;
            const yx = cx + Math.cos(yardAngle) * yardR;
            const yy = cy + Math.sin(yardAngle) * yardR;
            const slotOff = 16;
            this.yardCoords[col] = [
                { x: yx - slotOff, y: yy - slotOff },
                { x: yx + slotOff, y: yy - slotOff },
                { x: yx - slotOff, y: yy + slotOff },
                { x: yx + slotOff, y: yy + slotOff }
            ];
        }
    }

    // --- 8-Player Octagonal Board Coordinates ---
    _initCoordinates8() {
        this.trackLength = 104;
        this.stepTrackMax = 102;
        this.stepHomeStart = 103;
        this.stepGoal = 108;

        const colors8 = ["red", "green", "yellow", "blue", "orange", "purple", "cyan", "pink"];
        this.startOffsets = {};
        this.safeIndices = new Set();
        colors8.forEach((c, i) => {
            const start = i * 13;
            this.startOffsets[c] = start;
            this.safeIndices.add(start);
            this.safeIndices.add((start + 8) % 104);
        });

        const cx = 375;
        const cy = 375;
        const R_goal = 44;
        const R_tip = 250;
        const R_valley = 125;

        this.trackCoords = new Array(104);
        this.homeRunCoords = {};
        this.yardCoords = {};

        for (let k = 0; k < 8; k++) {
            const theta = (k * 2 * Math.PI) / 8 - Math.PI / 2;
            const nextTheta = ((k + 1) * 2 * Math.PI) / 8 - Math.PI / 2;
            const valleyTheta = theta + (Math.PI / 8);
            const baseIdx = k * 13;

            const tipX = cx + Math.cos(theta) * R_tip;
            const tipY = cy + Math.sin(theta) * R_tip;

            const valX = cx + Math.cos(valleyTheta) * R_valley;
            const valY = cy + Math.sin(valleyTheta) * R_valley;

            const nextTipX = cx + Math.cos(nextTheta) * R_tip;
            const nextTipY = cy + Math.sin(nextTheta) * R_tip;

            for (let i = 0; i < 6; i++) {
                const frac = (i + 0.6) / 6.5;
                this.trackCoords[baseIdx + i] = {
                    x: tipX + (valX - tipX) * frac,
                    y: tipY + (valY - tipY) * frac
                };
            }

            this.trackCoords[baseIdx + 6] = {
                x: valX,
                y: valY
            };

            for (let i = 0; i < 6; i++) {
                const frac = (i + 0.7) / 6.5;
                this.trackCoords[baseIdx + 7 + i] = {
                    x: valX + (nextTipX - valX) * frac,
                    y: valY + (nextTipY - valY) * frac
                };
            }

            const col = colors8[k];
            this.homeRunCoords[col] = [];
            for (let h = 0; h < 5; h++) {
                const dist = R_tip - (h + 1) * ((R_tip - R_goal) / 6.0);
                this.homeRunCoords[col].push({
                    x: cx + Math.cos(theta) * dist,
                    y: cy + Math.sin(theta) * dist
                });
            }
            this.homeRunCoords[col].push({
                x: cx + Math.cos(theta) * (R_goal * 0.45),
                y: cy + Math.sin(theta) * (R_goal * 0.45)
            });

            // 8 Yards nestled outside each valley
            const yardAngle = valleyTheta;
            const yardR = 300;
            const yx = cx + Math.cos(yardAngle) * yardR;
            const yy = cy + Math.sin(yardAngle) * yardR;
            const slotOff = 15;
            this.yardCoords[col] = [
                { x: yx - slotOff, y: yy - slotOff },
                { x: yx + slotOff, y: yy - slotOff },
                { x: yx - slotOff, y: yy + slotOff },
                { x: yx + slotOff, y: yy + slotOff }
            ];
        }
    }

    _setupResize() {
        const resize = () => {
            const rect = this.canvas.parentElement.getBoundingClientRect();
            const minDim = Math.min(rect.width, rect.height) || 600;
            const dpr = window.devicePixelRatio || 1;

            this.canvas.width = minDim * dpr;
            this.canvas.height = minDim * dpr;
            this.canvas.style.width = `${minDim}px`;
            this.canvas.style.height = `${minDim}px`;

            this.scale = (minDim * dpr) / this.boardSize;
            this.ctx.setTransform(this.scale, 0, 0, this.scale, 0, 0);
        };

        window.addEventListener("resize", resize);
        setTimeout(resize, 50);
    }

    _setupInteraction() {
        const getBoardPos = (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const w = rect.width || this.canvas.clientWidth || 1;
            const h = rect.height || this.canvas.clientHeight || 1;
            const hasTouch = Boolean(e.touches && e.touches.length > 0);
            const clientX = hasTouch ? e.touches[0].clientX : (e.clientX !== undefined ? e.clientX : 0);
            const clientY = hasTouch ? e.touches[0].clientY : (e.clientY !== undefined ? e.clientY : 0);
            const x = ((clientX - rect.left) / w) * this.boardSize;
            const y = ((clientY - rect.top) / h) * this.boardSize;
            return { x, y };
        };

        this.canvas.addEventListener("mousemove", (e) => {
            const pos = getBoardPos(e);
            this._checkHover(pos.x, pos.y);
        });

        this.canvas.addEventListener("click", (e) => {
            const now = performance.now();
            if (this._lastTouchTime && (now - this._lastTouchTime) < 500) return;
            const pos = getBoardPos(e);
            this._handleClick(pos.x, pos.y);
        });

        this.canvas.addEventListener("touchstart", (e) => {
            this._lastTouchTime = performance.now();
            const pos = getBoardPos(e);
            this._handleClick(pos.x, pos.y);
        }, { passive: true });
    }

    _checkHover(x, y) {
        if (!this.gameState || !this.validMoves || this.validMoves.length === 0) {
            this.canvas.style.cursor = "default";
            this.hoveredToken = null;
            return;
        }

        const currPlayer = this.gameState.players[this.gameState.current_player_index];
        if (!currPlayer) return;

        let movingPlayer = currPlayer;
        if (this.gameState.team_mode && (currPlayer.has_won || currPlayer.tokens.every(t => t.step === this.stepGoal || t.is_in_goal))) {
            const partnerColor = { red: "yellow", yellow: "red", green: "blue", blue: "green" }[currPlayer.color];
            movingPlayer = this.gameState.players.find(p => p.color === partnerColor) || currPlayer;
        }

        let found = null;
        const hitRadius = this.boardType > 4 ? 22 : this.cellSize * 0.48;

        for (const tokenId of this.validMoves) {
            const token = movingPlayer.tokens[tokenId];
            if (!token) continue;
            const coord = this.getTokenPixelPos(token);
            const dist = Math.hypot(coord.x - x, coord.y - y);
            if (dist <= hitRadius) {
                found = tokenId;
                break;
            }
        }

        this.hoveredToken = found;
        this.canvas.style.cursor = found !== null ? "pointer" : "default";
    }

    _handleClick(x, y) {
        const now = performance.now();
        this._lastClickTime = now;
        if (this.animatingToken) return;
        if (!this.gameState || !this.validMoves || this.validMoves.length === 0) return;

        const currPlayer = this.gameState.players[this.gameState.current_player_index];
        if (!currPlayer) return;

        let movingPlayer = currPlayer;
        if (this.gameState.team_mode && (currPlayer.has_won || currPlayer.tokens.every(t => t.step === this.stepGoal || t.is_in_goal))) {
            const partnerColor = { red: "yellow", yellow: "red", green: "blue", blue: "green" }[currPlayer.color];
            movingPlayer = this.gameState.players.find(p => p.color === partnerColor) || currPlayer;
        }

        const hitRadius = this.boardType > 4 ? 24 : this.cellSize * 0.52;

        for (const tokenId of this.validMoves) {
            const token = movingPlayer.tokens[tokenId];
            if (!token) continue;
            const coord = this.getTokenPixelPos(token);
            const dist = Math.hypot(coord.x - x, coord.y - y);
            if (dist <= hitRadius) {
                if (this.onTokenClick) {
                    this.onTokenClick(tokenId);
                }
                break;
            }
        }
    }

    updateState(gameState, validMoves = []) {
        this.gameState = gameState;
        this.validMoves = validMoves;

        const bType = gameState.board_type || (gameState.players && gameState.players.length > 4 ? gameState.players.length : 4);
        if (bType !== this.boardType) {
            this._initCoordinates(bType);
        }
    }

    getTokenPixelPos(token) {
        const color = token.color;
        const step = token.step;

        if (step === -1) {
            // In Yard
            const slots = this.yardCoords[color] || [];
            const slot = slots[token.id] || { x: 375, y: 375 };
            return { x: slot.x, y: slot.y };
        } else if (step <= this.stepTrackMax) {
            // Perimeter track
            const startOffset = this.startOffsets[color] !== undefined ? this.startOffsets[color] : 0;
            const globalIdx = (startOffset + step) % this.trackLength;
            const tile = this.trackCoords[globalIdx] || { x: 375, y: 375 };
            return { x: tile.x, y: tile.y };
        } else {
            // Home run / Goal
            const hrIdx = Math.min(Math.max(0, step - this.stepHomeStart), 5);
            const list = this.homeRunCoords[color] || [];
            const tile = list[hrIdx] || { x: 375, y: 375 };
            return { x: tile.x, y: tile.y };
        }
    }

    // --- Piece Movement Hopping Animation ---
    animateTokenMove(playerColor, tokenId, fromStep, toStep, captures, onComplete, escapedDanger = false, diceValue = null) {
        const pathPoints = [];

        if (fromStep === -1 && toStep === 0) {
            pathPoints.push(this.getTokenPixelPos({ color: playerColor, id: tokenId, step: -1 }));
            pathPoints.push(this.getTokenPixelPos({ color: playerColor, id: tokenId, step: 0 }));
        } else {
            for (let s = fromStep; s <= toStep; s++) {
                pathPoints.push(this.getTokenPixelPos({ color: playerColor, id: tokenId, step: s }));
            }
        }

        let currentHop = 0;
        const totalHops = pathPoints.length - 1;
        const hopDuration = 120; // ms per square hop
        let hopStartTime = performance.now();

        const tokenObj = {
            color: playerColor,
            id: tokenId,
            x: pathPoints[0].x,
            y: pathPoints[0].y,
            scale: 1.0,
            hopOffset: 0
        };

        this.animatingToken = tokenObj;

        const animateHop = (now) => {
            const elapsed = now - hopStartTime;
            const progress = Math.min(1.0, elapsed / hopDuration);

            const p0 = pathPoints[currentHop];
            const p1 = pathPoints[currentHop + 1] || p0;

            tokenObj.x = p0.x + (p1.x - p0.x) * progress;
            tokenObj.y = p0.y + (p1.y - p0.y) * progress;

            const arcHeight = (this.boardType > 4 ? 14 : this.cellSize * 0.42);
            tokenObj.hopOffset = Math.sin(progress * Math.PI) * arcHeight;
            tokenObj.scale = 1.0 + Math.sin(progress * Math.PI) * 0.22;

            if (progress >= 1.0) {
                currentHop++;
                if (window.soundEngine) {
                    window.soundEngine.playPawnHop(currentHop);
                }
                this._spawnHopPuff(tokenObj.x, tokenObj.y, playerColor);

                if (currentHop < totalHops) {
                    hopStartTime = performance.now();
                    requestAnimationFrame(animateHop);
                } else {
                    // Completed move!
                    this.animatingToken = null;

                    // 1. Released from Yard
                    if (fromStep === -1 && toStep === 0) {
                        const dice = diceValue || (this.gameState ? (this.gameState.selected_die || this.gameState.dice_value) : null);
                        const isBoost = (dice === 1);
                        if (dice === 6 || !isBoost) {
                            if (window.soundEngine && window.soundEngine.playSixRelease) {
                                window.soundEngine.playSixRelease();
                            }
                            this._spawnSixReleaseBurst(tokenObj.x, tokenObj.y, playerColor);
                        } else {
                            if (window.soundEngine && window.soundEngine.playTokenRelease) {
                                window.soundEngine.playTokenRelease(true);
                            }
                            this._spawnReleaseBurst(tokenObj.x, tokenObj.y, playerColor, true);
                        }
                    }

                    // 2. Safe star square landing
                    const startOff = this.startOffsets[playerColor] || 0;
                    const finalGlobal = (startOff + toStep) % this.trackLength;
                    if (toStep <= this.stepTrackMax && this.safeIndices.has(finalGlobal)) {
                        if (window.soundEngine) window.soundEngine.playSafeSquare();
                        this._spawnStarSparkles(tokenObj.x, tokenObj.y);
                    }

                    // 3. Goal reached celebration
                    if (toStep === this.stepGoal) {
                        if (window.soundEngine) window.soundEngine.playGoalReached();
                        this._spawnGoalCelebration(tokenObj.x, tokenObj.y, playerColor);
                    }

                    // 4. Knockout capture explosion
                    if (captures && captures.length > 0) {
                        if (window.soundEngine) window.soundEngine.playCapture();
                        const victimColor = captures[0].player || "gray";
                        this._spawnCaptureExplosion(tokenObj.x, tokenObj.y, playerColor, victimColor);
                    }

                    // 5. Escaping danger
                    if (escapedDanger) {
                        if (window.soundEngine && window.soundEngine.playEscapeDanger) {
                            window.soundEngine.playEscapeDanger();
                        }
                        this._spawnEscapeDangerEffect(tokenObj.x, tokenObj.y, playerColor);
                    }

                    if (onComplete) onComplete();
                }
            } else {
                requestAnimationFrame(animateHop);
            }
        };

        requestAnimationFrame(animateHop);
    }

    // --- Particle Animation Systems ---

    // 1. Capturing Opponent Piece: Fiery Knockout Blast
    _spawnCaptureExplosion(x, y, attackerColor, victimColor) {
        this.activeParticles.push({
            type: "shockwave",
            x: x, y: y,
            radius: 6,
            maxRadius: 60,
            color: "#ff3366",
            life: 1.0,
            decay: 0.035
        });
        this.activeParticles.push({
            type: "shockwave",
            x: x, y: y,
            radius: 3,
            maxRadius: 40,
            color: "#ffd700",
            life: 1.0,
            decay: 0.05
        });

        const sparkColors = ["#ff3366", "#ff9900", "#ffd700", "#ffffff"];
        for (let i = 0; i < 30; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 2.5 + Math.random() * 6.0;
            this.activeParticles.push({
                type: "blast_spark",
                x: x, y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: 2.5 + Math.random() * 3,
                color: sparkColors[Math.floor(Math.random() * sparkColors.length)],
                life: 1.0,
                decay: 0.028
            });
        }

        this._spawnHopPuff(x, y, attackerColor);

        this.activeParticles.push({
            type: "text",
            text: "⚔️ KNOCKOUT!",
            x: x,
            y: y - 18,
            vy: -0.9,
            color: "#ff3366",
            life: 1.0,
            decay: 0.018
        });
    }

    // 2. Reaching the Goal: Grand Confetti Celebration & Golden Halo
    _spawnGoalCelebration(x, y, playerColor) {
        this.activeParticles.push({
            type: "shockwave",
            x: x, y: y,
            radius: 8,
            maxRadius: 70,
            color: "#ffd700",
            life: 1.0,
            decay: 0.022
        });

        this._spawnConfetti(x, y);
        this._spawnStarSparkles(x, y);

        this.activeParticles.push({
            type: "text",
            text: "👑 GOAL!",
            x: x,
            y: y - 20,
            vy: -0.85,
            color: "#ffd700",
            life: 1.0,
            decay: 0.015
        });
    }

    // 3. Releasing Pieces on 6: Power Surge & Radial Energy Rays
    _spawnSixReleaseBurst(x, y, playerColor) {
        this.activeParticles.push({
            type: "shockwave",
            x: x, y: y,
            radius: 6,
            maxRadius: 50,
            color: "#ffcc00",
            life: 1.0,
            decay: 0.035
        });

        for (let i = 0; i < 24; i++) {
            const angle = (i / 24) * Math.PI * 2 + (Math.random() * 0.15);
            const speed = 2.2 + Math.random() * 4.2;
            this.activeParticles.push({
                type: "sparkle",
                x: x, y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: 2.8 + Math.random() * 2.5,
                color: Math.random() > 0.4 ? "#FFD700" : "#FF6600",
                life: 1.0,
                decay: 0.03
            });
        }

        this.activeParticles.push({
            type: "text",
            text: "🔥 6 RELEASE!",
            x: x,
            y: y - 16,
            vy: -0.9,
            color: "#ffaa00",
            life: 1.0,
            decay: 0.02
        });
    }

    // 4. Escaping Danger: Protective Shield Barrier Wave & Speed Trails
    _spawnEscapeDangerEffect(x, y, playerColor) {
        this.activeParticles.push({
            type: "shield_ripple",
            x: x, y: y,
            radius: 6,
            maxRadius: 52,
            color: "#00ff88",
            life: 1.0,
            decay: 0.03
        });

        for (let i = 0; i < 18; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 2.0 + Math.random() * 4.5;
            this.activeParticles.push({
                type: "speed_trail",
                x: x, y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                length: 8 + Math.random() * 10,
                color: Math.random() > 0.5 ? "#00ff88" : "#00f0ff",
                life: 1.0,
                decay: 0.035
            });
        }

        this.activeParticles.push({
            type: "text",
            text: "🛡️ ESCAPED!",
            x: x,
            y: y - 16,
            vy: -0.9,
            color: "#00f0ff",
            life: 1.0,
            decay: 0.018
        });
    }

    _spawnReleaseBurst(x, y, color, isBoost) {
        this._spawnStarSparkles(x, y);
        this.activeParticles.push({
            type: "shockwave",
            x: x, y: y,
            radius: 5,
            maxRadius: 40,
            color: isBoost ? "#00f0ff" : "#ffd700",
            life: 1.0,
            decay: 0.04
        });
        this.activeParticles.push({
            type: "text",
            text: isBoost ? "⚡ BOOST!" : "👑 OPEN!",
            x: x,
            y: y - 14,
            vy: -0.9,
            color: isBoost ? "#00f0ff" : "#ffd700",
            life: 1.0,
            decay: 0.02
        });
    }

    _spawnHopPuff(x, y, color) {
        for (let i = 0; i < 4; i++) {
            this.activeParticles.push({
                type: "puff",
                x: x + (Math.random() - 0.5) * 8,
                y: y + 4 + (Math.random() - 0.5) * 4,
                vx: (Math.random() - 0.5) * 1.5,
                vy: (Math.random() - 0.5) * 1.5,
                radius: 3 + Math.random() * 3,
                color: "rgba(255, 255, 255, 0.7)",
                life: 1.0,
                decay: 0.05
            });
        }
    }

    _spawnStarSparkles(x, y) {
        for (let i = 0; i < 16; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 1.5 + Math.random() * 3.5;
            this.activeParticles.push({
                type: "sparkle",
                x: x, y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: 2 + Math.random() * 2.5,
                color: Math.random() > 0.5 ? "#FFD700" : "#FFF8DC",
                life: 1.0,
                decay: 0.035
            });
        }
    }

    _spawnConfetti(x, y) {
        const colors = ["#FF3366", "#33CCFF", "#FFCC00", "#33FF66", "#FF66FF", "#FFFF66"];
        for (let i = 0; i < 48; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 2.5 + Math.random() * 6;
            this.activeParticles.push({
                type: "confetti",
                x: x, y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed - 2.5,
                gravity: 0.15,
                size: 4 + Math.random() * 4,
                color: colors[Math.floor(Math.random() * colors.length)],
                rotation: Math.random() * Math.PI * 2,
                rotSpeed: (Math.random() - 0.5) * 0.2,
                life: 1.0,
                decay: 0.016
            });
        }
    }

    // --- Render Loop ---
    _startRenderLoop() {
        const render = (time) => {
            this._drawBoard(time);
            this._drawMovePreview(time);
            this._drawTokens(time);
            this._drawParticles();
            requestAnimationFrame(render);
        };
        requestAnimationFrame(render);
    }

    _drawMovePreview(time) {
        if (!this.gameState || !this.validMoves || this.validMoves.length === 0) return;
        const currPlayer = this.gameState.players[this.gameState.current_player_index];
        if (!currPlayer) return;

        let targetTokenId = this.hoveredToken;
        if (targetTokenId === null && this.validMoves.length === 1) {
            targetTokenId = this.validMoves[0];
        }
        if (targetTokenId === null) return;

        let movingPlayer = currPlayer;
        if (this.gameState.team_mode && (currPlayer.has_won || currPlayer.tokens.every(t => t.step === this.stepGoal || t.is_in_goal))) {
            const partnerColor = { red: "yellow", yellow: "red", green: "blue", blue: "green" }[currPlayer.color];
            movingPlayer = this.gameState.players.find(p => p.color === partnerColor) || currPlayer;
        }

        const token = movingPlayer.tokens[targetTokenId];
        if (!token) return;

        let dice = this.gameState.selected_die || this.gameState.dice_value;
        if (!dice && this.gameState.dice_values && this.gameState.dice_values.length > 0) {
            const d0 = this.gameState.dice_values[0];
            const d1 = this.gameState.dice_values[1];
            const canD0 = (token.step === -1 ? (d0 === 6 || (this.gameState.open_on_one && d0 === 1)) : (token.step + d0 <= this.stepGoal));
            const canD1 = (token.step === -1 ? (d1 === 6 || (this.gameState.open_on_one && d1 === 1)) : (token.step + d1 <= this.stepGoal));
            if (canD0 && !canD1) {
                dice = d0;
            } else if (canD1 && !canD0) {
                dice = d1;
            } else {
                dice = d0;
            }
        }
        if (!dice) dice = 1;

        let targetStep = token.step === -1 ? 0 : token.step + dice;
        if (targetStep > this.stepGoal) return;

        const fromPos = this.getTokenPixelPos(token);
        const toPos = this.getTokenPixelPos({ color: token.color, id: token.id, step: targetStep });

        const ctx = this.ctx;
        ctx.save();

        // Trajectory arc
        ctx.beginPath();
        ctx.setLineDash([7, 4]);
        ctx.lineDashOffset = -time * 0.035;
        ctx.moveTo(fromPos.x, fromPos.y);

        const midX = (fromPos.x + toPos.x) / 2;
        const midY = (fromPos.y + toPos.y) / 2 - (this.boardType > 4 ? 20 : this.cellSize * 0.65);
        ctx.quadraticCurveTo(midX, midY, toPos.x, toPos.y);

        const isBoost = (token.step === -1 && dice === 1);
        ctx.strokeStyle = isBoost ? "rgba(0, 240, 255, 0.85)" : "rgba(255, 215, 0, 0.85)";
        ctx.lineWidth = 2.5;
        ctx.stroke();
        ctx.setLineDash([]);

        // Landing characteristics
        let isCapture = false;
        let isSafe = false;
        let isGoal = targetStep === this.stepGoal;
        let isStart = token.step === -1;

        if (targetStep <= this.stepTrackMax) {
            const startOff = this.startOffsets[token.color] || 0;
            const targetGlobal = (startOff + targetStep) % this.trackLength;
            isSafe = this.safeIndices.has(targetGlobal);

            for (const opp of this.gameState.players) {
                if (opp.color === token.color) continue;
                for (const oppToken of opp.tokens) {
                    if (oppToken.step >= 0 && oppToken.step <= this.stepTrackMax) {
                        const oppStart = this.startOffsets[opp.color] || 0;
                        const oppGlobal = (oppStart + oppToken.step) % this.trackLength;
                        if (oppGlobal === targetGlobal && !isSafe) {
                            isCapture = true;
                            break;
                        }
                    }
                }
                if (isCapture) break;
            }
        }

        const pulse = (Math.sin(time * 0.008) + 1) / 2;
        const radius = (this.boardType > 4 ? 16 : this.cellSize * 0.44) + pulse * 4;

        ctx.beginPath();
        ctx.arc(toPos.x, toPos.y, radius, 0, Math.PI * 2);
        if (isCapture) {
            ctx.fillStyle = `rgba(255, 51, 102, ${0.28 + pulse * 0.2})`;
            ctx.strokeStyle = "#ff3366";
        } else if (isGoal) {
            ctx.fillStyle = `rgba(255, 215, 0, ${0.32 + pulse * 0.25})`;
            ctx.strokeStyle = "#ffd700";
        } else if (isStart) {
            ctx.fillStyle = isBoost ? `rgba(0, 240, 255, ${0.32 + pulse * 0.25})` : `rgba(255, 215, 0, ${0.28 + pulse * 0.2})`;
            ctx.strokeStyle = isBoost ? "#00f0ff" : "#ffd700";
        } else if (isSafe) {
            ctx.fillStyle = `rgba(0, 255, 136, ${0.25 + pulse * 0.2})`;
            ctx.strokeStyle = "#00ff88";
        } else {
            ctx.fillStyle = `rgba(255, 255, 255, ${0.22 + pulse * 0.15})`;
            ctx.strokeStyle = "#ffffff";
        }
        ctx.fill();
        ctx.lineWidth = 2.5;
        ctx.stroke();

        let badgeText = `+${dice}`;
        let badgeColor = "#ffffff";
        if (isCapture) {
            badgeText = "⚔️ CAPTURE!";
            badgeColor = "#ff3366";
        } else if (isGoal) {
            badgeText = "👑 GOAL!";
            badgeColor = "#ffd700";
        } else if (isStart) {
            badgeText = isBoost ? "⚡ BOOST!" : "🚀 START";
            badgeColor = isBoost ? "#00f0ff" : "#ffd700";
        } else if (isSafe) {
            badgeText = "⭐ SAFE";
            badgeColor = "#00ff88";
        }

        ctx.font = "bold 13px 'Segoe UI', system-ui, sans-serif";
        ctx.textAlign = "center";
        const textY = toPos.y - radius - 5;
        ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
        ctx.fillText(badgeText, toPos.x + 1, textY + 1);
        ctx.fillStyle = badgeColor;
        ctx.fillText(badgeText, toPos.x, textY);

        ctx.restore();
    }

    // --- Master Board Drawing Router ---
    _drawBoard(time) {
        if (this.boardType === 6) {
            this._drawBoard6(time);
        } else if (this.boardType === 8) {
            this._drawBoard8(time);
        } else {
            this._drawBoard4(time);
        }
    }

    _drawBackground(bs) {
        const ctx = this.ctx;
        if (this.theme === "wood") {
            const woodGrad = ctx.createRadialGradient(bs / 2, bs / 2, 40, bs / 2, bs / 2, bs * 0.75);
            woodGrad.addColorStop(0, "#4a2411");
            woodGrad.addColorStop(0.7, "#2e1408");
            woodGrad.addColorStop(1, "#1c0b04");
            ctx.fillStyle = woodGrad;
            ctx.fillRect(0, 0, bs, bs);

            ctx.strokeStyle = "rgba(0, 0, 0, 0.12)";
            ctx.lineWidth = 1;
            for (let i = 0; i < bs; i += 18) {
                ctx.beginPath();
                ctx.moveTo(0, i);
                ctx.bezierCurveTo(bs * 0.3, i + 5, bs * 0.7, i - 5, bs, i + 2);
                ctx.stroke();
            }

            ctx.strokeStyle = "rgba(218, 165, 32, 0.6)";
            ctx.lineWidth = 6;
            ctx.strokeRect(3, 3, bs - 6, bs - 6);
        } else if (this.theme === "cyber") {
            ctx.fillStyle = "#0a0a14";
            ctx.fillRect(0, 0, bs, bs);

            ctx.strokeStyle = "rgba(0, 240, 255, 0.08)";
            ctx.lineWidth = 1;
            for (let i = 0; i <= bs; i += 50) {
                ctx.beginPath();
                ctx.moveTo(i, 0); ctx.lineTo(i, bs);
                ctx.moveTo(0, i); ctx.lineTo(bs, i);
                ctx.stroke();
            }

            ctx.strokeStyle = "#00f0ff";
            ctx.shadowColor = "#00f0ff";
            ctx.shadowBlur = 15;
            ctx.lineWidth = 3;
            ctx.strokeRect(3, 3, bs - 6, bs - 6);
            ctx.shadowBlur = 0;
        } else {
            ctx.fillStyle = "#f5f3ef";
            ctx.fillRect(0, 0, bs, bs);

            ctx.strokeStyle = "rgba(200, 180, 140, 0.4)";
            ctx.lineWidth = 4;
            ctx.strokeRect(4, 4, bs - 8, bs - 8);
        }
    }

    // --- 4-Player Board Render ---
    _drawBoard4(time) {
        const bs = this.boardSize;
        this._drawBackground(bs);

        this._drawYard(0, 0, 6, 6, "red", time);
        this._drawYard(0, 9, 6, 6, "green", time);
        this._drawYard(9, 9, 6, 6, "yellow", time);
        this._drawYard(9, 0, 6, 6, "blue", time);

        for (let i = 0; i < 52; i++) {
            const tile = this.trackCoords[i];
            const isSafe = this.safeIndices.has(i);
            const isStart = i === 0 || i === 13 || i === 26 || i === 39;
            const startColor = i === 0 ? "red" : i === 13 ? "green" : i === 26 ? "yellow" : i === 39 ? "blue" : null;
            this._drawTrackCell(tile.r, tile.c, isSafe, isStart, startColor, i);
        }

        const homeColors = ["red", "green", "yellow", "blue"];
        for (const hc of homeColors) {
            const coords = this.homeRunCoords[hc];
            for (let h = 0; h < 5; h++) {
                const tile = coords[h];
                this._drawHomeRunCell(tile.r, tile.c, hc, h + 1);
            }
        }

        this._drawCenterCrest(time);
    }

    // --- 6-Player Hexagonal Board Render ---
    _drawBoard6(time) {
        const bs = this.boardSize;
        this._drawBackground(bs);

        const colors6 = ["red", "green", "yellow", "blue", "orange", "purple"];
        const cx = 375;
        const cy = 375;
        const R_tip = 240;
        const R_valley = 110;
        const ctx = this.ctx;

        // Draw decorative 6-pointed star base
        ctx.save();
        ctx.beginPath();
        for (let k = 0; k < 6; k++) {
            const theta = (k * 2 * Math.PI) / 6 - Math.PI / 2;
            const valleyTheta = theta + (Math.PI / 6);
            const tx = cx + Math.cos(theta) * (R_tip + 18);
            const ty = cy + Math.sin(theta) * (R_tip + 18);
            const vx = cx + Math.cos(valleyTheta) * (R_valley - 8);
            const vy = cy + Math.sin(valleyTheta) * (R_valley - 8);
            if (k === 0) ctx.moveTo(tx, ty);
            else ctx.lineTo(tx, ty);
            ctx.lineTo(vx, vy);
        }
        ctx.closePath();
        ctx.fillStyle = this.theme === "cyber" ? "rgba(18, 24, 42, 0.88)" : "rgba(255, 255, 255, 0.88)";
        ctx.fill();
        ctx.strokeStyle = this.theme === "cyber" ? "rgba(0, 240, 255, 0.55)" : "rgba(218, 165, 32, 0.55)";
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.restore();

        // Draw radial track cells
        for (let i = 0; i < 78; i++) {
            const pt = this.trackCoords[i];
            if (!pt) continue;
            const isSafe = this.safeIndices.has(i);
            const isStart = i % 13 === 0;
            const startCol = isStart ? colors6[Math.floor(i / 13)] : null;
            this._drawPolygonCell(pt.x, pt.y, 11, isSafe, isStart, startCol);
        }

        // Draw 6 Home paths
        for (const col of colors6) {
            const path = this.homeRunCoords[col] || [];
            for (let h = 0; h < 5; h++) {
                const pt = path[h];
                if (!pt) continue;
                this._drawPolygonHomeCell(pt.x, pt.y, 10, col, h + 1);
            }
        }

        // Draw 6 Central Goal Wedges
        this._drawRadialCenterGoal(6, colors6);

        // Draw 6 Yards
        colors6.forEach((col, k) => {
            const theta = (k * 2 * Math.PI) / 6 - Math.PI / 2 + Math.PI / 6;
            const yx = cx + Math.cos(theta) * 295;
            const yy = cy + Math.sin(theta) * 295;
            this._drawCircularYard(yx, yy, 44, col);
        });
    }

    // --- 8-Player Octagonal Board Render ---
    _drawBoard8(time) {
        const bs = this.boardSize;
        this._drawBackground(bs);

        const colors8 = ["red", "green", "yellow", "blue", "orange", "purple", "cyan", "pink"];
        const cx = 375;
        const cy = 375;
        const R_tip = 250;
        const R_valley = 125;
        const ctx = this.ctx;

        // Draw decorative 8-pointed star base
        ctx.save();
        ctx.beginPath();
        for (let k = 0; k < 8; k++) {
            const theta = (k * 2 * Math.PI) / 8 - Math.PI / 2;
            const valleyTheta = theta + (Math.PI / 8);
            const tx = cx + Math.cos(theta) * (R_tip + 16);
            const ty = cy + Math.sin(theta) * (R_tip + 16);
            const vx = cx + Math.cos(valleyTheta) * (R_valley - 8);
            const vy = cy + Math.sin(valleyTheta) * (R_valley - 8);
            if (k === 0) ctx.moveTo(tx, ty);
            else ctx.lineTo(tx, ty);
            ctx.lineTo(vx, vy);
        }
        ctx.closePath();
        ctx.fillStyle = this.theme === "cyber" ? "rgba(18, 24, 42, 0.88)" : "rgba(255, 255, 255, 0.88)";
        ctx.fill();
        ctx.strokeStyle = this.theme === "cyber" ? "rgba(0, 240, 255, 0.55)" : "rgba(218, 165, 32, 0.55)";
        ctx.lineWidth = 3;
        ctx.stroke();
        ctx.restore();

        // Draw 104 radial track cells
        for (let i = 0; i < 104; i++) {
            const pt = this.trackCoords[i];
            if (!pt) continue;
            const isSafe = this.safeIndices.has(i);
            const isStart = i % 13 === 0;
            const startCol = isStart ? colors8[Math.floor(i / 13)] : null;
            this._drawPolygonCell(pt.x, pt.y, 9.5, isSafe, isStart, startCol);
        }

        // Draw 8 Home paths
        for (const col of colors8) {
            const path = this.homeRunCoords[col] || [];
            for (let h = 0; h < 5; h++) {
                const pt = path[h];
                if (!pt) continue;
                this._drawPolygonHomeCell(pt.x, pt.y, 8.5, col, h + 1);
            }
        }

        // Draw 8 Central Goal Wedges
        this._drawRadialCenterGoal(8, colors8);

        // Draw 8 Yards
        colors8.forEach((col, k) => {
            const theta = (k * 2 * Math.PI) / 8 - Math.PI / 2 + Math.PI / 8;
            const yx = cx + Math.cos(theta) * 300;
            const yy = cy + Math.sin(theta) * 300;
            this._drawCircularYard(yx, yy, 38, col);
        });
    }

    _drawPolygonCell(x, y, r, isSafe, isStart, startColor) {
        const ctx = this.ctx;
        ctx.save();

        let cellBg = this.theme === "cyber" ? "#161b2e" : "#fdfbf7";
        let borderCol = this.theme === "cyber" ? "#2d3758" : "#d0c8b8";

        if (isStart && startColor) {
            const pal = this._getColorPalette(startColor);
            cellBg = pal.main;
            borderCol = pal.border;
        }

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = cellBg;
        ctx.fill();
        ctx.strokeStyle = borderCol;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        if (isSafe) {
            this._drawStar(ctx, x, y, r * 0.65, isStart ? "#ffffff" : "#FFD700");
        } else if (isStart && startColor) {
            this._drawStar(ctx, x, y, r * 0.55, "#ffffff");
        }

        ctx.restore();
    }

    _drawPolygonHomeCell(x, y, r, color, stepNum) {
        const ctx = this.ctx;
        const pal = this._getColorPalette(color);
        ctx.save();

        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = pal.main;
        ctx.fill();
        ctx.strokeStyle = pal.border;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Inner pip
        ctx.beginPath();
        ctx.arc(x, y, r * 0.38, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
        ctx.fill();

        ctx.restore();
    }

    _drawRadialCenterGoal(numArms, colors) {
        const ctx = this.ctx;
        const cx = 375;
        const cy = 375;
        const rGoal = numArms === 8 ? 44 : 50;

        ctx.save();
        const halfWedge = Math.PI / numArms;
        for (let k = 0; k < numArms; k++) {
            const col = colors[k];
            const pal = this._getColorPalette(col);
            const theta = (k * 2 * Math.PI) / numArms - Math.PI / 2;
            const a1 = theta - halfWedge;
            const a2 = theta + halfWedge;

            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.arc(cx, cy, rGoal, a1, a2);
            ctx.closePath();

            ctx.fillStyle = pal.main;
            ctx.fill();
            ctx.strokeStyle = pal.border;
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Center Gold Crest
        ctx.beginPath();
        ctx.arc(cx, cy, rGoal * 0.45, 0, Math.PI * 2);
        const crestGrad = ctx.createRadialGradient(cx, cy, 3, cx, cy, rGoal * 0.45);
        crestGrad.addColorStop(0, "#FFF8DC");
        crestGrad.addColorStop(0.6, "#DAA520");
        crestGrad.addColorStop(1, "#8B6508");
        ctx.fillStyle = crestGrad;
        ctx.fill();
        ctx.strokeStyle = "#4A3305";
        ctx.lineWidth = 2;
        ctx.stroke();

        this._drawStar(ctx, cx, cy, rGoal * 0.25, "#ffffff");
        ctx.restore();
    }

    _drawCircularYard(x, y, radius, color) {
        const ctx = this.ctx;
        const pal = this._getColorPalette(color);
        ctx.save();

        // Outer base
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = pal.yardBg;
        ctx.fill();
        ctx.strokeStyle = pal.border;
        ctx.lineWidth = 3;
        ctx.stroke();

        // Inner plate
        ctx.beginPath();
        ctx.arc(x, y, radius * 0.78, 0, Math.PI * 2);
        ctx.fillStyle = this.theme === "cyber" ? "rgba(10, 15, 30, 0.85)" : "rgba(255, 255, 255, 0.9)";
        ctx.fill();

        // 4 Token Slots
        const slots = this.yardCoords[color] || [];
        slots.forEach(s => {
            const slotR = radius * 0.22;
            ctx.beginPath();
            ctx.arc(s.x, s.y, slotR, 0, Math.PI * 2);
            ctx.fillStyle = pal.slotBg;
            ctx.fill();
            ctx.strokeStyle = pal.slotBorder;
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(s.x, s.y, slotR * 0.65, 0, Math.PI * 2);
            ctx.fillStyle = pal.slotInner;
            ctx.fill();
        });

        ctx.restore();
    }

    _drawYard(r, c, w, h, color, time) {
        const ctx = this.ctx;
        const cs = this.cellSize;
        const x = c * cs;
        const y = r * cs;
        const width = w * cs;
        const height = h * cs;

        ctx.save();
        const palette = this._getColorPalette(color);

        ctx.fillStyle = palette.yardBg;
        ctx.strokeStyle = palette.border;
        ctx.lineWidth = 3;

        this._roundRect(ctx, x + 6, y + 6, width - 12, height - 12, 16);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = this.theme === "cyber" ? "rgba(10, 15, 30, 0.85)" : "rgba(255, 255, 255, 0.9)";
        this._roundRect(ctx, x + 30, y + 30, width - 60, height - 60, 16);
        ctx.fill();

        const slots = this.yardCoords[color] || [];
        slots.forEach(s => {
            const sx = s.x;
            const sy = s.y;
            const radius = cs * 0.44;

            ctx.beginPath();
            ctx.arc(sx, sy, radius, 0, Math.PI * 2);
            ctx.fillStyle = palette.slotBg;
            ctx.fill();
            ctx.strokeStyle = palette.slotBorder;
            ctx.lineWidth = 2.5;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(sx, sy, radius * 0.8, 0, Math.PI * 2);
            ctx.fillStyle = palette.slotInner;
            ctx.fill();
        });

        ctx.restore();
    }

    _drawTrackCell(r, c, isSafe, isStart, startColor, globalIndex) {
        const ctx = this.ctx;
        const cs = this.cellSize;
        const x = c * cs;
        const y = r * cs;

        ctx.save();
        let cellBg = this.theme === "cyber" ? "#161b2e" : "#fdfbf7";
        let borderCol = this.theme === "cyber" ? "#2d3758" : "#d0c8b8";

        if (isStart && startColor) {
            const pal = this._getColorPalette(startColor);
            cellBg = pal.main;
            borderCol = pal.border;
        }

        ctx.fillStyle = cellBg;
        ctx.fillRect(x + 1, y + 1, cs - 2, cs - 2);

        ctx.strokeStyle = borderCol;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x + 1, y + 1, cs - 2, cs - 2);

        if (isSafe) {
            this._drawStar(ctx, x + cs / 2, y + cs / 2, cs * 0.32, isStart ? "#ffffff" : "#FFD700");
        } else if (isStart && startColor) {
            this._drawStar(ctx, x + cs / 2, y + cs / 2, cs * 0.28, "#ffffff");
        }

        ctx.restore();
    }

    _drawHomeRunCell(r, c, color, stepNum) {
        const ctx = this.ctx;
        const cs = this.cellSize;
        const x = c * cs;
        const y = r * cs;
        const pal = this._getColorPalette(color);

        ctx.save();
        ctx.fillStyle = pal.main;
        ctx.fillRect(x + 1, y + 1, cs - 2, cs - 2);
        ctx.strokeStyle = pal.border;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(x + 1, y + 1, cs - 2, cs - 2);

        ctx.beginPath();
        ctx.arc(x + cs / 2, y + cs / 2, cs * 0.16, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.75)";
        ctx.fill();
        ctx.restore();
    }

    _drawCenterCrest(time) {
        const ctx = this.ctx;
        const cs = this.cellSize;
        const cx = 7.5 * cs;
        const cy = 7.5 * cs;

        ctx.save();
        this._drawCenterTriangle(6 * cs, 6 * cs, 6 * cs, 9 * cs, cx, cy, "red");
        this._drawCenterTriangle(6 * cs, 6 * cs, 9 * cs, 6 * cs, cx, cy, "green");
        this._drawCenterTriangle(9 * cs, 6 * cs, 9 * cs, 9 * cs, cx, cy, "yellow");
        this._drawCenterTriangle(6 * cs, 9 * cs, 9 * cs, 9 * cs, cx, cy, "blue");

        ctx.beginPath();
        ctx.arc(cx, cy, cs * 0.65, 0, Math.PI * 2);
        const crestGrad = ctx.createRadialGradient(cx, cy, 5, cx, cy, cs * 0.65);
        crestGrad.addColorStop(0, "#FFF8DC");
        crestGrad.addColorStop(0.6, "#DAA520");
        crestGrad.addColorStop(1, "#8B6508");
        ctx.fillStyle = crestGrad;
        ctx.fill();

        ctx.strokeStyle = "#4A3305";
        ctx.lineWidth = 2.5;
        ctx.stroke();

        this._drawStar(ctx, cx, cy, cs * 0.35, "#ffffff");
        ctx.restore();
    }

    _drawCenterTriangle(x1, y1, x2, y2, cx, cy, color) {
        const ctx = this.ctx;
        const pal = this._getColorPalette(color);

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.lineTo(cx, cy);
        ctx.closePath();

        ctx.fillStyle = pal.main;
        ctx.fill();
        ctx.strokeStyle = pal.border;
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    _drawStar(ctx, cx, cy, r, fillStyle) {
        ctx.save();
        ctx.beginPath();
        const spikes = 5;
        const innerR = r * 0.45;
        let rot = (Math.PI / 2) * 3;
        const step = Math.PI / spikes;

        ctx.moveTo(cx, cy - r);
        for (let i = 0; i < spikes; i++) {
            let x = cx + Math.cos(rot) * r;
            let y = cy + Math.sin(rot) * r;
            ctx.lineTo(x, y);
            rot += step;

            x = cx + Math.cos(rot) * innerR;
            y = cy + Math.sin(rot) * innerR;
            ctx.lineTo(x, y);
            rot += step;
        }
        ctx.lineTo(cx, cy - r);
        ctx.closePath();

        ctx.fillStyle = fillStyle;
        ctx.shadowColor = "rgba(0,0,0,0.3)";
        ctx.shadowBlur = 4;
        ctx.fill();
        ctx.restore();
    }

    // --- Token Rendering (3D Pawn Styling & Stacking) ---
    _drawTokens(time) {
        if (!this.gameState) return;

        const tileGroups = {};

        for (const player of this.gameState.players) {
            for (const token of player.tokens) {
                if (this.animatingToken && this.animatingToken.color === token.color && this.animatingToken.id === token.id) {
                    continue;
                }

                if (token.step === this.stepGoal) {
                    this._drawFinishedGoalToken(token);
                    continue;
                }

                const key = `${token.color}_${token.step}`;
                let groupKey = key;
                if (token.step >= 0 && token.step <= this.stepTrackMax) {
                    const startOff = this.startOffsets[token.color] || 0;
                    groupKey = `track_${(startOff + token.step) % this.trackLength}`;
                }

                if (!tileGroups[groupKey]) {
                    tileGroups[groupKey] = [];
                }
                tileGroups[groupKey].push(token);
            }
        }

        for (const groupKey of Object.keys(tileGroups)) {
            const tokens = tileGroups[groupKey];
            const count = tokens.length;

            tokens.forEach((token, index) => {
                const basePos = this.getTokenPixelPos(token);
                let offsetX = 0;
                let offsetY = 0;

                if (count > 1 && token.step !== -1) {
                    const spreadRadius = (this.boardType > 4 ? 8 : this.cellSize * 0.22);
                    const angle = (index / count) * Math.PI * 2 - Math.PI / 2;
                    offsetX = Math.cos(angle) * spreadRadius;
                    offsetY = Math.sin(angle) * spreadRadius;
                }

                const posX = basePos.x + offsetX;
                const posY = basePos.y + offsetY;
                let movingColor = this.gameState.current_player;
                if (this.gameState.team_mode) {
                    const cp = this.gameState.players[this.gameState.current_player_index];
                    if (cp && (cp.has_won || cp.tokens.every(t => t.step === this.stepGoal || t.is_in_goal))) {
                        movingColor = { red: "yellow", yellow: "red", green: "blue", blue: "green" }[cp.color] || cp.color;
                    }
                }

                const isHovered = this.hoveredToken === token.id && token.color === movingColor;
                const isMoveable = this.validMoves.includes(token.id) && token.color === movingColor;

                this._drawPawn(posX, posY, token.color, 1.0, 0, isHovered, isMoveable, time);
            });
        }

        // Draw actively animating hopping token on top
        if (this.animatingToken) {
            this._drawPawn(
                this.animatingToken.x,
                this.animatingToken.y,
                this.animatingToken.color,
                this.animatingToken.scale,
                this.animatingToken.hopOffset,
                false,
                false,
                time
            );
        }
    }

    _drawFinishedGoalToken(token) {
        const pos = this.getTokenPixelPos(token);
        this._drawPawn(pos.x, pos.y, token.color, 0.72, 0, false, false, 0);
    }

    _drawPawn(x, y, color, scale, hopOffset, isHovered, isMoveable, time) {
        const ctx = this.ctx;
        const pal = this._getColorPalette(color);
        const radius = (this.boardType > 4 ? 13 : this.cellSize * 0.38) * scale;
        const drawY = y - hopOffset;

        ctx.save();

        // 1. Shadow beneath pawn
        const shadowScale = Math.max(0.4, 1.0 - (hopOffset / 35));
        ctx.beginPath();
        ctx.ellipse(x, y + radius * 0.4, radius * 0.85 * shadowScale, radius * 0.35 * shadowScale, 0, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 0, 0, ${0.45 * shadowScale})`;
        ctx.fill();

        // 2. Moveable / Hover Glow Ring
        if (isMoveable || isHovered) {
            const pulse = (Math.sin(time * 0.009) + 1) / 2;
            ctx.beginPath();
            ctx.arc(x, drawY, radius * (1.35 + pulse * 0.2), 0, Math.PI * 2);
            ctx.fillStyle = isHovered ? "rgba(255, 255, 255, 0.35)" : "rgba(255, 215, 0, 0.3)";
            ctx.fill();
            ctx.strokeStyle = isHovered ? "#ffffff" : "#FFD700";
            ctx.lineWidth = 2.5;
            ctx.stroke();
        }

        // 3. Pawn Outer Metallic Rim
        ctx.beginPath();
        ctx.arc(x, drawY, radius, 0, Math.PI * 2);
        ctx.fillStyle = pal.border;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "rgba(0, 0, 0, 0.35)";
        ctx.stroke();

        // 4. Pawn Spherical 3D Dome
        ctx.beginPath();
        ctx.arc(x, drawY, radius * 0.85, 0, Math.PI * 2);
        const domeGrad = ctx.createRadialGradient(
            x - radius * 0.3, drawY - radius * 0.3, radius * 0.05,
            x, drawY, radius * 0.85
        );
        domeGrad.addColorStop(0, "#ffffff");
        domeGrad.addColorStop(0.2, pal.light);
        domeGrad.addColorStop(0.7, pal.main);
        domeGrad.addColorStop(1, pal.dark);

        ctx.fillStyle = domeGrad;
        ctx.fill();

        // 5. Center Top Crest
        ctx.beginPath();
        ctx.arc(x, drawY - radius * 0.1, radius * 0.28, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
        ctx.fill();

        ctx.restore();
    }

    _drawParticles() {
        const ctx = this.ctx;

        for (let i = this.activeParticles.length - 1; i >= 0; i--) {
            const p = this.activeParticles[i];
            p.life -= p.decay;

            if (p.life <= 0) {
                this.activeParticles.splice(i, 1);
                continue;
            }

            ctx.save();

            if (p.type === "puff") {
                p.x += p.vx;
                p.y += p.vy;
                p.radius += 0.2;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255, 255, 255, ${p.life * 0.6})`;
                ctx.fill();

            } else if (p.type === "shockwave") {
                p.radius += (p.maxRadius - p.radius) * 0.12;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.strokeStyle = p.color || `rgba(255, 60, 60, ${p.life * 0.85})`;
                ctx.globalAlpha = p.life;
                ctx.lineWidth = 4 * p.life;
                ctx.stroke();

            } else if (p.type === "shield_ripple") {
                p.radius += (p.maxRadius - p.radius) * 0.1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.strokeStyle = p.color || "#00ff88";
                ctx.globalAlpha = p.life * 0.8;
                ctx.lineWidth = 3.5 * p.life;
                ctx.shadowColor = p.color;
                ctx.shadowBlur = 10;
                ctx.stroke();

            } else if (p.type === "blast_spark") {
                p.x += p.vx;
                p.y += p.vy;
                p.vy += 0.08; // gravity
                p.vx *= 0.96;
                p.vy *= 0.96;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = p.life;
                ctx.shadowColor = p.color;
                ctx.shadowBlur = 8;
                ctx.fill();

            } else if (p.type === "speed_trail") {
                p.x += p.vx;
                p.y += p.vy;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p.x - p.vx * 2.5, p.y - p.vy * 2.5);
                ctx.strokeStyle = p.color;
                ctx.globalAlpha = p.life * 0.85;
                ctx.lineWidth = 2.5 * p.life;
                ctx.shadowColor = p.color;
                ctx.shadowBlur = 6;
                ctx.stroke();

            } else if (p.type === "sparkle") {
                p.x += p.vx;
                p.y += p.vy;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = p.life;
                ctx.shadowColor = p.color;
                ctx.shadowBlur = 6;
                ctx.fill();

            } else if (p.type === "confetti") {
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity;
                p.rotation += p.rotSpeed;

                ctx.translate(p.x, p.y);
                ctx.rotate(p.rotation);
                ctx.fillStyle = p.color;
                ctx.globalAlpha = p.life;
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);

            } else if (p.type === "text") {
                p.y += p.vy;
                ctx.font = "900 16px 'Segoe UI', system-ui, sans-serif";
                ctx.textAlign = "center";
                ctx.globalAlpha = p.life;
                ctx.shadowColor = p.color;
                ctx.shadowBlur = 10;
                ctx.fillStyle = p.color;
                ctx.fillText(p.text, p.x, p.y);
            }

            ctx.restore();
        }
    }

    // --- Luxury Color Palettes (All 8 Colors x 3 Themes) ---
    _getColorPalette(color) {
        if (this.theme === "cyber") {
            const cyber = {
                red: { main: "#ff0055", light: "#ff6699", dark: "#990033", border: "#ff3377", yardBg: "rgba(255,0,85,0.18)", slotBg: "#1f0d1b", slotBorder: "#ff0055", slotInner: "#3d112d" },
                green: { main: "#00ff88", light: "#66ffb3", dark: "#009952", border: "#33ff9f", yardBg: "rgba(0,255,136,0.18)", slotBg: "#0d1f16", slotBorder: "#00ff88", slotInner: "#113d26" },
                yellow: { main: "#ffcc00", light: "#ffdd66", dark: "#997a00", border: "#ffd633", yardBg: "rgba(255,204,0,0.18)", slotBg: "#1f1c0d", slotBorder: "#ffcc00", slotInner: "#3d3611" },
                blue: { main: "#00c3ff", light: "#66dbff", dark: "#007599", border: "#33cfff", yardBg: "rgba(0,195,255,0.18)", slotBg: "#0d1b1f", slotBorder: "#00c3ff", slotInner: "#11343d" },
                orange: { main: "#ff6600", light: "#ff9933", dark: "#993d00", border: "#ff7711", yardBg: "rgba(255,102,0,0.18)", slotBg: "#1f140d", slotBorder: "#ff6600", slotInner: "#3d2411" },
                purple: { main: "#b537f2", light: "#d073f7", dark: "#6d1299", border: "#be4cf5", yardBg: "rgba(181,55,242,0.18)", slotBg: "#190d1f", slotBorder: "#b537f2", slotInner: "#33113d" },
                cyan: { main: "#00f0ff", light: "#70f7ff", dark: "#008899", border: "#22f2ff", yardBg: "rgba(0,240,255,0.18)", slotBg: "#0d1e1f", slotBorder: "#00f0ff", slotInner: "#113b3d" },
                pink: { main: "#ff1493", light: "#ff69b4", dark: "#990b56", border: "#ff2a9f", yardBg: "rgba(255,20,147,0.18)", slotBg: "#1f0d18", slotBorder: "#ff1493", slotInner: "#3d112c" }
            };
            return cyber[color] || cyber.red;
        }

        // Royal Wood / Classic Luxury
        const classic = {
            red: { main: "#d32f2f", light: "#ff6659", dark: "#9a0007", border: "#800000", yardBg: "#5c1818", slotBg: "#f9eaea", slotBorder: "#d32f2f", slotInner: "#e0b0b0" },
            green: { main: "#2e7d32", light: "#60ad5e", dark: "#005005", border: "#003b00", yardBg: "#164718", slotBg: "#eaf9ec", slotBorder: "#2e7d32", slotInner: "#b0e0b4" },
            yellow: { main: "#f9a825", light: "#ffd95a", dark: "#c17900", border: "#8c5600", yardBg: "#573d09", slotBg: "#fdf8ea", slotBorder: "#f9a825", slotInner: "#f3e1b0" },
            blue: { main: "#1976d2", light: "#63a4ff", dark: "#004ba0", border: "#002d6b", yardBg: "#12375c", slotBg: "#eaf3f9", slotBorder: "#1976d2", slotInner: "#b0cfe0" },
            orange: { main: "#e65100", light: "#ff833a", dark: "#ac1900", border: "#731000", yardBg: "#572408", slotBg: "#fdf0ea", slotBorder: "#e65100", slotInner: "#f3c7b0" },
            purple: { main: "#6a1b9a", light: "#9c4dcc", dark: "#38006b", border: "#250047", yardBg: "#3b1154", slotBg: "#f5eaf9", slotBorder: "#6a1b9a", slotInner: "#dab0f3" },
            cyan: { main: "#00838f", light: "#4fb3bf", dark: "#005662", border: "#003b44", yardBg: "#0a3a40", slotBg: "#eaf7f9", slotBorder: "#00838f", slotInner: "#b0e6ec" },
            pink: { main: "#ad1457", light: "#e35182", dark: "#78002e", border: "#4f001c", yardBg: "#4a0b27", slotBg: "#f9eaf0", slotBorder: "#ad1457", slotInner: "#f0b0ca" }
        };
        return classic[color] || classic.red;
    }

    _roundRect(ctx, x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }
}

window.LudoBoard = LudoBoard;
