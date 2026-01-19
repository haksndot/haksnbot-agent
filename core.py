"""
Haksnbot Agent Core

Persistent agent using Claude Agent SDK with existing minecraft-mcp tools.
Uses chat-poll.sh for event detection, minecraft-mcp for bot actions.
"""

import asyncio
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
CHAT_POLL = REPO_DIR / "chat-poll.sh"

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
        self.poll_process: Optional[asyncio.subprocess.Process] = None

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

        # Stop chat poll process
        if self.poll_process:
            self.poll_process.terminate()
            await self.poll_process.wait()

        # Close SDK client (MCP server terminates and bot disconnects automatically)
        if self.client:
            await self.client.__aexit__(None, None, None)

        logger.info("Haksnbot Agent stopped")

    async def start_chat_poll(self) -> asyncio.subprocess.Process:
        """Start chat-poll.sh in background."""
        process = await asyncio.create_subprocess_exec(
            str(CHAT_POLL),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return process

    async def wait_for_event(self) -> Optional[dict]:
        """Wait for next chat/join/leave event from chat-poll.sh."""
        self.poll_process = await self.start_chat_poll()

        try:
            stdout, _ = await asyncio.wait_for(
                self.poll_process.communicate(),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            self.poll_process.terminate()
            return {"type": "timeout"}

        if not stdout:
            return None

        line = stdout.decode().strip()
        if not line:
            return None

        # Parse the log line
        # Format: [HH:MM:SS] [Server thread/INFO]: <Player> message
        # Or: [HH:MM:SS] [Server thread/INFO]: Player joined the game
        return self.parse_log_line(line)

    def parse_log_line(self, line: str) -> Optional[dict]:
        """Parse a Minecraft server log line into an event.

        We forward everything to Claude and let it decide what's relevant.
        Join/leave events are still detected for logging purposes.
        """
        # Extract message content after "]: "
        if "]: " in line:
            content = line.split("]: ", 1)[-1]
        else:
            content = line

        if not content.strip():
            return None

        # Detect join/leave for logging (but still forward to Claude)
        if "joined the game" in content:
            username = content.replace(" joined the game", "").strip()
            return {"type": "player_join", "username": username}

        if "left the game" in content:
            username = content.replace(" left the game", "").strip()
            return {"type": "player_leave", "username": username}

        # Forward everything else as server activity
        # Claude will see: chat messages, Discord messages, deaths, achievements,
        # command output, plugin messages, etc.
        return {"type": "activity", "content": content.strip()}

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
        """Main event loop."""
        await self.start()

        if not self.running:
            return

        logger.info("Entering main event loop...")

        try:
            while self.running:
                # Wait for next event from server logs
                event = await self.wait_for_event()

                if not event:
                    continue

                event_type = event.get("type")

                if event_type == "activity":
                    await self.handle_activity(event.get("content", ""))

                elif event_type == "player_join":
                    # Log locally, but also forward to Claude
                    logger.info(f"Player joined: {event.get('username')}")
                    await self.handle_activity(f"{event.get('username')} joined the game")

                elif event_type == "player_leave":
                    # Log locally, but also forward to Claude
                    logger.info(f"Player left: {event.get('username')}")
                    await self.handle_activity(f"{event.get('username')} left the game")

                elif event_type == "timeout":
                    # No events in 60s, just continue
                    pass

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()


async def main():
    """Entry point."""
    agent = HaksnbotAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
