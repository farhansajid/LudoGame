/**
 * Procedural Web Audio Sound Engine
 * Synthesizes all game sound effects and audio call alerts in real time.
 * Zero external audio files required - 100% reliable offline and online.
 */

class SoundEngine {
    constructor() {
        this.ctx = null;
        this.masterVolume = 0.7;
        this.muted = false;
        this._initOnUserGesture();
    }

    _initOnUserGesture() {
        const unlock = () => {
            if (!this.ctx) {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) {
                    this.ctx = new AudioCtx();
                }
            }
            if (this.ctx && this.ctx.state === "suspended") {
                this.ctx.resume();
            }
            window.removeEventListener("click", unlock);
            window.removeEventListener("keydown", unlock);
            window.removeEventListener("touchstart", unlock);
        };
        window.addEventListener("click", unlock, { once: true });
        window.addEventListener("keydown", unlock, { once: true });
        window.addEventListener("touchstart", unlock, { once: true });
    }

    _ensureContext() {
        if (!this.ctx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
                this.ctx = new AudioCtx();
            }
        }
        if (this.ctx && this.ctx.state === "suspended") {
            this.ctx.resume();
        }
        return this.ctx;
    }

    setMuted(muted) {
        this.muted = muted;
    }

    setVolume(vol) {
        this.masterVolume = Math.max(0, Math.min(1, vol));
    }

    // --- Dice Roll Sound ---
    playDiceRoll() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const count = 7;
        for (let i = 0; i < count; i++) {
            const t = now + (i * 0.04) + (Math.random() * 0.02);
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            const filter = ctx.createBiquadFilter();

            osc.type = "triangle";
            osc.frequency.setValueAtTime(140 + Math.random() * 180, t);
            osc.frequency.exponentialRampToValueAtTime(60, t + 0.05);

            filter.type = "lowpass";
            filter.frequency.setValueAtTime(600, t);

            const vol = (0.2 + (i / count) * 0.25) * this.masterVolume;
            gain.gain.setValueAtTime(vol, t);
            gain.gain.exponentialRampToValueAtTime(0.001, t + 0.06);

            osc.connect(filter);
            filter.connect(gain);
            gain.connect(ctx.destination);

            osc.start(t);
            osc.stop(t + 0.07);
        }
    }

    // --- Dice Land / Impact Sound ---
    playDiceLand() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(220, now);
        osc.frequency.exponentialRampToValueAtTime(80, now + 0.12);

        gain.gain.setValueAtTime(0.4 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + 0.16);
    }

    // --- Pawn Hop Sound ---
    playPawnHop(stepIndex = 0) {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        // Slightly increasing pitch with hop steps
        const baseFreq = 340 + (stepIndex % 6) * 30;
        osc.type = "sine";
        osc.frequency.setValueAtTime(baseFreq, now);
        osc.frequency.exponentialRampToValueAtTime(baseFreq * 1.5, now + 0.05);
        osc.frequency.exponentialRampToValueAtTime(baseFreq * 0.8, now + 0.09);

        gain.gain.setValueAtTime(0.28 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + 0.11);
    }

    // --- Pawn Capture / Knockout Sound ---
    playCapture() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        // Punch impact
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(260, now);
        osc.frequency.exponentialRampToValueAtTime(40, now + 0.25);

        gain.gain.setValueAtTime(0.55 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.32);

        // Slide whistle effect (flying back)
        const slide = ctx.createOscillator();
        const slideGain = ctx.createGain();
        slide.type = "sine";
        slide.frequency.setValueAtTime(700, now + 0.05);
        slide.frequency.exponentialRampToValueAtTime(150, now + 0.4);

        slideGain.gain.setValueAtTime(0.2 * this.masterVolume, now + 0.05);
        slideGain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

        slide.connect(slideGain);
        slideGain.connect(ctx.destination);
        slide.start(now + 0.05);
        slide.stop(now + 0.46);
    }

    // --- Safe Square Chime ---
    playSafeSquare() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const chord = [523.25, 659.25, 783.99]; // C5, E5, G5
        chord.forEach((freq, idx) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, now + idx * 0.04);

            gain.gain.setValueAtTime(0.18 * this.masterVolume, now + idx * 0.04);
            gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.04 + 0.4);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + idx * 0.04);
            osc.stop(now + idx * 0.04 + 0.42);
        });
    }

    // --- Token Released from Yard Sound (Boost or Royal 6) ---
    playTokenRelease(isBoost = false) {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const notes = isBoost
            ? [{ f: 587.33, t: 0.0, d: 0.09 }, { f: 880.00, t: 0.08, d: 0.12 }, { f: 1174.66, t: 0.17, d: 0.28 }]
            : [{ f: 523.25, t: 0.0, d: 0.09 }, { f: 659.25, t: 0.08, d: 0.09 }, { f: 783.99, t: 0.16, d: 0.12 }, { f: 1046.50, t: 0.24, d: 0.32 }];

        notes.forEach(note => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = isBoost ? "sine" : "triangle";
            osc.frequency.setValueAtTime(note.f, now + note.t);

            gain.gain.setValueAtTime((isBoost ? 0.32 : 0.28) * this.masterVolume, now + note.t);
            gain.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + note.t);
            osc.stop(now + note.t + note.d + 0.04);
        });
    }

    // --- Extra / Bonus Turn Chime ---
    playBonusTurn() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const notes = [
            { f: 659.25, t: 0.0, d: 0.08 },
            { f: 783.99, t: 0.07, d: 0.08 },
            { f: 987.77, t: 0.14, d: 0.12 },
            { f: 1318.51, t: 0.22, d: 0.25 }
        ];

        notes.forEach(note => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(note.f, now + note.t);

            gain.gain.setValueAtTime(0.25 * this.masterVolume, now + note.t);
            gain.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + note.t);
            osc.stop(now + note.t + note.d + 0.04);
        });
    }

    // --- Token Reached Goal Fanfare ---
    playGoalReached() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const melody = [
            { f: 440.00, t: 0.0, d: 0.12 },
            { f: 554.37, t: 0.12, d: 0.12 },
            { f: 659.25, t: 0.24, d: 0.12 },
            { f: 880.00, t: 0.36, d: 0.35 }
        ];

        melody.forEach(note => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "triangle";
            osc.frequency.setValueAtTime(note.f, now + note.t);

            gain.gain.setValueAtTime(0.3 * this.masterVolume, now + note.t);
            gain.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + note.t);
            osc.stop(now + note.t + note.d + 0.05);
        });
    }

    // --- Victory Game Over Fanfare ---
    playVictory() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const fanfare = [
            { f: 523.25, t: 0.0, d: 0.15 },
            { f: 523.25, t: 0.15, d: 0.15 },
            { f: 523.25, t: 0.30, d: 0.15 },
            { f: 659.25, t: 0.45, d: 0.30 },
            { f: 587.33, t: 0.75, d: 0.15 },
            { f: 659.25, t: 0.90, d: 0.15 },
            { f: 783.99, t: 1.05, d: 0.55 }
        ];

        fanfare.forEach(note => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "triangle";
            osc.frequency.setValueAtTime(note.f, now + note.t);

            gain.gain.setValueAtTime(0.35 * this.masterVolume, now + note.t);
            gain.gain.exponentialRampToValueAtTime(0.001, now + note.t + note.d);

            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + note.t);
            osc.stop(now + note.t + note.d + 0.05);
        });
    }

    // --- Turn Alert Chime ---
    playTurnAlert() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = "sine";
        osc.frequency.setValueAtTime(587.33, now); // D5
        osc.frequency.setValueAtTime(880.00, now + 0.08); // A5

        gain.gain.setValueAtTime(0.22 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.3);
    }

    // --- Audio Voice Chat Connected / Mic Mute Sound ---
    playAudioBeep(isPositive = true) {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = "sine";
        if (isPositive) {
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.setValueAtTime(660, now + 0.06);
        } else {
            osc.frequency.setValueAtTime(660, now);
            osc.frequency.setValueAtTime(440, now + 0.06);
        }

        gain.gain.setValueAtTime(0.18 * this.masterVolume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.18);
    }

    // --- Escaping Danger Protective Sound ---
    playEscapeDanger() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        // 1. Whoosh / wind rush
        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(280, now);
        osc1.frequency.exponentialRampToValueAtTime(740, now + 0.18);
        gain1.gain.setValueAtTime(0.25 * this.masterVolume, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.24);

        // 2. Chime resonance / shield up
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = "triangle";
        osc2.frequency.setValueAtTime(587.33, now + 0.08); // D5
        osc2.frequency.exponentialRampToValueAtTime(880.00, now + 0.25); // A5
        gain2.gain.setValueAtTime(0.3 * this.masterVolume, now + 0.08);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.08);
        osc2.stop(now + 0.48);
    }

    // --- Six Release Fanfare / Power Burst ---
    playSixRelease() {
        if (this.muted) return;
        const ctx = this._ensureContext();
        if (!ctx) return;

        const now = ctx.currentTime;
        const notes = [
            { f: 523.25, t: 0.0, d: 0.12 }, // C5
            { f: 659.25, t: 0.08, d: 0.14 }, // E5
            { f: 783.99, t: 0.16, d: 0.18 }, // G5
            { f: 1046.50, t: 0.24, d: 0.35 } // C6
        ];
        notes.forEach(n => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(n.f, now + n.t);
            gain.gain.setValueAtTime(0.28 * this.masterVolume, now + n.t);
            gain.gain.exponentialRampToValueAtTime(0.001, now + n.t + n.d);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + n.t);
            osc.stop(now + n.t + n.d + 0.02);
        });
    }
}

// Global singleton instance
window.soundEngine = new SoundEngine();
