# Gameplay Tips

Practical tips for using MCP tools effectively. These are learned behaviors that help the bot operate reliably.

## Harvesting Resources

**IMPORTANT:** When you break blocks (crops, trees, etc.), items drop on the ground. You must **walk over to the dropped items to pick them up**. This is an explicit step - don't skip it!

For single blocks:
1. Break the block (wheat, log, etc.)
2. Move to where the items dropped
3. Walk over them to collect into your inventory

**Mandatory cleanup scan:** After any batch harvesting operation (multiple blocks), run `get_nearby_entities(type="item")` to scan for missed drops within a 10-15 block radius. Collect any found items before moving to a new area or declaring the job complete.

## Climbing Ladders

Ladders are tricky for bots. If you target a block containing a ladder (e.g. the top of a ladder), you'll sink down instead of staying at the top. The trick is to **step off the ladder** at your destination.

To climb a ladder:
1. Scan to find the ladder's top Y level
2. Use `move_near` with a target that **overshoots the Y level** (a few blocks higher than needed)
3. Target a block **adjacent to the ladder**, not the ladder itself
4. This causes you to step off onto solid ground at the top

## Finding Players

- `get_nearby_players` only shows players within ~100 blocks
- To see all online players, use `chat("/list")` - the response appears in chat history
- Use `get_chat_history` to read the response

## Connection Handling

- **On startup:** Call `connect` when instructed to do so by the system
- **On disconnect:** Reconnection is automatic with exponential backoff
- If you get "Reconnecting..." errors: Just wait a few seconds and retry

Use `get_connection_status` to check the current state:
- `connected` - Ready to use
- `reconnecting` - Auto-reconnect in progress, wait and retry
- `connecting` - Initial connection in progress
- `disconnected` - Call `connect` to join the server

## Memory System

If memory-mcp is available, use it to remember experiences across sessions.

### Session Startup

At the start of each session, review your memories to refresh context:
1. Use `get_memory_stats` to see what's stored
2. Use `list_memories` (sorted by importance or recency) to review key memories
3. Before interacting with a specific player, use `search_memories` to find relevant history

### When to Create Memories

Create memories for **significant experiences**:

- **Player interactions** - Conversations, trades, partnerships, favors given/received
- **Relationship milestones** - First meeting, building trust, notable moments
- **Business dealings** - Trades, shop transactions, debts, agreements
- **Adventures** - Mining expeditions, builds, discoveries, deaths
- **Lessons learned** - Things that worked, things that failed, insights gained
- **Promises or commitments** - Things you agreed to do or players agreed to do

**Don't create memories for:**
- Routine/trivial exchanges ("hi", "thanks", simple questions)
- General Minecraft knowledge
- Temporary situations that won't matter later

### Memory Best Practices

- **Use descriptive tags** like `player:Steve`, `activity:mining`, `event:trade`, `lesson:trust`
- **Set importance appropriately** - 1-3 for minor notes, 4-6 for normal events, 7-10 for significant moments
- **Include context** - When/where/why something happened
- **Be concise** - Capture the essence, not every detail
- **Update memories** when situations change (debts repaid, relationships evolve)

## Villager Trading

To trade with villagers:
1. Use `find_villagers` to locate nearby villagers and see their professions
2. Move close to the villager (within 3 blocks)
3. Use `open_villager_trades` to see available trades
4. Use `trade_with_villager` with the trade index to execute
5. Use `close_villager_trades` when done

## Container Operations

When working with chests and furnaces:
1. Use `open_container` with coordinates to open it
2. Use `get_container_contents` to see what's inside
3. Use `transfer_items` to move items (direction: "to_container" or "to_inventory")
4. For furnaces: slot 0 = input, slot 1 = fuel, slot 2 = output
5. Use `close_container` when done

## Crafting

1. Use `get_craftable_items` to see what you can make with current inventory
2. Use `get_recipe` if you need to see ingredients for something
3. Use `craft_item` to craft - it automatically uses a nearby crafting table for 3x3 recipes
4. For 3x3 recipes, make sure you're near a crafting table first

## Combat Tips

- Use `get_nearby_entities` to see what mobs are around
- `attack_entity` attacks the nearest entity of that type
- The bot will continue attacking until the mob is dead
- Equip a weapon first with `equip_item` for better damage
- `break_block` with `equip_best_tool=true` automatically selects the right tool
