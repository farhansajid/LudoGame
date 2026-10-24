/**
 * 3D Dice Roller Engine
 * Supports 1-die and 2-dice modes with realistic tumbling physics, shadows,
 * face pip layouts, and interactive die selection.
 */

class DiceRoller {
    constructor(containerElement, onRollClick, onDieSelect) {
        this.container = containerElement;
        this.onRollClick = onRollClick;
        this.onDieSelect = onDieSelect;
        this.twoDiceMode = false;
        this.isRolling = false;
        this.canRoll = false;
        this.canSelect = false;
        this.currentValues = [1, 1];
        this.selectedDieIndex = 0;

        // Base rotations to display each face (1 through 6)
        this.faceRotations = {
            1: { x: 0, y: 0 },
            2: { x: -90, y: 0 },
            3: { x: 0, y: -90 },
            4: { x: 0, y: 90 },
            5: { x: 90, y: 0 },
            6: { x: 180, y: 0 }
        };

        this._buildDom();
        this._setupListeners();
    }

    setTwoDiceMode(enabled) {
        if (this.twoDiceMode !== !!enabled) {
            this.twoDiceMode = !!enabled;
            this._buildDom();
            this.showValues(this.currentValues);
        }
    }

    _getCubeHtml(idx) {
        return `
            <div class="dice-wrapper" id="dice-wrapper-${idx}" data-index="${idx}">
                <div class="dice-scene">
                    <div class="dice-cube" id="dice-cube-${idx}">
                        <div class="dice-face face-1"><span class="pip"></span></div>
                        <div class="dice-face face-2"><span class="pip"></span><span class="pip"></span></div>
                        <div class="dice-face face-3"><span class="pip"></span><span class="pip"></span><span class="pip"></span></div>
                        <div class="dice-face face-4"><span class="pip"></span><span class="pip"></span><span class="pip"></span><span class="pip"></span></div>
                        <div class="dice-face face-5"><span class="pip"></span><span class="pip"></span><span class="pip"></span><span class="pip"></span><span class="pip"></span></div>
                        <div class="dice-face face-6"><span class="pip"></span><span class="pip"></span><span class="pip"></span><span class="pip"></span><span class="pip"></span><span class="pip"></span></div>
                    </div>
                </div>
                <div class="dice-shadow"></div>
                <div class="dice-prompt" id="dice-prompt-${idx}">ROLL</div>
                <div class="dice-select-badge" id="dice-badge-${idx}">USE</div>
            </div>
        `;
    }

    _buildDom() {
        if (this.twoDiceMode) {
            this.container.innerHTML = `
                <div class="two-dice-container">
                    ${this._getCubeHtml(0)}
                    ${this._getCubeHtml(1)}
                </div>
            `;
            this.cubes = [
                this.container.querySelector("#dice-cube-0"),
                this.container.querySelector("#dice-cube-1")
            ];
            this.wrappers = [
                this.container.querySelector("#dice-wrapper-0"),
                this.container.querySelector("#dice-wrapper-1")
            ];
            this.prompts = [
                this.container.querySelector("#dice-prompt-0"),
                this.container.querySelector("#dice-prompt-1")
            ];
            this.badges = [
                this.container.querySelector("#dice-badge-0"),
                this.container.querySelector("#dice-badge-1")
            ];
        } else {
            this.container.innerHTML = this._getCubeHtml(0);
            this.cubes = [this.container.querySelector("#dice-cube-0")];
            this.wrappers = [this.container.querySelector("#dice-wrapper-0")];
            this.prompts = [this.container.querySelector("#dice-prompt-0")];
            this.badges = [this.container.querySelector("#dice-badge-0")];
        }

        // Setup individual wrapper click events
        this.wrappers.forEach((wrap, idx) => {
            wrap.addEventListener("click", () => {
                if (this.canRoll && !this.isRolling) {
                    if (this.onRollClick) this.onRollClick();
                } else if (this.canSelect && !this.isRolling && this.twoDiceMode && !wrap.classList.contains("disabled-die") && !wrap.classList.contains("consumed-die")) {
                    this.selectDieIndex(idx, true);
                }
            });
        });
    }

    _setupListeners() {
        window.addEventListener("keydown", (e) => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
            // Roll with Space or Enter key
            if ((e.code === "Space" || e.key === "Enter") && this.canRoll && !this.isRolling) {
                if (!window.audioSystem || !window.audioSystem.isPushToTalk) {
                    e.preventDefault();
                    if (this.onRollClick) this.onRollClick();
                }
            } else if (this.canSelect && this.twoDiceMode && (e.key === "1" || e.key === "2")) {
                const idx = parseInt(e.key, 10) - 1;
                const wrap = this.wrappers && this.wrappers[idx];
                if (wrap && !wrap.classList.contains("disabled-die") && !wrap.classList.contains("consumed-die")) {
                    this.selectDieIndex(idx, true);
                }
            }
        });
    }

    setCanRoll(canRoll, promptText = "ROLL") {
        this.canRoll = canRoll;
        this.wrappers.forEach((w, idx) => {
            w.classList.remove("consumed-die");
            if (canRoll) {
                w.classList.add("can-roll");
                w.classList.remove("selected", "selectable");
                if (this.prompts[idx]) {
                    this.prompts[idx].innerText = promptText;
                    this.prompts[idx].classList.add("active");
                }
                if (this.badges[idx]) {
                    this.badges[idx].classList.remove("active");
                }
            } else {
                w.classList.remove("can-roll");
                if (this.prompts[idx]) {
                    this.prompts[idx].classList.remove("active");
                    if (!this.isRolling) this.prompts[idx].innerText = "";
                }
            }
        });
    }

    setCanSelect(canSelect, validMovesByDie = null, remainingDice = null, usedDice = null, selectedDie = null) {
        if (!this.twoDiceMode) return;
        if (remainingDice !== null || usedDice !== null) {
            this.updateDiceStatus(remainingDice, usedDice, selectedDie, validMovesByDie, canSelect);
            return;
        }

        this.canSelect = canSelect;
        this.wrappers.forEach((w, idx) => {
            const val = this.currentValues[idx];
            const hasMoves = !validMovesByDie || (validMovesByDie[String(val)] && validMovesByDie[String(val)].length > 0);

            if (canSelect && hasMoves) {
                w.classList.add("selectable");
                w.classList.remove("disabled-die");
                if (this.badges[idx]) {
                    this.badges[idx].classList.add("active");
                    this.badges[idx].innerText = idx === this.selectedDieIndex ? "✓ ACTIVE" : "SELECT";
                }
            } else {
                w.classList.remove("selectable");
                if (canSelect && !hasMoves) {
                    w.classList.add("disabled-die");
                    if (this.badges[idx]) {
                        this.badges[idx].classList.add("active");
                        this.badges[idx].innerText = "NO MOVES";
                    }
                } else if (this.badges[idx]) {
                    this.badges[idx].classList.remove("active");
                }
            }
            if (idx === this.selectedDieIndex && canSelect) {
                w.classList.add("selected");
            } else {
                w.classList.remove("selected");
            }
        });
    }

    updateDiceStatus(remainingDice, usedDice, selectedDie, validMovesByDie, canSelect) {
        if (!this.twoDiceMode || !this.wrappers) return;
        this.canSelect = canSelect;

        const rem = Array.isArray(remainingDice) ? [...remainingDice] : [];
        const used = Array.isArray(usedDice) ? [...usedDice] : [];

        this.wrappers.forEach((wrap, idx) => {
            const val = this.currentValues[idx];
            const usedIdx = used.indexOf(val);

            if (usedIdx !== -1) {
                // Die has been consumed in this turn
                used.splice(usedIdx, 1);
                wrap.classList.add("consumed-die");
                wrap.classList.remove("selectable", "selected", "can-roll", "disabled-die");
                if (this.badges[idx]) {
                    this.badges[idx].classList.add("active");
                    this.badges[idx].innerText = "✓ USED";
                }
            } else {
                wrap.classList.remove("consumed-die");
                const hasMoves = !validMovesByDie || (validMovesByDie[String(val)] && validMovesByDie[String(val)].length > 0);

                if (canSelect && hasMoves) {
                    wrap.classList.add("selectable");
                    wrap.classList.remove("disabled-die");
                    const isSelected = (selectedDie !== null && selectedDie !== undefined)
                        ? (val === selectedDie)
                        : (idx === this.selectedDieIndex || rem.length === 1);

                    if (isSelected) {
                        wrap.classList.add("selected");
                        if (this.badges[idx]) {
                            this.badges[idx].classList.add("active");
                            this.badges[idx].innerText = "✓ ACTIVE";
                        }
                    } else {
                        wrap.classList.remove("selected");
                        if (this.badges[idx]) {
                            this.badges[idx].classList.add("active");
                            this.badges[idx].innerText = "SELECT";
                        }
                    }
                } else if (canSelect && !hasMoves) {
                    wrap.classList.add("disabled-die");
                    wrap.classList.remove("selectable", "selected");
                    if (this.badges[idx]) {
                        this.badges[idx].classList.add("active");
                        this.badges[idx].innerText = "NO MOVES";
                    }
                } else {
                    wrap.classList.remove("selectable", "selected");
                    if (this.badges[idx]) {
                        this.badges[idx].classList.remove("active");
                    }
                }
            }
        });
    }

    selectDieIndex(idx, triggerCallback = false) {
        if (!this.twoDiceMode || idx < 0 || idx >= this.currentValues.length) return;
        this.selectedDieIndex = idx;
        const val = this.currentValues[idx];

        this.wrappers.forEach((w, i) => {
            if (w.classList.contains("consumed-die")) return;
            if (i === idx) {
                w.classList.add("selected");
                if (this.badges[i]) this.badges[i].innerText = "✓ ACTIVE";
            } else {
                w.classList.remove("selected");
                if (this.badges[i] && !w.classList.contains("disabled-die")) this.badges[i].innerText = "SELECT";
            }
        });

        if (triggerCallback && this.onDieSelect) {
            this.onDieSelect(val, idx);
        }
    }

    selectDieValue(val) {
        if (!this.wrappers) return;
        for (let i = 0; i < this.wrappers.length; i++) {
            if (this.currentValues[i] === val && !this.wrappers[i].classList.contains("consumed-die")) {
                this.selectDieIndex(i, false);
                return;
            }
        }
        const idx = this.currentValues.indexOf(val);
        if (idx !== -1) {
            this.selectDieIndex(idx, false);
        }
    }

    animateRoll(finalValues, callback) {
        if (this.isRolling) return;
        this.isRolling = true;
        this.setCanRoll(false);
        this.canSelect = false;

        const vals = Array.isArray(finalValues) ? finalValues : [finalValues, Math.floor(Math.random() * 6) + 1];
        this.currentValues = vals;

        if (window.soundEngine) {
            window.soundEngine.playDiceRoll();
        }

        const count = this.twoDiceMode ? 2 : 1;

        for (let i = 0; i < count; i++) {
            const wrap = this.wrappers[i];
            const cube = this.cubes[i];
            const val = vals[i];

            if (!wrap || !cube) continue;
            wrap.classList.add("rolling");

            const turnsX = (Math.floor(Math.random() * 2) + 2) * 360;
            const turnsY = (Math.floor(Math.random() * 2) + 2) * 360 + (i * 90);
            const targetRot = this.faceRotations[val] || { x: 0, y: 0 };

            const finalX = turnsX + targetRot.x;
            const finalY = turnsY + targetRot.y;

            cube.style.transition = "transform 0.85s cubic-bezier(0.2, 0.9, 0.3, 1.15)";
            cube.style.transform = `rotateX(${finalX}deg) rotateY(${finalY}deg)`;
        }

        setTimeout(() => {
            if (window.soundEngine) {
                window.soundEngine.playDiceLand();
            }

            for (let i = 0; i < count; i++) {
                const wrap = this.wrappers[i];
                const cube = this.cubes[i];
                const val = vals[i];
                if (!wrap || !cube) continue;

                wrap.classList.remove("rolling");
                if (this.prompts[i]) {
                    this.prompts[i].innerText = `${val}`;
                    this.prompts[i].classList.add("active");
                }

                const targetRot = this.faceRotations[val] || { x: 0, y: 0 };
                cube.style.transition = "none";
                cube.style.transform = `rotateX(${targetRot.x}deg) rotateY(${targetRot.y}deg)`;
            }

            this.isRolling = false;
            if (callback) callback();
        }, 900);
    }

    showValues(values) {
        if (this.isRolling) return;
        const vals = Array.isArray(values) ? values : [values, values];
        this.currentValues = vals;
        const count = this.twoDiceMode ? 2 : 1;

        for (let i = 0; i < count; i++) {
            const cube = this.cubes[i];
            const val = vals[i] || 1;
            if (!cube) continue;

            const targetRot = this.faceRotations[val] || { x: 0, y: 0 };
            cube.style.transition = "none";
            cube.style.transform = `rotateX(${targetRot.x}deg) rotateY(${targetRot.y}deg)`;
            if (this.prompts[i]) {
                this.prompts[i].innerText = `${val}`;
            }
        }
    }

    showValue(value) {
        if (this.isRolling) return;
        this.showValues([value, value]);
    }
}

window.DiceRoller = DiceRoller;
