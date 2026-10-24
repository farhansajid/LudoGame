/**
 * Real-Time Local Audio Calling Client Engine
 * Implements:
 * 1. WebRTC Mesh Audio for peer-to-peer crystal clear low-latency voice over LAN/loopback.
 * 2. WebSocket Binary PCM Relay as an automatic fallback if WebRTC ICE is restricted.
 * 3. Real-time Voice Activity Detection (VAD) and RMS Speaking Visualizer.
 * 4. Mute / Deafen controls, Push-to-Talk, and individual peer volume control.
 */

class AudioSystem {
    constructor() {
        this.wsClient = null;
        this.roomId = null;
        this.sessionId = null;
        this.playerName = "Player";
        this.playerColor = "red";

        // Media & Web Audio
        this.audioCtx = null;
        this.localStream = null;
        this.micSource = null;
        this.micGain = null;
        this.micAnalyser = null;
        this.analyserData = null;

        // Settings & State
        this.isMuted = false;
        this.isDeafened = false;
        this.isPushToTalk = false;
        this.isPttActive = false;
        this.isSpeaking = false;
        this.isCallActive = false;
        this.micVolume = 1.0;
        this.masterVolume = 1.0;
        this.peerVolumes = {}; // sessionId -> volume float (0.0 .. 2.0)

        // WebRTC Peers: sessionId -> { pc: RTCPeerConnection, audioEl: HTMLAudioElement, gainNode: GainNode }
        this.peers = {};
        this.roster = new Map(); // sessionId -> peer data

        // WebSocket Binary Audio Relay Fallback
        this.useWsRelayFallback = false;
        this.pcmProcessorNode = null;
        this.nextPlaybackTime = 0;

        // Call Modes: 'conference' (all players) vs 'individual' (1-on-1 private call)
        this.callMode = "conference";
        this.activePrivatePartnerSid = null;
        this.onIncomingCall = null; // (callerSid, callerName, callerColor) => {}
        this.onPrivateCallConnected = null; // (peerSid, peerName, peerColor) => {}
        this.onCallDeclined = null; // (targetSid) => {}
        this.onPrivateCallEnded = null; // () => {}

        // Callbacks for UI updates
        this.onSpeakingChange = null; // (sessionId, isSpeaking, level) => {}
        this.onPeerStateChange = null; // (sessionId, state) => {}
        this.onRosterUpdate = null; // (peers) => {}
        this.onError = null; // (errorMsg) => {}

        // Animation frame for VAD & visualizer
        this.vadAnimFrame = null;
        this.lastSpeakingNotify = 0;

        this._setupShortcuts();
    }

    _ensureAudioContext() {
        if (!this.audioCtx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) this.audioCtx = new AudioCtx();
        }
        if (this.audioCtx && this.audioCtx.state === "suspended") {
            this.audioCtx.resume();
        }
        return this.audioCtx;
    }

    _setupShortcuts() {
        window.addEventListener("keydown", (e) => {
            // Push-to-Talk via Space or 'T' key when enabled and not typing in chat input
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

            if (this.isPushToTalk && (e.code === "Space" || e.key === "t" || e.key === "T")) {
                if (!this.isPttActive) {
                    this.isPttActive = true;
                    this._updateMicState();
                }
            }
        });

        window.addEventListener("keyup", (e) => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

            if (this.isPushToTalk && (e.code === "Space" || e.key === "t" || e.key === "T")) {
                if (this.isPttActive) {
                    this.isPttActive = false;
                    this._updateMicState();
                }
            }
        });
    }

    setNetworkClient(wsClient) {
        this.wsClient = wsClient;
    }

    async joinCall(roomId, playerName, color) {
        this.roomId = roomId;
        this.playerName = playerName;
        this.playerColor = color;
        this._ensureAudioContext();

        // Check if mediaDevices API is available (requires Secure Context / HTTPS / localhost)
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            const isPlainHttpLan = !window.isSecureContext && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1";
            const errMsg = isPlainHttpLan
                ? "Microphone requires HTTPS or localhost in modern browsers. Playing in listen mode."
                : "Microphone hardware not available on this device. Playing in listen mode.";
            console.warn(errMsg);
            if (this.onError) {
                this.onError(errMsg);
            }
            this._initListenOnly();
            this.isCallActive = true;
            if (this.wsClient && this.wsClient.isOpen()) {
                this.wsClient.send({
                    type: "audio_join",
                    room_id: this.roomId,
                    player_name: this.playerName,
                    color: this.playerColor
                });
            }
            return false;
        }

        try {
            // Request microphone access
            this.localStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                },
                video: false
            });

            this._initWebAudio();
            this.isCallActive = true;

            // Notify server of audio join
            if (this.wsClient && this.wsClient.isOpen()) {
                this.wsClient.send({
                    type: "audio_join",
                    room_id: this.roomId,
                    player_name: this.playerName,
                    color: this.playerColor
                });
            }

            if (window.soundEngine) {
                window.soundEngine.playAudioBeep(true);
            }

            this._startVadLoop();
            return true;
        } catch (err) {
            console.warn("Microphone access denied or unavailable:", err);
            if (this.onError) {
                this.onError("Microphone access denied. You can still listen and play!");
            }
            // Allow listening even without local mic
            this._initListenOnly();
            this.isCallActive = true;
            if (this.wsClient && this.wsClient.isOpen()) {
                this.wsClient.send({
                    type: "audio_join",
                    room_id: this.roomId,
                    player_name: this.playerName,
                    color: this.playerColor
                });
            }
            return false;
        }
    }

    _initWebAudio() {
        this._ensureAudioContext();

        if (this.localStream && this.localStream.getAudioTracks().length > 0) {
            this.micSource = this.audioCtx.createMediaStreamSource(this.localStream);
            this.micGain = this.audioCtx.createGain();
            this.micAnalyser = this.audioCtx.createAnalyser();

            this.micAnalyser.fftSize = 256;
            this.analyserData = new Uint8Array(this.micAnalyser.frequencyBinCount);

            this.micSource.connect(this.micGain);
            this.micGain.connect(this.micAnalyser);
            // Notice: micAnalyser does NOT connect to destination to avoid local feedback loop!

            // Setup WebSocket PCM relay fallback processor
            this._setupPcmRelayProcessor();
        }
    }

    _initListenOnly() {
        if (!this.audioCtx) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            this.audioCtx = new AudioCtx();
        }
    }

    _setupPcmRelayProcessor() {
        if (!this.audioCtx || !this.micGain) return;
        try {
            // Fallback script processor for binary audio relay
            const bufferSize = 2048;
            this.pcmProcessorNode = this.audioCtx.createScriptProcessor(bufferSize, 1, 1);
            this.pcmProcessorNode.onaudioprocess = (e) => {
                // Clear output buffer to eliminate any local feedback howling
                const outputData = e.outputBuffer.getChannelData(0);
                outputData.fill(0);

                if (!this.useWsRelayFallback || this.isMuted || (this.isPushToTalk && !this.isPttActive)) {
                    return;
                }
                const inputData = e.inputBuffer.getChannelData(0);
                // Downsample or compress to Int16 PCM
                const pcm16 = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                if (this.wsClient && this.wsClient.isOpen()) {
                    this.wsClient.sendBinary(pcm16.buffer);
                }
            };

            // Connect through a silent GainNode to keep processor active without speaker output
            const silentGain = this.audioCtx.createGain();
            silentGain.gain.value = 0;
            this.micGain.connect(this.pcmProcessorNode);
            this.pcmProcessorNode.connect(silentGain);
            silentGain.connect(this.audioCtx.destination);
        } catch (e) {
            console.warn("Could not create ScriptProcessorNode for audio relay:", e);
        }
    }

    _startVadLoop() {
        const checkVad = () => {
            if (!this.isCallActive) return;

            if (this.micAnalyser && this.analyserData) {
                this.micAnalyser.getByteTimeDomainData(this.analyserData);

                // Compute RMS volume
                let sum = 0;
                for (let i = 0; i < this.analyserData.length; i++) {
                    const val = (this.analyserData[i] - 128) / 128.0;
                    sum += val * val;
                }
                const rms = Math.sqrt(sum / this.analyserData.length);

                // Live VU meter update in Audio Settings modal if open
                const meterBar = document.getElementById("mic-test-meter-fill");
                const meterText = document.getElementById("mic-meter-text");
                if (meterBar) {
                    const pct = Math.min(100, Math.round(rms * 350));
                    meterBar.style.width = `${pct}%`;
                    if (meterText) meterText.innerText = `${pct}%`;
                }

                const effectivelyMuted = this.isMuted || (this.isPushToTalk && !this.isPttActive);
                const speakingNow = !effectivelyMuted && rms > 0.035;

                if (speakingNow !== this.isSpeaking) {
                    this.isSpeaking = speakingNow;
                    const now = Date.now();
                    if (now - this.lastSpeakingNotify > 100) {
                        this.lastSpeakingNotify = now;
                        if (this.wsClient && this.wsClient.isOpen()) {
                            this.wsClient.send({
                                type: "audio_speaking",
                                room_id: this.roomId,
                                is_speaking: this.isSpeaking
                            });
                        }
                    }
                    if (this.onSpeakingChange) {
                        this.onSpeakingChange("local", this.isSpeaking, rms);
                    }
                } else if (this.isSpeaking && this.onSpeakingChange) {
                    this.onSpeakingChange("local", true, rms);
                }
            }

            this.vadAnimFrame = requestAnimationFrame(checkVad);
        };
        this.vadAnimFrame = requestAnimationFrame(checkVad);
    }

    // --- Handling Incoming Audio Signaling Messages ---
    async handleSignalingMessage(data) {
        const msgType = data.type;

        if (msgType === "audio_roster") {
            const peers = data.peers || [];
            this.roster.clear();
            for (const p of peers) {
                this.roster.set(p.session_id, p);
            }
            if (this.onRosterUpdate) {
                this.onRosterUpdate(Array.from(this.roster.values()));
            }
            // Initiate WebRTC peer connection to each existing peer
            for (const peer of peers) {
                if (peer.session_id !== this.sessionId && !this.peers[peer.session_id]) {
                    await this._createPeerConnection(peer.session_id, true);
                }
            }
        } else if (msgType === "audio_peer_joined") {
            const peer = data.peer;
            this.roster.set(peer.session_id, peer);
            if (this.onRosterUpdate) {
                this.onRosterUpdate(Array.from(this.roster.values()));
            }
            if (peer.session_id !== this.sessionId && !this.peers[peer.session_id]) {
                await this._createPeerConnection(peer.session_id, false);
            }
        } else if (msgType === "audio_peer_left") {
            this.roster.delete(data.session_id);
            if (this.onRosterUpdate) {
                this.onRosterUpdate(Array.from(this.roster.values()));
            }
            this._removePeer(data.session_id);
        } else if (msgType === "audio_offer") {
            await this._handleOffer(data);
        } else if (msgType === "audio_answer") {
            await this._handleAnswer(data);
        } else if (msgType === "audio_candidate") {
            await this._handleCandidate(data);
        } else if (msgType === "audio_peer_speaking") {
            if (this.onSpeakingChange) {
                this.onSpeakingChange(data.session_id, data.is_speaking, data.is_speaking ? 0.5 : 0.0);
            }
        } else if (msgType === "audio_peer_state") {
            if (this.onPeerStateChange) {
                this.onPeerStateChange(data.session_id, {
                    is_muted: data.is_muted,
                    is_deafened: data.is_deafened
                });
            }
        } else if (msgType === "audio_call_incoming") {
            if (this.onIncomingCall) {
                this.onIncomingCall(data.caller_session_id, data.caller_name, data.caller_color);
            }
        } else if (msgType === "audio_call_connected") {
            this.callMode = "individual";
            this.activePrivatePartnerSid = data.peer_session_id;
            this._updateAllPeerVolumes();
            if (this.onPrivateCallConnected) {
                this.onPrivateCallConnected(data.peer_session_id, data.peer_name, data.peer_color);
            }
        } else if (msgType === "audio_call_declined") {
            if (this.onCallDeclined) {
                this.onCallDeclined(data.target_session_id);
            }
        } else if (msgType === "audio_call_ended") {
            this._onPrivateCallEnded();
        }
    }

    // --- WebRTC Peer Connection Logic ---
    async _createPeerConnection(targetSessionId, isInitiator) {
        if (this.peers[targetSessionId]) return this.peers[targetSessionId];

        // Local LAN WebRTC ICE config (local host candidates allow direct LAN p2p without STUN)
        const config = {
            iceServers: [
                { urls: "stun:stun.l.google.com:19302" } // Fallback for internet play
            ]
        };

        const pc = new RTCPeerConnection(config);
        const peerObj = {
            sessionId: targetSessionId,
            pc: pc,
            audioEl: null,
            gainNode: null,
            pendingCandidates: []
        };
        this.peers[targetSessionId] = peerObj;

        // Add local audio tracks if available
        if (this.localStream) {
            this.localStream.getAudioTracks().forEach(track => {
                pc.addTrack(track, this.localStream);
            });
        }

        // ICE candidate exchange
        pc.onicecandidate = (event) => {
            if (event.candidate && this.wsClient && this.wsClient.isOpen()) {
                this.wsClient.send({
                    type: "audio_candidate",
                    room_id: this.roomId,
                    target_session_id: targetSessionId,
                    candidate: event.candidate
                });
            }
        };

        // Remote track received
        pc.ontrack = (event) => {
            const remoteStream = event.streams[0] || new MediaStream([event.track]);
            this._setupRemoteAudio(targetSessionId, remoteStream);
        };

        pc.oniceconnectionstatechange = () => {
            if (pc.iceConnectionState === "failed" || pc.iceConnectionState === "disconnected") {
                console.log(`WebRTC connection with ${targetSessionId} in state ${pc.iceConnectionState}. Fallback available.`);
                this.useWsRelayFallback = true;
            }
        };

        if (isInitiator) {
            try {
                const offer = await pc.createOffer({
                    offerToReceiveAudio: true
                });
                await pc.setLocalDescription(offer);

                if (this.wsClient && this.wsClient.isOpen()) {
                    this.wsClient.send({
                        type: "audio_offer",
                        room_id: this.roomId,
                        target_session_id: targetSessionId,
                        sdp: pc.localDescription
                    });
                }
            } catch (err) {
                console.warn("Error creating WebRTC offer:", err);
                this.useWsRelayFallback = true;
            }
        }

        return peerObj;
    }

    async _handleOffer(data) {
        const senderId = data.sender_session_id;
        const peerObj = await this._createPeerConnection(senderId, false);
        const pc = peerObj.pc;

        try {
            await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));

            // Drain queued ICE candidates
            if (peerObj.pendingCandidates && peerObj.pendingCandidates.length > 0) {
                for (const cand of peerObj.pendingCandidates) {
                    try {
                        await pc.addIceCandidate(new RTCIceCandidate(cand));
                    } catch (e) {
                        console.warn("Error adding queued ICE candidate:", e);
                    }
                }
                peerObj.pendingCandidates = [];
            }

            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);

            if (this.wsClient && this.wsClient.isOpen()) {
                this.wsClient.send({
                    type: "audio_answer",
                    room_id: this.roomId,
                    target_session_id: senderId,
                    sdp: pc.localDescription
                });
            }
        } catch (err) {
            console.warn("Error handling WebRTC offer:", err);
            this.useWsRelayFallback = true;
        }
    }

    async _handleAnswer(data) {
        const senderId = data.sender_session_id;
        const peerObj = this.peers[senderId];
        if (peerObj && peerObj.pc) {
            try {
                await peerObj.pc.setRemoteDescription(new RTCSessionDescription(data.sdp));

                // Drain queued ICE candidates
                if (peerObj.pendingCandidates && peerObj.pendingCandidates.length > 0) {
                    for (const cand of peerObj.pendingCandidates) {
                        try {
                            await peerObj.pc.addIceCandidate(new RTCIceCandidate(cand));
                        } catch (e) {
                            console.warn("Error adding queued ICE candidate:", e);
                        }
                    }
                    peerObj.pendingCandidates = [];
                }
            } catch (err) {
                console.warn("Error setting remote answer:", err);
            }
        }
    }

    async _handleCandidate(data) {
        const senderId = data.sender_session_id;
        const peerObj = this.peers[senderId];
        if (peerObj && peerObj.pc && data.candidate) {
            if (!peerObj.pc.remoteDescription) {
                peerObj.pendingCandidates.push(data.candidate);
            } else {
                try {
                    await peerObj.pc.addIceCandidate(new RTCIceCandidate(data.candidate));
                } catch (err) {
                    console.warn("Error adding ICE candidate:", err);
                }
            }
        }
    }

    _setupRemoteAudio(sessionId, stream) {
        let peerObj = this.peers[sessionId];
        if (!peerObj) return;

        let audioEl = document.getElementById(`audio-peer-${sessionId}`);
        if (!audioEl) {
            audioEl = document.createElement("audio");
            audioEl.id = `audio-peer-${sessionId}`;
            audioEl.autoplay = true;
            audioEl.playsInline = true;
            document.body.appendChild(audioEl);
        }

        audioEl.srcObject = stream;
        peerObj.audioEl = audioEl;
        this._updatePeerVolume(sessionId);
    }

    _removePeer(sessionId) {
        const peerObj = this.peers[sessionId];
        if (peerObj) {
            if (peerObj.pc) {
                peerObj.pc.close();
            }
            if (peerObj.audioEl) {
                peerObj.audioEl.srcObject = null;
                peerObj.audioEl.remove();
            }
            delete this.peers[sessionId];
        }
        if (sessionId === this.activePrivatePartnerSid) {
            this._onPrivateCallEnded();
        }
        if (this.onSpeakingChange) {
            this.onSpeakingChange(sessionId, false, 0);
        }
    }

    // --- Binary PCM Relay Playback (Fallback) ---
    playBinaryAudioFrame(arrayBuffer) {
        if (this.isDeafened) return;
        const ctx = this._ensureAudioContext();
        if (!ctx) return;

        const int16 = new Int16Array(arrayBuffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768.0;
        }

        const buffer = this.audioCtx.createBuffer(1, float32.length, this.audioCtx.sampleRate);
        buffer.getChannelData(0).set(float32);

        const source = this.audioCtx.createBufferSource();
        source.buffer = buffer;

        const gainNode = this.audioCtx.createGain();
        gainNode.gain.value = this.masterVolume;

        source.connect(gainNode);
        gainNode.connect(this.audioCtx.destination);

        const now = this.audioCtx.currentTime;
        if (this.nextPlaybackTime < now) {
            this.nextPlaybackTime = now;
        }
        source.start(this.nextPlaybackTime);
        this.nextPlaybackTime += buffer.duration;
    }

    // --- Audio Control Functions ---
    toggleMute() {
        this.isMuted = !this.isMuted;
        this._updateMicState();
        if (window.soundEngine) {
            window.soundEngine.playAudioBeep(!this.isMuted);
        }
        this._broadcastMuteState();
        return this.isMuted;
    }

    toggleDeafen() {
        this.isDeafened = !this.isDeafened;
        // When deafened, also automatically mute
        if (this.isDeafened) {
            this.isMuted = true;
        }
        this._updateMicState();
        this._updateAllPeerVolumes();
        if (window.soundEngine) {
            window.soundEngine.playAudioBeep(!this.isDeafened);
        }
        this._broadcastMuteState();
        return this.isDeafened;
    }

    setPushToTalk(enabled) {
        this.isPushToTalk = enabled;
        this._updateMicState();
    }

    setMasterVolume(vol) {
        this.masterVolume = Math.max(0, Math.min(2.0, vol));
        this._updateAllPeerVolumes();
    }

    setPeerVolume(sessionId, vol) {
        this.peerVolumes[sessionId] = Math.max(0, Math.min(2.0, vol));
        this._updatePeerVolume(sessionId);
    }

    _updateMicState() {
        const enabled = !this.isMuted && (!this.isPushToTalk || this.isPttActive);
        if (this.localStream) {
            this.localStream.getAudioTracks().forEach(track => {
                track.enabled = enabled;
            });
        }
        if (this.micGain) {
            this.micGain.gain.value = enabled ? this.micVolume : 0.0;
        }
    }

    _updatePeerVolume(sessionId) {
        const peer = this.peers[sessionId];
        if (peer && peer.audioEl) {
            // If in 1-on-1 private call, silence peers other than the private call partner
            if (this.callMode === "individual" && this.activePrivatePartnerSid && sessionId !== this.activePrivatePartnerSid) {
                peer.audioEl.volume = 0.0;
                return;
            }
            const peerVol = this.peerVolumes[sessionId] !== undefined ? this.peerVolumes[sessionId] : 1.0;
            const effectiveVol = this.isDeafened ? 0.0 : Math.min(1.0, peerVol * this.masterVolume);
            peer.audioEl.volume = effectiveVol;
        }
    }

    _updateAllPeerVolumes() {
        for (const sid of Object.keys(this.peers)) {
            this._updatePeerVolume(sid);
        }
    }

    // --- Individual 1-on-1 Private Call Controls ---
    requestIndividualCall(targetSessionId) {
        if (this.wsClient && this.wsClient.isOpen()) {
            this.wsClient.send({
                type: "audio_call_request",
                room_id: this.roomId,
                target_session_id: targetSessionId
            });
        }
    }

    acceptIndividualCall(callerSessionId) {
        if (this.wsClient && this.wsClient.isOpen()) {
            this.wsClient.send({
                type: "audio_call_accept",
                room_id: this.roomId,
                caller_session_id: callerSessionId
            });
        }
    }

    declineIndividualCall(callerSessionId) {
        if (this.wsClient && this.wsClient.isOpen()) {
            this.wsClient.send({
                type: "audio_call_decline",
                room_id: this.roomId,
                caller_session_id: callerSessionId
            });
        }
    }

    endIndividualCall() {
        if (this.wsClient && this.wsClient.isOpen()) {
            this.wsClient.send({
                type: "audio_call_end",
                room_id: this.roomId
            });
        }
        this._onPrivateCallEnded();
    }

    setCallMode(mode) {
        if (mode === "conference" && this.callMode === "individual") {
            this.endIndividualCall();
        }
        this.callMode = mode;
        this._updateAllPeerVolumes();
    }

    _onPrivateCallEnded() {
        this.callMode = "conference";
        this.activePrivatePartnerSid = null;
        this._updateAllPeerVolumes();
        if (this.onPrivateCallEnded) {
            this.onPrivateCallEnded();
        }
    }

    _broadcastMuteState() {
        if (this.wsClient && this.wsClient.isOpen()) {
            this.wsClient.send({
                type: "audio_mute",
                room_id: this.roomId,
                is_muted: this.isMuted,
                is_deafened: this.isDeafened
            });
        }
    }

    leaveCall() {
        this.isCallActive = false;
        if (this.vadAnimFrame) {
            cancelAnimationFrame(this.vadAnimFrame);
        }
        if (this.localStream) {
            this.localStream.getTracks().forEach(t => t.stop());
            this.localStream = null;
        }
        for (const sid of Object.keys(this.peers)) {
            this._removePeer(sid);
        }
        if (this.wsClient && this.wsClient.isOpen()) {
            this.wsClient.send({
                type: "audio_leave",
                room_id: this.roomId
            });
        }
    }
}

window.audioSystem = new AudioSystem();
