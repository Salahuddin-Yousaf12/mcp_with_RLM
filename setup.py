"""
setup.py — one-time setup for the Reddit Scraper MCP server.

What it does:
  1. Installs Python dependencies for mcp-server/
  2. Merges the reddit-scraper MCP entry into Claude Desktop's config
     (creates the file if it doesn't exist yet)

Run:
  python setup.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MCP_SERVER = ROOT / "orchestrator" / "mcp_server.py"
REQUIREMENTS = ROOT / "orchestrator" / "requirements.txt"

CLAUDE_CONFIG = (
    Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
)

MCP_ENTRY = {
    "command": "python",
    "args": [str(MCP_SERVER)],
}


def install_deps():
    print("→ Installing mcp-server dependencies...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        stdout=subprocess.DEVNULL,
    )
    print("  ✓ Done")


def patch_claude_config():
    print(f"→ Patching Claude Desktop config at:\n  {CLAUDE_CONFIG}")

    CLAUDE_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    if CLAUDE_CONFIG.exists():
        config = json.loads(CLAUDE_CONFIG.read_text(encoding="utf-8"))
    else:
        config = {}

    config.setdefault("mcpServers", {})

    if config["mcpServers"].get("reddit-scraper") == MCP_ENTRY:
        print("  ✓ Already configured, nothing to do")
        return

    config["mcpServers"]["reddit-scraper"] = MCP_ENTRY
    CLAUDE_CONFIG.write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    print("  ✓ Config updated — restart Claude Desktop to apply")


if __name__ == "__main__":
    install_deps()
    patch_claude_config()
    print("\nAll done. Start the Reddit scraper with:")
    print("  docker-compose up -d")
