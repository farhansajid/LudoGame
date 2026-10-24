/**
 * WebSocket Network Client for Ludo Game & Voice Chat
 * Handles auto-reconnect, JSON signaling, and binary audio streaming.
 */

class NetworkClient {
    constructor() {
        this.ws = null;
        this.url = null;
        this.listeners = {};
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.isExplicitClose = false;
        this.sessionId = null;
        this.sendQueue = [];
    }

    connect(customUrl = null) {
        if (this.isOpen() || (this.ws && this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        if (customUrl) {
            this.url = customUrl;
        } else {
            const loc = window.location;
            const proto = loc.protocol === "https:" ? "wss:" : "ws:";
            this.url = `${proto}//${loc.host}/ws`;
        }

        try {
            this.ws = new WebSocket(this.url);
            this.ws.binaryType = "arraybuffer";

            this.ws.onopen = () => {
                this.reconnectAttempts = 0;
                while (this.sendQueue.length > 0) {
                    const item = this.sendQueue.shift();
                    try {
                        this.ws.send(item);
                    } catch (e) {
                        console.error("Failed to send queued message:", e);
                    }
                }
                this._emit("connect", {});
            };


            this.ws.onmessage = (event) => {
                if (typeof event.data === "string") {
                    try {
                        const data = jsonParseSafe(event.data);
                        if (data && data.type) {
                            if (data.type === "room_joined") {
                                this.sessionId = data.session_id;
                            }
                            this._emit(data.type, data);
                            this._emit("message", data);
                        }
                    } catch (e) {
                        console.error("JSON parse error:", e);
                    }
                } else if (event.data instanceof ArrayBuffer) {
                    // Binary audio frame from WebSocket audio relay
                    if (window.audioSystem) {
                        window.audioSystem.playBinaryAudioFrame(event.data);
                    }
                    this._emit("binary_audio", event.data);
                } else if (event.data instanceof Blob) {
                    event.data.arrayBuffer().then(buf => {
                        if (window.audioSystem) {
                            window.audioSystem.playBinaryAudioFrame(buf);
                        }
                        this._emit("binary_audio", buf);
                    }).catch(err => console.warn("Blob to ArrayBuffer error:", err));
                }
            };

            this.ws.onclose = () => {
                this._emit("disconnect", {});
                if (!this.isExplicitClose && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    const delay = Math.min(5000, 1000 * Math.pow(1.5, this.reconnectAttempts));
                    setTimeout(() => this.connect(), delay);
                }
            };

            this.ws.onerror = (err) => {
                this._emit("error", err);
            };

        } catch (e) {
            console.error("Failed to establish WebSocket connection:", e);
        }

        function jsonParseSafe(str) {
            try { return JSON.parse(str); } catch (e) { return null; }
        }
    }

    isOpen() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    send(data) {
        const jsonStr = JSON.stringify(data);
        if (this.isOpen()) {
            this.ws.send(jsonStr);
        } else {
            this.sendQueue.push(jsonStr);
            if (!this.ws || (this.ws.readyState !== WebSocket.CONNECTING && this.ws.readyState !== WebSocket.OPEN)) {
                this.connect();
            }
        }
    }

    sendBinary(arrayBuffer) {
        if (this.isOpen()) {
            this.ws.send(arrayBuffer);
        } else {
            this.sendQueue.push(arrayBuffer);
            if (!this.ws || (this.ws.readyState !== WebSocket.CONNECTING && this.ws.readyState !== WebSocket.OPEN)) {
                this.connect();
            }
        }
    }


    on(eventType, callback) {
        if (!this.listeners[eventType]) {
            this.listeners[eventType] = [];
        }
        this.listeners[eventType].push(callback);
    }

    off(eventType, callback) {
        if (!this.listeners[eventType]) return;
        this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback);
    }

    _emit(eventType, payload) {
        const handlers = this.listeners[eventType];
        if (handlers) {
            handlers.forEach(fn => {
                try {
                    fn(payload);
                } catch (err) {
                    console.error(`Error in event listener for ${eventType}:`, err);
                }
            });
        }
    }

    close() {
        this.isExplicitClose = true;
        if (this.ws) {
            this.ws.close();
        }
    }
}

window.NetworkClient = NetworkClient;
