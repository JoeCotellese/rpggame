# ABOUTME: Prompt template functions for generating LLM requests
# ABOUTME: Builds structured prompts for room descriptions, combat, victories, and deaths

from typing import Any, Dict


def build_room_description_prompt(room_data: Dict[str, Any]) -> str:
    """
    Build prompt for room description enhancement.

    Args:
        room_data: Room info (name, description, exits, contents)

    Returns:
        Formatted prompt for LLM
    """
    base_desc = room_data.get("description", "")
    room_type = room_data.get("name", "chamber")

    prompt = f"""Enhance this D&D dungeon room description with atmospheric details:

Room: {room_type}
Basic description: {base_desc}

Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. Make it immersive but concise."""

    return prompt


def build_combat_action_prompt(action_data: Dict[str, Any]) -> str:
    """
    Build prompt for combat action narration.

    Args:
        action_data: Combat details (attacker, target, weapon, damage, hit/miss)

    Returns:
        Formatted prompt for LLM
    """
    attacker = action_data.get("attacker", "Someone")
    target = action_data.get("target", "something")
    weapon = action_data.get("weapon", "weapon")
    damage = action_data.get("damage", 0)
    hit = action_data.get("hit", False)

    if hit:
        prompt = f"""Narrate this D&D combat action vividly:

{attacker} attacks {target} with a {weapon} for {damage} damage.

Describe the hit in 2-3 dramatic sentences. Focus on the impact and visual details."""
    else:
        prompt = f"""Narrate this D&D combat miss:

{attacker} attacks {target} with a {weapon} but misses.

Describe the miss in 1-2 sentences. Why did it fail? Make it cinematic."""

    return prompt


def build_death_prompt(character_data: Dict[str, Any]) -> str:
    """
    Build prompt for character death narration.

    Args:
        character_data: Character info (name, race, class, how they died)

    Returns:
        Formatted prompt for LLM
    """
    name = character_data.get("name", "The hero")
    how_died = character_data.get("cause", "fell in battle")

    prompt = f"""Narrate a heroic D&D character death:

{name} {how_died}.

Write 2-3 sentences about their final moments. Be dramatic but respectful. This is the end of their story."""

    return prompt


def build_victory_prompt(combat_data: Dict[str, Any]) -> str:
    """
    Build prompt for combat victory narration.

    Args:
        combat_data: Combat details (enemies defeated, final blow)

    Returns:
        Formatted prompt for LLM
    """
    enemies = combat_data.get("enemies", ["foes"])
    final_blow = combat_data.get("final_blow", "struck down the last enemy")

    prompt = f"""Narrate a D&D combat victory:

The party defeats {', '.join(enemies)}. The final blow: {final_blow}.

Describe the aftermath in 2-3 sentences. Capture the sense of triumph and relief."""

    return prompt
