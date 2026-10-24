# 🌐 Royal Ludo: Internet Deployment & Android Publishing Guide

Comprehensive, production-ready handbook for deploying Royal Ludo over the public Internet with WebRTC audio calling (conference & 1-on-1 private calls) and publishing the game as an Android application on the Google Play Store.

---

## 📑 Table of Contents
1. [Internet Multiplayer Server Deployment](#1-internet-multiplayer-server-deployment)
   - [Architecture Overview](#architecture-overview)
   - [Server Provisioning (Ubuntu VPS)](#server-provisioning-ubuntu-vps)
   - [Systemd Production Service](#systemd-production-service)
   - [Nginx Reverse Proxy & WebSocket Configuration](#nginx-reverse-proxy--websocket-configuration)
   - [Let's Encrypt Free SSL/TLS Certificates](#lets-encrypt-free-ssltls-certificates)
   - [Docker & Docker-Compose Deployment](#docker--docker-compose-deployment)
2. [WebRTC Audio Calling (Conference & Individual Calls)](#2-webrtc-audio-calling-conference--individual-calls)
   - [Understanding NAT Traversal & STUN/TURN](#understanding-nat-traversal--stunturn)
   - [Coturn TURN Server Installation & Configuration](#coturn-turn-server-installation--configuration)
   - [Firewall & Cloud Security Groups](#firewall--cloud-security-groups)
   - [Client WebRTC Configuration (audio_system.js)](#client-webrtc-configuration-audio_systemjs)
   - [Managed TURN Alternatives](#managed-turn-alternatives)
3. [Android App Packaging & Google Play Store Publishing](#3-android-app-packaging--google-play-store-publishing)
   - [Capacitor Setup & Architecture](#capacitor-setup--architecture)
   - [AndroidManifest.xml Audio & Network Permissions](#androidmanifestxml-audio--network-permissions)
   - [Android WebView WebRTC Microphone Permission Handling](#android-webview-webrtc-microphone-permission-handling)
   - [Adaptive Icons & Splash Screens](#adaptive-icons--splash-screens)
   - [Release Keystore Generation](#release-keystore-generation)
   - [Building the Production Android App Bundle (.aab)](#building-the-production-android-app-bundle-aab)
   - [Google Play Console Setup & Data Safety Declaration](#google-play-console-setup--data-safety-declaration)

---

## 1. Internet Multiplayer Server Deployment

### Architecture Overview
The game architecture consists of:
- **Backend Core**: Python 3.11 with `aiohttp` running the asynchronous Game Engine, Bot AI heuristics, and Audio Signaling Relay.
- **Frontend Client**: Vanilla JavaScript ES6+, HTML5 Canvas high-DPI board renderer, Web Audio sound engine, and WebRTC audio peer mesh.
- **Reverse Proxy**: Nginx handling HTTPS/SSL termination, HTTP/2 multiplexing, WebSocket protocol upgrading (`/ws`), and static asset caching.
- **NAT Traversal**: Coturn STUN/TURN server providing UDP relay when players connect across restrictive symmetric NATs or mobile cellular networks (4G/5G).

```
   [ Web Browser / Android App ]
                 │
       HTTPS / WSS (Port 443)
                 ▼
       ┌───────────────────┐
       │   Nginx Proxy     │ (Certbot SSL / Let's Encrypt)
       └─────────┬─────────┘
                 │ Proxy Pass (HTTP / WS to localhost:8080)
                 ▼
       ┌───────────────────┐        ┌───────────────────┐
       │ Python aiohttp    │◄──────►│ Coturn STUN/TURN  │
       │ Game Engine & WS  │        │ (UDP Ports 3478,  │
       │ (Port 8080)       │        │  49152 - 65535)   │
       └───────────────────┘        └───────────────────┘
```

> [!IMPORTANT]
> **HTTPS is strictly required for WebRTC audio.** Modern mobile browsers (Chrome, Safari, Edge) block `navigator.mediaDevices.getUserMedia` when loaded over plain `http://` on any address other than `localhost` or `127.0.0.1`. You must bind an SSL certificate to your domain.

---

### Server Provisioning (Ubuntu VPS)
1. Launch an Ubuntu 22.04 or 24.04 LTS instance (1 vCPU, 2GB RAM minimum on AWS EC2, DigitalOcean, Hetzner, or Linode).
2. Point your DNS domain `A` record (e.g. `ludo.yourdomain.com`) to your VPS public IPv4 address.
3. SSH into your server and install runtime dependencies:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git certbot python3-certbot-nginx
```

4. Clone the repository and configure Python virtual environment:

```bash
cd /opt
sudo git clone https://github.com/your-username/royal-ludo.git
sudo chown -R ubuntu:ubuntu /opt/royal-ludo
cd /opt/royal-ludo

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Systemd Production Service
Create a persistent systemd service so Royal Ludo starts on boot and automatically restarts on crashes:

```bash
sudo nano /etc/systemd/system/ludo.service
```

Paste the following service definition:

```ini
[Unit]
Description=Royal Ludo Multiplayer Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/royal-ludo
Environment="PATH=/opt/royal-ludo/venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/royal-ludo/venv/bin/python main.py --host 127.0.0.1 --port 8080
Restart=always
RestartSec=3
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ludo.service
sudo systemctl start ludo.service
sudo systemctl status ludo.service
```

---

### Nginx Reverse Proxy & WebSocket Configuration
Create an Nginx server block configured for WebSocket connection upgrading and static asset delivery:

```bash
sudo nano /etc/nginx/sites-available/ludo
```

Paste the following configuration (replace `ludo.yourdomain.com` with your actual domain):

```nginx
server {
    listen 80;
    server_name ludo.yourdomain.com;

    # Redirect all plain HTTP traffic to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ludo.yourdomain.com;

    # SSL certificates managed by Certbot will be inserted here

    access_log /var/log/nginx/ludo.access.log;
    error_log  /var/log/nginx/ludo.error.log;

    client_max_body_size 20M;

    # WebSocket Endpoint (/ws)
    location /ws {
        proxy_pass http://127.0.0.1:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # REST APIs and HTTP requests
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Cache static asset files for high performance
    location /static/ {
        alias /opt/royal-ludo/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }
}
```

Enable the site configuration and test:

```bash
sudo ln -s /etc/nginx/sites-available/ludo /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

### Let's Encrypt Free SSL/TLS Certificates
Issue free, automatically renewing certificates using Certbot:

```bash
sudo certbot --nginx -d ludo.yourdomain.com
```

Select the option to automatically configure SSL settings. Verify that auto-renewal is enabled:

```bash
sudo systemctl status certbot.timer
```

Now visiting `https://ludo.yourdomain.com` will serve Royal Ludo under a verified SSL certificate with microphone permissions fully unlocked!

---

### Docker & Docker-Compose Deployment
If you prefer containerized deployment, create a `Dockerfile` and `docker-compose.yml`:

**`Dockerfile`**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8080"]
```

**`docker-compose.yml`**:
```yaml
version: '3.8'

services:
  ludo-app:
    build: .
    restart: always
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      - PYTHONUNBUFFERED=1
```

Start the container stack:
```bash
docker compose up -d
```

---

## 2. WebRTC Audio Calling (Conference & Individual Calls)

### Understanding NAT Traversal & STUN/TURN
- **STUN (Session Traversal Utilities for NAT)**: Discovers the client's public IP and port. Works for ~80% of consumer residential connections (Full Cone, Restricted Cone).
- **TURN (Traversal Using Relays around NAT)**: Acts as a media relay server. Required when players connect via **Symmetric NAT** (typical in mobile 4G/5G carriers, university dorms, office firewalls, and public hotspots). Without a TURN server, voice calls will fail between mobile cellular players.

Royal Ludo supports both:
1. **Conference Voice**: All participants hear each other with spatial voice activity indicators.
2. **1-on-1 Individual Calls**: Two players engage in private audio dialogue; audio packets are strictly isolated to those two participants, while non-participants are muted.

---

### Coturn TURN Server Installation & Configuration
Install Coturn on your Ubuntu server:

```bash
sudo apt install -y coturn
```

Enable Coturn as an automatic system service:
Edit `/etc/default/coturn` and uncomment:
```ini
TURNSERVER_ENABLED=1
```

Edit `/etc/turnserver.conf`:
```bash
sudo nano /etc/turnserver.conf
```

Add the following production configuration:

```ini
# Listening ports
listening-port=3478
tls-listening-port=5349

# Realm and domain
realm=yourdomain.com
server-name=turn.yourdomain.com

# Public IP address of your VPS
external-ip=YOUR_SERVER_PUBLIC_IPV4

# Relay UDP port range for media streams
min-port=49152
max-port=65535

# Authentication credentials (Long-term credential mechanism)
lt-cred-mech
user=ludo_voice_user:UltraSecurePassword123!

# Security & logging
fingerprint
no-cli
no-tcp-relay
verbose
log-file=/var/log/turnserver/turnserver.log
```

Create the log directory, restart, and enable Coturn:

```bash
sudo mkdir -p /var/log/turnserver
sudo chown turnserver:turnserver /var/log/turnserver
sudo systemctl restart coturn
sudo systemctl enable coturn
```

---

### Firewall & Cloud Security Groups
Ensure the following ports are open in `ufw` and in your cloud provider's firewall (AWS Security Group, DigitalOcean Firewall, Hetzner Firewall):

| Port / Protocol | Service | Direction | Purpose |
|-----------------|---------|-----------|---------|
| `80/tcp` | HTTP | Inbound | Nginx & Certbot verification |
| `443/tcp` | HTTPS | Inbound | Web game & WebSocket (`/ws`) |
| `3478/tcp & udp` | STUN/TURN | Inbound | Coturn standard listening port |
| `5349/tcp & udp` | TURNS (TLS) | Inbound | Secure encrypted TURN |
| `49152-65535/udp` | Media Relay | Inbound | WebRTC audio relay streaming |

Commands for `ufw`:
```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp
sudo ufw allow 5349/tcp
sudo ufw allow 5349/udp
sudo ufw allow 49152:65535/udp
sudo ufw enable
```

---

### Client WebRTC Configuration (audio_system.js)
Open `static/js/audio_system.js` and update the `iceServers` configuration inside `_createPeerConnection()`:

```javascript
const peerConfig = {
    iceServers: [
        // Public STUN server (Fast discovery)
        { urls: "stun:stun.l.google.com:19302" },
        // Your private production Coturn TURN server
        {
            urls: [
                "turn:turn.yourdomain.com:3478",
                "turn:turn.yourdomain.com:3478?transport=tcp"
            ],
            username: "ludo_voice_user",
            credential: "UltraSecurePassword123!"
        }
    ],
    iceCandidatePoolSize: 4
};
```

---

### Managed TURN Alternatives
If you do not wish to operate and maintain Coturn:
- **Twilio Network Traversal Service**: Highly reliable global TURN infrastructure.
- **Metered.ca TURN**: Free tier provides 50GB/month of TURN bandwidth.
- **Xirsys**: Turnkey WebRTC TURN provider with low-latency geolocated servers.

---

## 3. Android App Packaging & Google Play Store Publishing

### Capacitor Setup & Architecture
The modern, Google-recommended method to package a web application into an Android native APK/AAB is **Capacitor** (by Ionic). It maintains direct access to hardware APIs and WebRTC WebViews without deprecated Cordova wrappers.

#### Step 1: Install Node.js & Capacitor CLI
On your local development machine:

```bash
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap init "Royal Ludo" "com.royalludo.app" --web-dir static
```

#### Step 2: Configure `capacitor.config.json`
To allow the Android app to connect to your live cloud multiplayer server while serving UI assets, configure `capacitor.config.json`:

```json
{
  "appId": "com.royalludo.app",
  "appName": "Royal Ludo",
  "webDir": "static",
  "bundledWebRuntime": false,
  "server": {
    "url": "https://ludo.yourdomain.com",
    "cleartext": false,
    "allowNavigation": [
      "ludo.yourdomain.com"
    ]
  },
  "android": {
    "allowMixedContent": false,
    "webContentsDebuggingEnabled": false
  }
}
```

#### Step 3: Add Android Platform
```bash
npx cap add android
```
This generates the native Android Studio project in the `android/` directory.

---

### AndroidManifest.xml Audio & Network Permissions
Open `android/app/src/main/AndroidManifest.xml` and insert the necessary permissions inside the `<manifest>` tag:

```xml
<!-- Internet & Network State for Multiplayer WebSockets -->
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />

<!-- Microphone and Audio Hardware for Real-Time Calling -->
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />
<uses-permission android:name="android.permission.WAKE_LOCK" />

<!-- Declare microphone as optional so users without mics can still install -->
<uses-feature android:name="android.hardware.microphone" android:required="false" />
```

---

### Android WebView WebRTC Microphone Permission Handling
Android WebViews do not automatically grant microphone permissions to `getUserMedia()` calls even if the app holds `RECORD_AUDIO`. You must intercept `onPermissionRequest` in your `MainActivity.java`:

Open `android/app/src/main/java/com/royalludo/app/MainActivity.java`:

```java
package com.royalludo.app;

import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Access WebView and grant WebRTC media capture permissions
        WebView webView = this.getBridge().getWebView();
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                // Grant microphone resource request to our verified domain
                MainActivity.this.runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        request.grant(request.getResources());
                    }
                });
            }
        });
    }
}
```

---

### Adaptive Icons & Splash Screens
Install the Capacitor assets generation utility:

```bash
npm install -g @capacitor/assets
```

Provide two high-resolution images in an `assets/` folder:
- `assets/icon.png`: 1024x1024 px (game icon with dice crest)
- `assets/splash.png`: 2732x2732 px (splash screen backdrop)

Generate all Android density icons (mdpi, hdpi, xhdpi, xxhdpi, xxxhdpi):
```bash
npx capacitor-assets generate --android
```

---

### Release Keystore Generation
Generate a cryptographically secure RSA keystore for signing your release builds:

```bash
keytool -genkey -v -keystore royal-ludo-release-key.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias royalludokey
```
Store the keystore and passphrase securely.

In `android/app/build.gradle`, configure the signing configs:

```groovy
android {
    ...
    signingConfigs {
        release {
            storeFile file("royal-ludo-release-key.jks")
            storePassword System.getenv("KEYSTORE_PASSWORD") ?: "YourPassword"
            keyAlias "royalludokey"
            keyPassword System.getenv("KEY_PASSWORD") ?: "YourPassword"
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled true
            shrinkResources true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
}
```

---

### Building the Production Android App Bundle (.aab)
Google Play requires publishing builds in the **Android App Bundle (.aab)** format:

```bash
cd android
./gradlew bundleRelease
```

The resulting signed bundle is output to:
`android/app/build/outputs/bundle/release/app-release.aab`

---

### Google Play Console Setup & Data Safety Declaration

#### 1. Create App on Play Console
1. Navigate to [Google Play Console](https://play.google.com/console).
2. Click **Create App**:
   - App Name: `Royal Ludo: Multiplayer & Voice`
   - Default language: English (United States)
   - App or Game: **Game**
   - Free or Paid: **Free**

#### 2. Store Listing Assets
- **App Icon**: 512 x 512 px PNG (32-bit color).
- **Feature Graphic**: 1024 x 500 px JPG or PNG.
- **Phone Screenshots**: At least 4 screenshots (16:9 or 18:9 aspect ratio, e.g., 1080 x 1920 or 1080 x 2400) showing gameplay, 3D dice, audio calling HUD, and board themes.
- **Tablet Screenshots**: At least 1 screenshot for 7-inch and 10-inch tablets.

#### 3. Content Rating (IARC)
Complete the questionnaire:
- Category: Game -> Board / Strategy.
- Violence: None / Cartoon board pieces.
- Online Interactions: **Yes** (Players can communicate via voice chat and text chat).
- Rating Outcome: **PEGI 3 / ESRB Everyone**.

#### 4. Target Audience & Families Policy
- Target age: 13 and older (to comply with simplified voice chat regulations).
- Ads: None.

#### 5. Data Safety Form (Microphone & Voice Privacy)
Google Play requires explicit declarations for apps using `RECORD_AUDIO`:

| Field | Declaration |
|-------|-------------|
| **Does your app collect or share data?** | Yes |
| **Data Type** | Audio recordings (Voice or sound recordings) |
| **Collected or Shared?** | **Collected** (Streamed real-time for in-game multiplayer communication) |
| **Is data processed ephemerally?** | **Yes** (Audio is relayed in real-time between match participants and is NEVER saved to disk or permanent storage) |
| **Is data shared with third parties?** | **No** (Direct WebRTC peer-to-peer or private room relay only) |
| **Purpose** | App Functionality (In-game voice communication) |
| **Security Practices** | Data is encrypted in transit using industry-standard DTLS/SRTP and HTTPS/WSS protocols |
| **Account Deletion** | Users play anonymously or with guest profiles; no permanent accounts required |

#### 6. Privacy Policy
Host a privacy policy at `https://yourdomain.com/privacy` clearly detailing:
> *"Royal Ludo accesses device microphones exclusively to facilitate live, ephemeral in-game voice chat during active multiplayer matches. Audio data is transmitted via encrypted peer-to-peer WebRTC streams or real-time relay buffers. Audio recordings are never recorded, transcribed, stored, or sold."*

#### 7. Release Track Deployment
1. Upload your signed `app-release.aab` under **Testing -> Internal testing**.
2. Invite internal testers to verify microphone access on various Android phone models.
3. Advance to **Closed testing** (complete Google's 20-tester requirement for personal developer accounts).
4. Submit for **Production** review. Review typically completes within 24 to 72 hours.
