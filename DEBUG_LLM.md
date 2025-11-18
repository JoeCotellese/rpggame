# Debug LLM Provider

The debug LLM provider allows you to inspect the exact prompts being sent to the LLM without making actual API calls.

## Usage

### Command Line

```bash
# Use debug provider instead of actual LLM
dnd-game --llm-provider debug

# Or via environment variable
export LLM_PROVIDER=debug
dnd-game
```

### What It Does

Instead of calling OpenAI or Anthropic APIs, the debug provider returns the prompt text wrapped in debug markers:

```
[DEBUG PROMPT]
Enhance this D&D dungeon room description with atmospheric details:

Room: Guard Post
Basic description: A fortified checkpoint with arrow slits in the walls.

Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. Make it immersive but concise.
[/DEBUG PROMPT]
```

### When to Use It

- **Debugging narratives**: See exactly what context is being passed to the LLM
- **Prompt engineering**: Test prompt changes without burning API credits
- **Offline testing**: Test the game flow without needing API keys
- **Performance testing**: Isolate game logic from LLM latency

### Example Output

When you enter a room:
```
You step into the Guard Post...

[DEBUG PROMPT]
Enhance this D&D dungeon room description with atmospheric details:

Room: Guard Post
Basic description: A fortified checkpoint with arrow slits in the walls.

Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. Make it immersive but concise.
[/DEBUG PROMPT]
```

During combat:
```
⚔️ Larry attacks Goblin: 15+3=18 vs AC 15 - HIT for 8 damage

[DEBUG PROMPT]
Narrate this D&D combat action vividly:

Larry (a Human) attacks Goblin (wearing leather armor) with a Longsword (slashing damage) for 8 damage.
Location: Guard Post
This is the opening exchange of combat.

Describe the hit in 2-3 dramatic sentences. Focus on the impact and visual details. Use environmental details appropriate to the location.
[/DEBUG PROMPT]
```

## Implementation

- **File**: `dnd_engine/llm/debug_provider.py`
- **Class**: `DebugProvider`
- **Base**: Inherits from `LLMProvider`
- **Tests**: `tests/test_debug_provider.py`

The debug provider implements the same interface as OpenAI and Anthropic providers, making it a drop-in replacement for debugging purposes.
