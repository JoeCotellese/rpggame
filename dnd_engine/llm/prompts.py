# ABOUTME: Prompt template functions for generating LLM requests
# ABOUTME: Builds structured prompts for room descriptions, combat, victories, and deaths

from typing import Any


def build_room_description_prompt(room_data: dict[str, Any]) -> str:
    """
    Build prompt for room description enhancement.

    Args:
        room_data: Room info (name, description, exits, contents, monsters)

    Returns:
        Formatted prompt for LLM
    """
    base_desc = room_data.get("description", "")
    room_type = room_data.get("name", "chamber")
    monsters = room_data.get("monsters", [])

    # Build monster context if present
    monster_context = ""
    if monsters:
        # Format monster list for natural language
        monster_count = len(monsters)
        if monster_count == 1:
            monster_context = f"\nPresent in the room: {monsters[0]} (hostile)"
        elif monster_count == 2:
            monster_context = f"\nPresent in the room: {monsters[0]} and {monsters[1]} (hostile)"
        else:
            # Group by type for readability
            from collections import Counter
            monster_counts = Counter(monsters)
            monster_parts = []
            for monster, count in monster_counts.items():
                if count == 1:
                    monster_parts.append(monster)
                else:
                    monster_parts.append(f"{count} {monster}s")
            if len(monster_parts) == 1:
                monster_context = f"\nPresent in the room: {monster_parts[0]} (hostile)"
            else:
                monster_list = ", ".join(monster_parts[:-1]) + f", and {monster_parts[-1]}"
                monster_context = f"\nPresent in the room: {monster_list} (hostile)"

    prompt = f"""Enhance this D&D dungeon room description with atmospheric details:

Room: {room_type}
Basic description: {base_desc}{monster_context}

Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. Make it immersive but concise.{" Acknowledge the presence of hostile creatures naturally in your description - describe their stance, readiness, or threatening demeanor." if monster_context else ""}"""

    return prompt


def build_combat_action_prompt(action_data: dict[str, Any]) -> str:
    """
    Build prompt for combat action narration.

    Args:
        action_data: Combat details including:
            - attacker, defender, weapon, damage, hit/miss, location
            - attacker_race, defender_armor, damage_type
            - combat_history: List of recent action summaries
            - battlefield_state: Current HP status of all combatants

    Returns:
        Formatted prompt for LLM
    """
    attacker = action_data.get("attacker", "Someone")
    defender = action_data.get("defender", "something")
    weapon = action_data.get("weapon", "weapon")
    damage = action_data.get("damage", 0)
    hit = action_data.get("hit", False)
    location = action_data.get("location", "")

    # Combat history and battlefield state
    combat_history = action_data.get("combat_history", [])
    battlefield_state = action_data.get("battlefield_state", {})

    # Additional context for narrative richness
    attacker_race = action_data.get("attacker_race", "")
    defender_armor = action_data.get("defender_armor", "")
    damage_type = action_data.get("damage_type", "")
    round_number = action_data.get("round_number")

    # Build context strings
    location_context = f"Location: {location}\n" if location else ""

    # Build round context
    round_context = ""
    if round_number is not None:
        if round_number <= 1:
            round_context = "Combat Stage: Opening exchange\n"
        else:
            round_context = f"Combat Stage: Ongoing battle (Round {round_number})\n"

    # Build combat history context
    history_context = ""
    if combat_history:
        history_lines = []
        for i, action in enumerate(combat_history[-8:], 1):  # Last 8 actions
            history_lines.append(f"  {i}. {action}")
        history_context = "Recent Combat Actions:\n" + "\n".join(history_lines) + "\n\n"

    # Build battlefield state context
    battlefield_context = ""
    if battlefield_state:
        party_hp = battlefield_state.get("party_hp", [])
        enemy_hp = battlefield_state.get("enemy_hp", [])

        if party_hp or enemy_hp:
            party_status = ", ".join([f"{name} {hp}/{max_hp}" for name, hp, max_hp in party_hp])
            enemy_status = ", ".join([f"{name} {hp}/{max_hp}" for name, hp, max_hp in enemy_hp])
            battlefield_context = (
                f"Battlefield: Party [{party_status}] | Enemies [{enemy_status}]\n\n"
            )

    # Build combatant descriptions
    attacker_desc = attacker
    if attacker_race:
        attacker_desc = f"{attacker} (a {attacker_race})"

    defender_desc = defender
    if defender_armor:
        defender_desc = f"{defender} (wearing {defender_armor})"

    weapon_desc = weapon
    if damage_type:
        weapon_desc = f"{weapon} ({damage_type} damage)"

    # Build the main prompt
    if hit:
        prompt = f"""Narrate this D&D combat action vividly:

{location_context}{round_context}{battlefield_context}{history_context}
Current Action: {attacker_desc} attacks {defender_desc} with a {weapon_desc}
for {damage} damage.

Describe the hit in 1-2 dramatic sentences. Focus on rich detail but maintain
brevity so the player isn't bogged down reading. Consider the battlefield state
and recent action flow. Focus on the impact and visual details."""
    else:
        prompt = f"""Narrate this D&D combat miss:

{location_context}{round_context}{battlefield_context}{history_context}Current 
Action: {attacker_desc} attacks {defender_desc} with a {weapon_desc} but misses.

Describe the miss in 1-2 sentences. Focus on rich detail but maintain
brevity so the player isn't bogged down reading.
Consider the battlefield state and recent action flow. Make it cinematic."""

    return prompt


def build_death_prompt(character_data: dict[str, Any]) -> str:
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


def build_victory_prompt(combat_data: dict[str, Any]) -> str:
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

The party defeats {", ".join(enemies)}. The final blow: {final_blow}.

Describe the aftermath in 2-3 sentences. Capture the sense of triumph and relief."""

    return prompt


def build_combat_start_prompt(combat_data: dict[str, Any]) -> str:
    """
    Build prompt for combat initiation narration.

    Args:
        combat_data: Combat details (enemies, location, party)

    Returns:
        Formatted prompt for LLM
    """
    enemies = combat_data.get("enemies", ["enemies"])
    location = combat_data.get("location", "")
    party_size = combat_data.get("party_size", 1)

    location_context = f" in the {location}" if location else ""
    party_desc = "The adventurer" if party_size == 1 else f"The party of {party_size}"

    # Format enemy list for natural language
    if len(enemies) == 1:
        enemy_desc = f"a {enemies[0]}"
    elif len(enemies) == 2:
        enemy_desc = f"a {enemies[0]} and a {enemies[1]}"
    else:
        enemy_desc = f"{len(enemies)} enemies"

    prompt = f"""Narrate the start of a D&D combat encounter:

{party_desc} encounters {enemy_desc}{location_context}.

Describe how combat begins in 2-3 dramatic sentences. Do the enemies ambush the party, or does the party surprise them? Set the scene for the battle to come."""

    return prompt
