"""
Haksnbot Agent Core

Persistent agent using Claude Agent SDK with existing minecraft-mcp tools.
Uses persistent tail on server log for event detection, minecraft-mcp for bot actions.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import yaml

# Import the Claude Agent SDK
try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    SDK_AVAILABLE = True
except ImportError:
    print("Warning: claude-agent-sdk not installed, running in stub mode")
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    SDK_AVAILABLE = False

# Paths
AGENT_DIR = Path(__file__).parent
REPO_DIR = AGENT_DIR.parent
MINECRAFT_MCP = REPO_DIR / "minecraft-mcp" / "src" / "index.js"
SERVER_ADMIN_MCP = REPO_DIR / "server-admin-mcp" / "src" / "index.js"
MEMORY_MCP = REPO_DIR / "memory-mcp" / "src" / "index.js"
MAP_MCP = REPO_DIR / "map-mcp" / "src" / "index.js"
SERVER_LOG = Path("/home/haksndot/server/logs/latest.log")
BOT_LOG = AGENT_DIR / "data" / "bot-messages.log"

# Patterns to filter out from server log (private/technical noise)
SKIP_PATTERNS = [
    "issued server command:",  # Player commands (private)
    "UUID of player",          # Connection technical details
    "logged in with entity id", # Login coordinates
    "lost connection:",        # Disconnect details
    "GameProfile",             # Auth details
    "[QuickShop-Hikari]",      # Plugin spam
    "CONSOLE issued",          # Console commands
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(AGENT_DIR / "data" / "agent.log"),
    ],
)
logger = logging.getLogger("haksnbot")


def load_config() -> dict:
    """Load configuration from agent.yaml."""
    config_path = AGENT_DIR / "config" / "agent.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def validate_config(config: dict) -> list[str]:
    """
    Validate that required config fields are populated.
    Returns a list of error messages (empty if valid).
    """
    errors = []
    mc = config.get("minecraft", {})

    if not mc.get("host"):
        errors.append("minecraft.host is required (e.g. 'localhost' or '192.168.1.100')")

    if not mc.get("username"):
        errors.append("minecraft.username is required (Microsoft email for online-mode, or any name for offline)")

    if not mc.get("version"):
        errors.append("minecraft.version is required (e.g. '1.21.8')")

    return errors


def load_system_prompt() -> str:
    """Load system prompt and documentation files.

    Loads all .md files from:
    1. agent/prompts/ - Base agent behavior and tips (published)
    2. docs/ - User's custom server documentation (not published)
    """
    parts = []
    prompts_dir = AGENT_DIR / "prompts"
    docs_dir = REPO_DIR / "docs"

    # Load all prompt files
    if prompts_dir.exists():
        prompt_files = sorted(prompts_dir.glob("*.md"))
        for prompt_file in prompt_files:
            with open(prompt_file) as f:
                parts.append(f.read())
        if prompt_files:
            logger.info(f"Loaded {len(prompt_files)} prompt files")

    # Load user's custom documentation
    if docs_dir.exists():
        doc_files = sorted(docs_dir.glob("*.md"))
        for doc_file in doc_files:
            with open(doc_file) as f:
                parts.append(f.read())
        if doc_files:
            logger.info(f"Loaded {len(doc_files)} doc files")

    if not parts:
        parts.append("You are a Minecraft bot agent.")

    return "\n\n---\n\n".join(parts)


class HaksnbotAgent:
    """Main Haksnbot agent class."""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        self.client: Optional[ClaudeSDKClient] = None
        self.running = False
        self.server_tail: Optional[asyncio.subprocess.Process] = None
        self.bot_tail: Optional[asyncio.subprocess.Process] = None
        self.event_queue: Optional[asyncio.Queue] = None

    async def start(self):
        """Start the agent."""
        logger.info("Starting Haksnbot Agent...")

        # Validate config
        config_errors = validate_config(self.config)
        if config_errors:
            logger.error("Configuration incomplete. Please edit agent/config/agent.yaml:")
            for err in config_errors:
                logger.error(f"  - {err}")
            sys.exit(1)

        if not SDK_AVAILABLE:
            logger.error("Claude Agent SDK not available")
            return

        # Build MCP server config - use existing minecraft-mcp
        mc_config = self.config.get("minecraft", {})
        claude_config = self.config.get("claude", {})

        # Environment variables for the MCP server
        mcp_env = {
            **os.environ,
            "MC_HOST": mc_config.get("host"),
            "MC_PORT": str(mc_config.get("port", 25565)),
            "MC_USERNAME": mc_config.get("username"),
            "MC_VERSION": mc_config.get("version"),
        }
        # Only set auth if specified (omit for offline-mode)
        if mc_config.get("auth"):
            mcp_env["MC_AUTH"] = mc_config.get("auth")
        # Server root for QuickShop integration
        if mc_config.get("server_root"):
            mcp_env["MC_SERVER_ROOT"] = mc_config.get("server_root")

        options = ClaudeAgentOptions(
            mcp_servers={
                "minecraft": {
                    "type": "stdio",
                    "command": "node",
                    "args": [str(MINECRAFT_MCP)],
                    "env": mcp_env,
                },
                "admin": {
                    "type": "stdio",
                    "command": "node",
                    "args": [str(SERVER_ADMIN_MCP)],
                },
                "memory": {
                    "type": "stdio",
                    "command": "node",
                    "args": [str(MEMORY_MCP)],
                },
                "map": {
                    "type": "stdio",
                    "command": "node",
                    "args": [str(MAP_MCP)],
                }
            },
            allowed_tools=[
                # All minecraft-mcp tools
                "mcp__minecraft__connect",
                "mcp__minecraft__disconnect",
                "mcp__minecraft__get_connection_status",
                "mcp__minecraft__get_status",
                "mcp__minecraft__get_block_at",
                "mcp__minecraft__scan_area",
                "mcp__minecraft__find_blocks",
                "mcp__minecraft__get_nearby_entities",
                "mcp__minecraft__get_nearby_players",
                "mcp__minecraft__move_to",
                "mcp__minecraft__move_near",
                "mcp__minecraft__follow_player",
                "mcp__minecraft__look_at",
                "mcp__minecraft__stop",
                "mcp__minecraft__chat",
                "mcp__minecraft__whisper",
                "mcp__minecraft__get_chat_history",
                "mcp__minecraft__get_inventory",
                "mcp__minecraft__get_held_item",
                "mcp__minecraft__equip_item",
                "mcp__minecraft__open_container",
                "mcp__minecraft__get_container_contents",
                "mcp__minecraft__transfer_items",
                "mcp__minecraft__close_container",
                "mcp__minecraft__get_craftable_items",
                "mcp__minecraft__get_recipe",
                "mcp__minecraft__craft_item",
                "mcp__minecraft__attack_entity",
                "mcp__minecraft__use_item",
                "mcp__minecraft__sleep",
                "mcp__minecraft__wake",
                "mcp__minecraft__place_sign",
                "mcp__minecraft__read_sign",
                "mcp__minecraft__edit_sign",
                "mcp__minecraft__place_block",
                "mcp__minecraft__break_block",
                "mcp__minecraft__create_chest_shop",
                "mcp__minecraft__get_player_skin",
                "mcp__minecraft__take_screenshot",
                "mcp__minecraft__interact_entity",
                # Villager trading tools
                "mcp__minecraft__find_villagers",
                "mcp__minecraft__open_villager_trades",
                "mcp__minecraft__trade_with_villager",
                "mcp__minecraft__close_villager_trades",
                "mcp__minecraft__mount_entity",
                "mcp__minecraft__dismount",
                # QuickShop economy tools
                "mcp__minecraft__list_all_shops",
                "mcp__minecraft__search_shops",
                # All server-admin-mcp tools
                "mcp__admin__read_file",
                "mcp__admin__write_file",
                "mcp__admin__edit_file",
                "mcp__admin__list_directory",
                "mcp__admin__run_command",
                "mcp__admin__git_status",
                "mcp__admin__git_diff",
                "mcp__admin__git_commit",
                "mcp__admin__git_push",
                "mcp__admin__git_pull",
                "mcp__admin__get_online_players",
                "mcp__admin__send_server_command",
                "mcp__admin__restart_server",
                "mcp__admin__get_server_status",
                # Memory tools
                "mcp__memory__create_memory",
                "mcp__memory__get_memory",
                "mcp__memory__update_memory",
                "mcp__memory__delete_memory",
                "mcp__memory__list_memories",
                "mcp__memory__search_memories",
                "mcp__memory__get_memory_stats",
                # Map tools (location storage and spatial queries)
                "mcp__map__save_location",
                "mcp__map__get_location",
                "mcp__map__list_locations",
                "mcp__map__delete_location",
                "mcp__map__search_locations",
                "mcp__map__find_by_tags",
                "mcp__map__list_tags",
                "mcp__map__get_distance",
                "mcp__map__find_nearest",
                "mcp__map__find_in_radius",
                "mcp__map__get_nether_coords",
                "mcp__map__add_tags",
                "mcp__map__remove_tags",
                "mcp__map__get_location_stats",
            ],
            system_prompt=load_system_prompt(),
            model=claude_config.get("model", "claude-sonnet-4-20250514"),
        )

        self.client = ClaudeSDKClient(options=options)
        await self.client.__aenter__()
        logger.info("Claude SDK client initialized with minecraft-mcp")

        # MCP server auto-connects using env vars, just give Claude initial context
        await self.client.query(
            "You are now connected to the Minecraft server as Haksnbot. "
            "You are ready to assist players. When players mention 'haksnbot' in chat, "
            "respond helpfully using the chat tool."
        )
        logger.info("Waiting for Claude init response...")
        async for msg in self.client.receive_response():
            logger.info(f"Init response: {type(msg).__name__}")
            self.log_sdk_message(msg)

        logger.info("Bot connected to Minecraft server")
        self.running = True

    async def stop(self):
        """Stop the agent."""
        logger.info("Stopping Haksnbot Agent...")
        self.running = False

        # Stop tail processes
        for proc in [self.server_tail, self.bot_tail]:
            if proc:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    proc.kill()

        # Close SDK client (MCP server terminates and bot disconnects automatically)
        if self.client:
            await self.client.__aexit__(None, None, None)

        logger.info("Haksnbot Agent stopped")

    async def start_tail(self, log_file: Path) -> asyncio.subprocess.Process:
        """Start persistent tail -f on a log file."""
        # Ensure the file exists (create if needed for bot log)
        if not log_file.exists():
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()

        # Use stdbuf to disable output buffering (tail buffers when not on tty)
        process = await asyncio.create_subprocess_exec(
            "stdbuf", "-oL", "tail", "-n", "0", "-f", str(log_file),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info(f"Started tail on {log_file}")
        return process

    async def tail_reader(self, process: asyncio.subprocess.Process, source: str):
        """Read lines from a tail process and put them in the event queue."""
        while self.running and process.stdout:
            try:
                line_bytes = await process.stdout.readline()
                if not line_bytes:
                    # EOF - process died
                    logger.warning(f"Tail process for {source} ended")
                    break
                line = line_bytes.decode().strip()
                if line:
                    await self.event_queue.put((source, line))
            except Exception as e:
                logger.error(f"Error reading from {source} tail: {e}")
                break

    def should_forward_server_line(self, line: str) -> bool:
        """Check if a server log line should be forwarded to Claude."""
        # Only forward INFO lines
        if "/INFO]: " not in line:
            return False

        # Skip lines matching any skip pattern
        for pattern in SKIP_PATTERNS:
            if pattern in line:
                return False

        return True

    def parse_server_line(self, line: str) -> Optional[dict]:
        """Parse a Minecraft server log line into an event."""
        # Extract message content after "]: "
        if "]: " in line:
            content = line.split("]: ", 1)[-1]
        else:
            content = line

        if not content.strip():
            return None

        # Detect join/leave for logging
        if "joined the game" in content:
            username = content.replace(" joined the game", "").strip()
            return {"type": "player_join", "username": username, "content": content.strip()}

        if "left the game" in content:
            username = content.replace(" left the game", "").strip()
            return {"type": "player_leave", "username": username, "content": content.strip()}

        return {"type": "activity", "content": content.strip()}

    def parse_bot_line(self, line: str) -> Optional[dict]:
        """Parse a bot message log line (JSON format) into an event."""
        try:
            data = json.loads(line)
            msg_type = data.get("type", "system")
            content = data.get("content", "")

            if msg_type == "chat":
                user = data.get("user", "Unknown")
                return {"type": "bot_chat", "content": f"<{user}> {content}", "user": user}
            else:
                # System message (command response, etc.)
                return {"type": "bot_system", "content": content}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse bot log line: {line}")
            return None

    def log_sdk_message(self, msg):
        """Log SDK message in human-readable format."""
        msg_type = type(msg).__name__

        if msg_type == "AssistantMessage":
            # Claude's thinking/response
            for block in msg.content:
                block_type = type(block).__name__
                if block_type == "TextBlock":
                    logger.info(f"[Claude] {block.text}")
                elif block_type == "ToolUseBlock":
                    tool_name = getattr(block, 'name', 'unknown')
                    tool_input = getattr(block, 'input', {})
                    logger.info(f"[Tool Call] {tool_name}: {tool_input}")
                else:
                    logger.debug(f"[Assistant/{block_type}] {block}")

        elif msg_type == "UserMessage":
            # Tool results
            for block in msg.content:
                block_type = type(block).__name__
                if block_type == "ToolResultBlock":
                    content = getattr(block, 'content', '')
                    is_error = getattr(block, 'is_error', False)
                    if is_error:
                        logger.warning(f"[Tool Error] {content}")
                    else:
                        # Truncate long results
                        if len(str(content)) > 200:
                            content = str(content)[:200] + "..."
                        logger.info(f"[Tool Result] {content}")
                else:
                    logger.debug(f"[User/{block_type}] {block}")

        elif msg_type == "ResultMessage":
            # Final result
            cost = getattr(msg, 'total_cost_usd', 0)
            turns = getattr(msg, 'num_turns', 0)
            logger.info(f"[Done] {turns} turns, ${cost:.4f}")

        else:
            logger.debug(f"[{msg_type}] {msg}")

    async def handle_activity(self, content: str):
        """Handle server activity - forward everything to Claude."""
        logger.info(f"[Server] {content}")

        if not self.client:
            logger.warning("No Claude client available")
            return

        # Forward raw server log content to Claude
        prompt = f"Server log:\n{content}"

        try:
            await self.client.query(prompt)

            # Process response (Claude will decide if/how to respond)
            async for msg in self.client.receive_response():
                self.log_sdk_message(msg)
        except Exception as e:
            logger.error(f"Error getting Claude response: {e}")

    async def run(self):
        """Main event loop with dual-stream log tailing."""
        await self.start()

        if not self.running:
            return

        # Create event queue for both log streams
        self.event_queue = asyncio.Queue()

        # Start tail processes for both logs
        self.server_tail = await self.start_tail(SERVER_LOG)
        self.bot_tail = await self.start_tail(BOT_LOG)

        # Start reader tasks for both streams
        server_reader = asyncio.create_task(
            self.tail_reader(self.server_tail, "server")
        )
        bot_reader = asyncio.create_task(
            self.tail_reader(self.bot_tail, "bot")
        )

        logger.info("Entering main event loop (dual-stream)...")

        try:
            while self.running:
                # Wait for next event from either stream
                try:
                    source, line = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Process based on source
                if source == "server":
                    # Filter server log lines
                    if not self.should_forward_server_line(line):
                        continue

                    event = self.parse_server_line(line)
                    if not event:
                        continue

                    event_type = event.get("type")
                    content = event.get("content", "")

                    if event_type == "player_join":
                        logger.info(f"Player joined: {event.get('username')}")
                    elif event_type == "player_leave":
                        logger.info(f"Player left: {event.get('username')}")

                    # Forward to Claude
                    await self.handle_activity(content)

                elif source == "bot":
                    # Bot messages are already filtered (only chat/system)
                    event = self.parse_bot_line(line)
                    if not event:
                        continue

                    event_type = event.get("type")
                    content = event.get("content", "")

                    if event_type == "bot_system":
                        logger.info(f"[Bot received] {content}")
                        # Forward system messages (command responses) to Claude
                        await self.handle_activity(f"[Bot received] {content}")
                    # Note: bot_chat is likely duplicate of server log, skip it

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            # Cancel reader tasks
            server_reader.cancel()
            bot_reader.cancel()
            await self.stop()


async def main():
    """Entry point."""
    agent = HaksnbotAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
