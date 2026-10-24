"""
Royal Ludo Game - Main Server Launcher
Starts the authoritative Ludo game server, WebSocket real-time audio calling hub,
and automatically opens the browser for the user.
"""

import argparse
import asyncio
import logging
import os
import sys
import webbrowser
from pathlib import Path

from aiohttp import web
from server.app import create_app, get_local_ip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


# Ensure stdout and stderr handle utf-8 cleanly on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


import ssl

def print_banner(host: str, port: int, local_ip: str, is_ssl: bool = False):
    proto = "https" if is_ssl else "http"
    banner = f"""
======================================================================
  [*]  ROYAL LUDO CHAMPIONSHIP  [*]
  Real-Time Local Audio Calling & Multiplayer System
======================================================================
  Local PC URL:      {proto}://localhost:{port}
  Local LAN / Wi-Fi: {proto}://{local_ip}:{port}

  Features:
  - 2 to 4 Players: Play Solo vs Smart AI, Pass & Play, or LAN
  - Real-Time Audio Calling (WebRTC P2P + Binary Relay Fallback)
  - Live Voice Visualizer & Speaking Rings
  - 3D Tumbling Animated Dice
  - 3 Luxury Board Themes (Royal Wood, Cyber Neon, Emerald Marble)
  - Win Celebration, Confetti & Sound Effects
======================================================================
  Press Ctrl+C to stop the server anytime.
======================================================================
"""
    try:
        print(banner)
    except Exception:
        print(banner.encode("ascii", errors="replace").decode("ascii"))


def parse_arguments(cli_args=None) -> argparse.Namespace:
    """Parse CLI arguments with dynamic PORT environment variable fallback."""
    default_port = int(os.environ.get("PORT", 8080))
    parser = argparse.ArgumentParser(description="Royal Ludo Server Launcher")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to listen on (default: {default_port})")
    parser.add_argument("--ssl-cert", default=None, help="Path to SSL certificate PEM file for HTTPS")
    parser.add_argument("--ssl-key", default=None, help="Path to SSL private key PEM file for HTTPS")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open the browser")
    return parser.parse_args(cli_args)


async def main():
    args = parse_arguments()

    project_root = Path(__file__).resolve().parent
    static_dir = project_root / "static"

    app = create_app(static_dir)
    local_ip = get_local_ip()

    ssl_ctx = None
    if args.ssl_cert and args.ssl_key:
        ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(certfile=args.ssl_cert, keyfile=args.ssl_key)

    is_ssl = ssl_ctx is not None
    print_banner(args.host, args.port, local_ip, is_ssl=is_ssl)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, args.host, args.port, ssl_context=ssl_ctx)
    await site.start()

    proto = "https" if is_ssl else "http"
    local_url = f"{proto}://localhost:{args.port}"

    is_headless = args.no_browser or bool(os.environ.get("RENDER")) or os.environ.get("HEADLESS", "").lower() in ("1", "true")
    if not is_headless:
        async def open_browser():
            await asyncio.sleep(0.6)
            try:
                webbrowser.open(local_url)
            except Exception as e:
                logger.warning(f"Could not automatically launch browser: {e}")

        asyncio.create_task(open_browser())

    # Keep server running until interrupt
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("Shutting down Royal Ludo server...")
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped. Thank you for playing Royal Ludo!")
        sys.exit(0)
