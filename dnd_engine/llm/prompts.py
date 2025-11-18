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
        action_data: Combat details (attacker, target, weapon, damage, hit/miss, location,
                     attacker_race, attacker_armor, defender_armor, damage_type, round_number)

    Returns:
        Formatted prompt for LLM
    """
    attacker = action_data.get("attacker", "Someone")
    defender = action_data.get("defender", "something")
    weapon = action_data.get("weapon", "weapon")
    damage = action_data.get("damage", 0)
    hit = action_data.get("hit", False)
    location = action_data.get("location", "")
    round_number = action_data.get("round_number", 1)

    # Additional context for narrative richness
    attacker_race = action_data.get("attacker_race", "")
    attacker_armor = action_data.get("attacker_armor", "")
    defender_armor = action_data.get("defender_armor", "")
    damage_type = action_data.get("damage_type", "")

    # Build context strings
    location_context = f"\nLocation: {location}" if location else ""

    # Round context for pacing
    # Note: round_number starts at 0 for first round, increments when initiative wraps
    if round_number <= 1:
        round_context = "\nThis is the opening exchange of combat."
    else:
        round_context = f"\nThis is round {round_number} of an ongoing battle."

    attacker_desc = attacker
    if attacker_race:
        attacker_desc = f"{attacker} (a {attacker_race})"

    defender_desc = defender
    if defender_armor:
        defender_desc = f"{defender} (wearing {defender_armor})"

    weapon_desc = weapon
    if damage_type:
        weapon_desc = f"{weapon} ({damage_type} damage)"

    if hit:
        prompt = f"""Narrate this D&D combat action vividly:

{attacker_desc} attacks {defender_desc} with a {weapon_desc} for {damage} damage.{location_context}{round_context}

Describe the hit in 2-3 dramatic sentences. Focus on the impact and visual details. Use environmental details appropriate to the location."""
    else:
        prompt = f"""Narrate this D&D combat miss:

{attacker_desc} attacks {defender_desc} with a {weapon_desc} but misses.{location_context}{round_context}

Describe the miss in 1-2 sentences. Why did it fail? Make it cinematic and appropriate to the location."""

    return prompt


def build_death_prompt(character_data: Dict[str, Any]) -> str:
    """
    Build prompt for death narration (player or enemy).

    Args:
        character_data: Character info (name, is_player, race, class, how they died)

    Returns:
        Formatted prompt for LLM
    """
    name = character_data.get("name", "The combatant")
    is_player = character_data.get("is_player", False)
    how_died = character_data.get("cause", "fell in battle")

    if is_player:
        prompt = f"""Narrate a heroic D&D character death:

{name} {how_died}.

Write 2-3 sentences about their final moments. Be dramatic but respectful. This is the end of their story."""
    else:
        prompt = f"""Narrate the defeat of an enemy creature:

{name} {how_died}.

Write 2-3 sentences about their final moments. Be dramatic and satisfying for the victors."""

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
