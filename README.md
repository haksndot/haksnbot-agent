# haksnbot-agent

An autonomous Minecraft bot powered by [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python). The bot connects to a Minecraft server, responds to player chat, and plays the game autonomously - surviving, building, crafting, and helping other players.

## Features

- **Autonomous gameplay** - Survives, gathers resources, crafts tools, builds shelter
- **Player interaction** - Responds to chat, helps players, answers questions
- **Persistent connection** - Auto-reconnects on disconnection
- **Event-driven** - Reacts to chat messages, player joins/leaves, system events
- **Customizable personality** - Override the system prompt for your server's needs
- **50+ MCP tools** - Full Minecraft bot control plus optional server admin tools

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     haksnbot-agent                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │ Claude Agent SDK│  │ chat-poll.sh    │  │ Event Loop  │  │
│  │ (persistent)    │  │ (log watcher)   │  │ (asyncio)   │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────┘  │
└───────────┼────────────────────┼────────────────────────────┘
            │                    │
            │ stdio              │ reads server logs
            ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      MCP Servers                             │
│  ┌─────────────────────┐  ┌──────────────────────────────┐  │
│  │   haksnbot-tools    │  │   haksnbot-admin (optional)  │  │
│  │   (40+ tools)       │  │   (14 tools)                 │  │
│  │   - movement, chat  │  │   - files, git               │  │
│  │   - inventory, build│  │   - server management        │  │
│  └──────────┬──────────┘  └──────────────────────────────┘  │
└─────────────┼───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│   Minecraft Server      │
│   (via Mineflayer)      │
└─────────────────────────┘
```

## Prerequisites

- Python 3.10+
- [haksnbot-tools](https://github.com/haksndot/haksnbot-tools) installed
- Claude API key (set as `ANTHROPIC_API_KEY` environment variable)
- Minecraft server to connect to
- Microsoft account (for online-mode servers)

## Installation

```bash
git clone https://github.com/haksndot/haksnbot-agent.git
cd haksnbot-agent
./install.sh
```

This creates a virtual environment and installs dependencies (claude-agent-sdk, pyyaml).

## Configuration

Copy the example config and fill in your details:

```bash
cp config/agent.yaml.example config/agent.yaml
```

Edit `config/agent.yaml`:

```yaml
minecraft:
  host: mc.example.com        # Your server address
  port: 25565
  username: bot@outlook.com   # Microsoft email for online-mode
  auth: microsoft             # Omit for offline-mode servers
  version: "1.20.4"           # Minecraft version

claude:
  model: claude-sonnet-4-20250514
  max_tokens: 1024

behavior:
  respond_to_mentions: true   # Only respond when bot name mentioned
  greet_on_join: false        # Greet players who join
  message_batch_delay_ms: 3000

reconnect:
  enabled: true
  initial_delay_ms: 5000
  max_delay_ms: 300000
  backoff_multiplier: 2
```

## Running the Agent

```bash
./run.sh
```

Or manually:

```bash
source venv/bin/activate
export ANTHROPIC_API_KEY=your-api-key
python -m core
```

## Customization

### Prompt Loading

The agent concatenates all `.md` files from two directories:

1. `prompts/*.md` - Base behavior (published with the repo)
2. `docs/*.md` - Your custom documentation (you create this)

Files are loaded alphabetically within each directory.

### Adding Server Knowledge

Create a `docs/` directory and add markdown files for your server:

```
haksnbot-agent/
├── docs/
│   ├── commands.md         # Available commands
│   ├── personality.md      # Custom personality traits
│   ├── players.md          # Known players
│   └── server.md           # Server rules, economy, etc.
```

Use `docs/` to:
- Define server-specific rules and economy
- Add custom personality traits or guardrails
- Document known players and relationships
- Include plugin-specific instructions

## Default Behavior

The default system prompt creates an autonomous, friendly bot that:

- **Survives** - Finds food, builds shelter, crafts tools
- **Explores** - Gathers resources, discovers the world
- **Helps players** - Answers questions, offers assistance
- **Socializes** - Greets players, makes conversation

See `prompts/system.md` for the full default prompt.

## Available Tools

### Minecraft Tools (haksnbot-tools)

40+ tools for in-game actions:

| Category | Tools |
|----------|-------|
| Connection | connect, disconnect, get_connection_status |
| Observation | get_status, get_block_at, scan_area, find_blocks, get_nearby_entities |
| Movement | move_to, move_near, follow_player, look_at, stop |
| Communication | chat, whisper, get_chat_history |
| Inventory | get_inventory, get_held_item, equip_item |
| Containers | open_container, transfer_items, close_container |
| Crafting | get_craftable_items, get_recipe, craft_item |
| Combat | attack_entity, use_item, interact_entity |
| Building | place_block, break_block, place_sign, read_sign |
| Trading | find_villagers, open_villager_trades, trade_with_villager |
| Vision | take_screenshot, get_player_skin |

### Admin Tools (haksnbot-admin, optional)

14 tools for server administration:

| Category | Tools |
|----------|-------|
| Files | read_file, write_file, edit_file, list_directory |
| Commands | run_command |
| Git | git_status, git_diff, git_commit, git_push, git_pull |
| Server | get_online_players, send_server_command, restart_server |

## Plugin Integrations

This agent system was originally developed for a server running GriefPrevention and QuickShop-Hikari. The underlying [haksnbot-tools](https://github.com/haksndot/haksnbot-tools) has built-in support for these plugins, which the agent inherits.

### GriefPrevention Support

On servers with GriefPrevention, the agent automatically:
- **Respects claims** - Detects when actions are denied due to claim protection
- **Reports denials** - Tells players when it can't perform an action due to claims
- **Checks trust levels** - Uses `/trustlist` to understand claim permissions

Affected tools: `break_block`, `place_block`, `place_sign`, `edit_sign`, `open_container`, `interact_entity`, `mount_entity`

### QuickShop-Hikari Support

On servers with QuickShop-Hikari (requires `MC_SERVER_ROOT` env var), the agent can:
- **Browse shops** - List all player shops or search by item
- **Help with economy** - Answer "where can I buy X?" questions
- **Create shops** - Set up chest shops for players

See [haksnbot-tools Plugin Integrations](https://github.com/haksndot/haksnbot-tools#plugin-integrations) for configuration details.

### Without These Plugins

All agent features work normally without GriefPrevention or QuickShop. Claim checks are simply skipped, and shop tools return a helpful error. The agent adapts its responses based on what works.

## Event Handling

The agent receives events from the Minecraft server:

- **Chat messages**: `[username]: message`
- **Player joins**: `Player joined the game`
- **Player leaves**: `Player left the game`
- **System messages**: Deaths, achievements, server announcements

Events are detected by watching server logs via `chat-poll.sh`.

## Troubleshooting

### Config validation errors

The agent validates config on startup. If required fields are missing:

```
Configuration incomplete. Please edit agent/config/agent.yaml:
  - minecraft.host is required
  - minecraft.username is required
  - minecraft.version is required
```

### Microsoft auth failed

```bash
cd /path/to/haksnbot-tools
node auth.js status your-email@outlook.com
node auth.js login your-email@outlook.com
```

### MCP server not found

Ensure haksnbot-tools is installed:

```bash
cd /path/to/haksnbot-tools
npm install
```

## Files

```
haksnbot-agent/
├── core.py                 # Main agent (event loop, SDK integration)
├── config/
│   ├── agent.yaml.example  # Template configuration
│   └── agent.yaml          # Your configuration (gitignored)
├── prompts/
│   └── system.md           # Default system prompt
├── data/
│   └── agent.log           # Runtime logs
├── requirements.txt        # Python dependencies
├── install.sh              # Installation script
└── run.sh                  # Run script
```

## Related Projects

- [haksnbot-tools](https://github.com/haksndot/haksnbot-tools) - Minecraft MCP tools (required)
- [haksnbot-admin](https://github.com/haksndot/haksnbot-admin) - Server admin MCP tools (optional)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) - Official SDK

## License

MIT
