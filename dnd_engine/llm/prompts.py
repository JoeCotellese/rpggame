# ABOUTME: Prompt template functions for generating LLM requests
# ABOUTME: Builds structured prompts for room descriptions, combat, victories, and deaths

from typing import Any


def build_room_description_prompt(
    room_data: dict[str, Any],
    combat_starting: bool = False,
    monsters_data: dict[str, Any] | None = None,
    party_size: int = 1,
) -> str:
    """
    Build prompt for room description enhancement.

    Args:
        room_data: Room info (name, description, exits, contents, monsters)
        combat_starting: If True, include combat initiation narrative in description
        monsters_data: Full monster definitions from monsters.json
        party_size: Number of party members for combat context

    Returns:
        Formatted prompt for LLM
    """
    base_desc = room_data.get("description", "")
    room_type = room_data.get("name", "chamber")
    room_id = room_data.get("id", room_type.lower().replace(" ", "_"))
    monsters = room_data.get("monsters", [])

    # Detect room transition for narrative context
    previous_room_id = room_data.get("previous_room_id")
    is_entering = previous_room_id != room_id if previous_room_id is not None else True

    # Extract lighting information
    base_lighting = room_data.get("base_lighting", "bright")
    party_lighting = room_data.get("party_lighting", [])

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

    # Build creature-aware combat instruction
    creature_behavior_guide = ""
    if combat_starting and monster_context and monsters_data:
        # Extract creature details for narrative guidance
        creature_types = []
        for monster_name in monsters:
            monster_key = monster_name.lower().replace(" ", "_")
            if monster_key in monsters_data:
                m = monsters_data[monster_key]
                creature_type = m.get("type", "creature")
                size = m.get("size", "medium")
                alignment = m.get("alignment", "neutral")
                creature_types.append({
                    "name": monster_name,
                    "type": creature_type,
                    "size": size,
                    "alignment": alignment,
                })

        # Build behavior guidance based on creature types
        if creature_types:
            type_examples = []
            seen_types = set()
            for c in creature_types:
                ctype = c["type"].split("(")[0].strip()  # Handle "humanoid (goblinoid)"
                if ctype not in seen_types:
                    seen_types.add(ctype)
                    if "undead" in ctype.lower():
                        type_examples.append(
                            f"- Undead: mechanical precision, relentless advance, emotionless determination"
                        )
                    elif "beast" in ctype.lower():
                        type_examples.append(
                            f"- Beasts: snarling, prowling, feral aggression, instinctive pack behavior"
                        )
                    elif "humanoid" in ctype.lower():
                        type_examples.append(
                            f"- Humanoids: tactical positioning, drawing weapons, battle cries, coordinated movements"
                        )

            if type_examples:
                creature_behavior_guide = (
                    f"\n\nCreature behavior guide:\n" + "\n".join(type_examples)
                )

    # Build instruction based on whether combat is starting
    if combat_starting and monster_context:
        party_context = (
            f"Party size: {party_size} adventurer{'s' if party_size != 1 else ''}\n"
        )
        instruction = f"""Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. Make it immersive but concise.

IMPORTANT: This is the moment combat begins. Naturally transition from describing the room into the combat initiation - describe how the enemies react to the party's presence using behavior appropriate to their nature. Show their threatening stance or aggressive movement toward the party, and the immediate tension as battle is about to erupt. Make it feel like a seamless escalation from scene-setting to action. Do NOT use phrases like "combat begins" - show it through the enemies' actions and the rising tension.

{party_context}{creature_behavior_guide}"""
    elif monster_context:
        instruction = " Acknowledge the presence of hostile creatures naturally in your description - describe their stance, readiness, or threatening demeanor."
    else:
        instruction = ""

    # Build lighting context for narrative
    lighting_context = ""
    light_casters = room_data.get("light_casters", [])

    if base_lighting == "dark":
        # Check if anyone can see
        can_see_bright = []
        can_see_dim = []
        cannot_see = []

        for char_lighting in party_lighting:
            if char_lighting["lighting"] == "bright":
                can_see_bright.append(char_lighting['character'])
            elif char_lighting["lighting"] == "dim":
                if char_lighting["has_darkvision"]:
                    can_see_dim.append(char_lighting['character'])
                else:
                    cannot_see.append(char_lighting['character'])
            else:  # dark
                cannot_see.append(char_lighting['character'])

        # Build natural language lighting description
        if light_casters:
            # Someone cast Light spell - mention them specifically
            if len(light_casters) == 1:
                light_source = f"{light_casters[0]}'s Light spell"
            elif len(light_casters) == 2:
                light_source = f"{light_casters[0]} and {light_casters[1]}'s Light spells"
            else:
                light_source = f"{', '.join(light_casters[:-1])}, and {light_casters[-1]}'s Light spells"

            if cannot_see:
                lighting_context = f"\n\nLighting: The room is pitch black, but {light_source} illuminates the area for the party. Describe the magical light cutting through the darkness."
            else:
                lighting_context = f"\n\nLighting: {light_source} pierces the darkness, revealing the chamber in bright magical light."
        elif can_see_bright:
            # Can see bright but no Light spell tracked - generic
            lighting_context = f"\n\nLighting: Magical light illuminates the darkness."
        elif can_see_dim and not cannot_see:
            # Everyone has darkvision
            lighting_context = f"\n\nLighting: The room is pitch black, but the party sees through the darkness with darkvision - limited grayscale vision. Describe muted colors and shadows."
        elif can_see_dim and cannot_see:
            # Mixed darkvision
            lighting_context = f"\n\nLighting: The room is pitch black. {', '.join(can_see_dim)} see through the darkness with darkvision, but {', '.join(cannot_see)} are blind. Emphasize the contrast."
        else:
            # Nobody can see
            lighting_context = f"\n\nLighting: The room is pitch black. The party cannot see anything - describe only non-visual sensory details (sounds, smells, textures, echoes, temperature). Emphasize the oppressive darkness and disorientation."

    elif base_lighting == "dim":
        lighting_context = "\n\nLighting: The room is dimly lit with shadows and limited visibility. Describe how shapes are unclear, colors are muted, and details are hard to make out. Create an atmosphere of uncertainty and gloom."

    # If bright, no special lighting context needed

    # Build transition narrative instruction
    transition_instruction = ""
    if is_entering:
        transition_instruction = "\n\nNarrative Context: The party is ENTERING this room. Include a brief transition that describes their entrance (e.g., 'As you step through the doorway...' or 'Leaving the previous chamber behind...'). Make it feel like they're arriving for the first time."
    else:
        transition_instruction = "\n\nNarrative Context: The party is already IN this room, examining it more closely. Do NOT describe them entering or transitioning - they're already here. Focus on what they observe in the moment."

    prompt = f"""Enhance this D&D dungeon room description with atmospheric details:

Room: {room_type}
Basic description: {base_desc}{monster_context}{lighting_context}{transition_instruction}

Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. Make it immersive but concise.{instruction}

IMPORTANT: If lighting context is provided above, you MUST incorporate it into your description. The lighting level dramatically affects what can be perceived and should be central to the atmosphere."""

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
