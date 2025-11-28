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

    # Room significance determines description length
    # "minor" = transition rooms, hallways (1 sentence)
    # "standard" = typical rooms (2-3 sentences)
    # "major" = story beats, boss rooms, reveals (3-4 sentences)
    significance = room_data.get("significance", "standard")

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
                creature_types.append(
                    {
                        "name": monster_name,
                        "type": creature_type,
                        "size": size,
                        "alignment": alignment,
                    }
                )

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
                            "- Undead: mechanical precision, relentless advance, emotionless determination"
                        )
                    elif "beast" in ctype.lower():
                        type_examples.append(
                            "- Beasts: snarling, prowling, feral aggression, instinctive pack behavior"
                        )
                    elif "humanoid" in ctype.lower():
                        type_examples.append(
                            "- Humanoids: tactical positioning, drawing weapons, battle cries, coordinated movements"
                        )

            if type_examples:
                creature_behavior_guide = "\n\nCreature behavior guide:\n" + "\n".join(
                    type_examples
                )

    # Build instruction based on whether combat is starting
    if combat_starting and monster_context:
        party_context = f"Party size: {party_size} adventurer{'s' if party_size != 1 else ''}\n"
        instruction = (
            f"Add vivid sensory details (sights, sounds, smells) in 2-3 sentences. "
            f"Make it immersive but concise.\n\n"
            f"IMPORTANT: This is the moment combat begins. Naturally transition from "
            f"describing the room into the combat initiation - describe how the enemies "
            f"react to the party's presence using behavior appropriate to their nature. "
            f"Show their threatening stance or aggressive movement toward the party, "
            f"and the immediate tension as battle is about to erupt. Make it feel like "
            f"a seamless escalation from scene-setting to action. Do NOT use phrases "
            f"like \"combat begins\" - show it through the enemies' actions and the "
            f"rising tension.\n\n"
            f"{party_context}{creature_behavior_guide}"
        )
    elif monster_context:
        instruction = (
            " Acknowledge the presence of hostile creatures naturally in your "
            "description - describe their stance, readiness, or threatening demeanor."
        )
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
                can_see_bright.append(char_lighting["character"])
            elif char_lighting["lighting"] == "dim":
                if char_lighting["has_darkvision"]:
                    can_see_dim.append(char_lighting["character"])
                else:
                    cannot_see.append(char_lighting["character"])
            else:  # dark
                cannot_see.append(char_lighting["character"])

        # Build natural language lighting description
        if light_casters:
            # Someone cast Light spell - mention them specifically
            if len(light_casters) == 1:
                light_source = f"{light_casters[0]}'s Light spell"
            elif len(light_casters) == 2:
                light_source = f"{light_casters[0]} and {light_casters[1]}'s Light spells"
            else:
                light_source = (
                    f"{', '.join(light_casters[:-1])}, and {light_casters[-1]}'s Light spells"
                )

            if cannot_see:
                lighting_context = (
                    f"\n\nLighting: The room is pitch black, but {light_source} "
                    f"illuminates the area for the party. "
                    f"Describe the magical light cutting through the darkness."
                )
            else:
                lighting_context = (
                    f"\n\nLighting: {light_source} pierces the darkness, "
                    f"revealing the chamber in bright magical light."
                )
        elif can_see_bright:
            # Can see bright but no Light spell tracked - generic
            lighting_context = "\n\nLighting: Magical light illuminates the darkness."
        elif can_see_dim and not cannot_see:
            # Everyone has darkvision
            lighting_context = (
                "\n\nLighting: The room is pitch black, but the party sees through "
                "the darkness with darkvision - limited grayscale vision. "
                "Describe muted colors and shadows."
            )
        elif can_see_dim and cannot_see:
            # Mixed darkvision
            lighting_context = (
                f"\n\nLighting: The room is pitch black. "
                f"{', '.join(can_see_dim)} see through the darkness with darkvision, "
                f"but {', '.join(cannot_see)} are blind. Emphasize the contrast."
            )
        else:
            # Nobody can see
            lighting_context = (
                "\n\nLighting: The room is pitch black. The party cannot see "
                "anything - describe only non-visual sensory details (sounds, smells, "
                "textures, echoes, temperature). Emphasize the oppressive darkness "
                "and disorientation."
            )

    elif base_lighting == "dim":
        lighting_context = (
            "\n\nLighting: The room is dimly lit with shadows and limited visibility. "
            "Describe how shapes are unclear, colors are muted, and details are hard "
            "to make out. Create an atmosphere of uncertainty and gloom."
        )

    # If bright, no special lighting context needed

    # POV and style constraints
    pov_constraint = (
        "\n\nSTYLE RULES:\n"
        "- Use third-person, never \"you\" (player controls multiple characters)\n"
        "- NEVER describe arrival, stepping into, entering, or movement\n"
        "- Just describe what IS HERE - the space, atmosphere, and contents\n"
        "- Write as if describing a snapshot, not a transition"
    )

    # Determine description length based on significance and combat
    # Combat starting = keep it short, players want to fight
    if combat_starting:
        length_instruction = "1-2 sentences max (40 words). Combat is imminent - be brief."
    elif significance == "minor":
        length_instruction = "1 sentence (20 words max). This is a transition space."
    elif significance == "major":
        length_instruction = "3-4 sentences (80 words max). This is a significant location."
    else:  # standard
        length_instruction = "2-3 sentences (50 words max). Sensory details only."

    prompt = (
        f"Enhance this D&D room description:\n\n"
        f"Room: {room_type}\n"
        f"Basic description: {base_desc}{monster_context}{lighting_context}"
        f"{pov_constraint}\n\n"
        f"LENGTH: {length_instruction}{instruction}"
    )

    return prompt


def build_combat_action_prompt(action_data: dict[str, Any]) -> str:
    """
    Build prompt for combat action narration with tiered verbosity.

    Uses minimal context for regular hits, more for crits, full context for
    killing blows. This keeps combat snappy while preserving drama for
    significant moments.

    Args:
        action_data: Combat details including:
            - attacker, defender, weapon, hit/miss, location
            - is_critical: Whether this was a critical hit
            - is_killing_blow: Whether this kills the target
            - combat_history: List of recent action summaries (used for crits+)
            - battlefield_state: Current HP status (used for killing blows)

    Returns:
        Formatted prompt for LLM
    """
    attacker = action_data.get("attacker", "Someone")
    defender = action_data.get("defender", "something")
    weapon = action_data.get("weapon", "weapon")
    hit = action_data.get("hit", False)
    location = action_data.get("location", "")

    # Action significance - determines how much context to include
    is_critical = action_data.get("is_critical", False)
    is_killing_blow = action_data.get("is_killing_blow", False)

    # Combat history and battlefield state - only used for significant actions
    combat_history = action_data.get("combat_history", [])
    battlefield_state = action_data.get("battlefield_state", {})

    # Additional context for narrative richness
    damage_type = action_data.get("damage_type", "")

    # Build context strings - location always included
    location_context = f"Location: {location}\n" if location else ""

    # Build combat history context - only for crits and killing blows
    history_context = ""
    if (is_critical or is_killing_blow) and combat_history:
        # Crits get last 2 actions, killing blows get last 4
        history_count = 4 if is_killing_blow else 2
        history_lines = []
        for i, action in enumerate(combat_history[-history_count:], 1):
            history_lines.append(f"  {i}. {action}")
        history_context = "Recent Actions:\n" + "\n".join(history_lines) + "\n\n"

    # Build battlefield state context - only for killing blows
    battlefield_context = ""
    if is_killing_blow and battlefield_state:
        party_combatants = getattr(battlefield_state, "party_combatants", [])
        enemy_combatants = getattr(battlefield_state, "enemy_combatants", [])

        if party_combatants or enemy_combatants:
            party_status = ", ".join(
                [
                    f"{c.display_name} {c.current_hp}/{c.max_hp}"
                    for c in party_combatants
                    if c.is_alive
                ]
            )
            enemy_status = ", ".join(
                [
                    f"{c.display_name} {c.current_hp}/{c.max_hp}"
                    for c in enemy_combatants
                    if c.is_alive
                ]
            )
            battlefield_context = (
                f"Battlefield: Party [{party_status}] | Enemies [{enemy_status}]\n\n"
            )

    # Build weapon description
    weapon_desc = weapon
    if damage_type:
        weapon_desc = f"{weapon} ({damage_type})"

    # Third-person constraint - player controls multiple characters
    pov_constraint = "Use third-person (character names), never \"you\"."

    # Build the main prompt with tiered instructions
    if hit:
        if is_killing_blow:
            prompt = (
                f"Narrate this killing blow:\n\n"
                f"{location_context}{battlefield_context}{history_context}"
                f"{attacker} strikes down {defender} with their {weapon_desc}.\n\n"
                f"2-3 vivid sentences. {pov_constraint}"
            )
        elif is_critical:
            prompt = (
                f"Narrate this critical hit:\n\n"
                f"{location_context}{history_context}"
                f"{attacker} lands a devastating blow on {defender} "
                f"with their {weapon_desc}.\n\n"
                f"One visceral sentence (15-25 words). {pov_constraint}"
            )
        else:
            # Regular hit - minimal context, tight output
            prompt = (
                f"Narrate this combat hit:\n\n"
                f"{location_context}"
                f"{attacker} hits {defender} with their {weapon_desc}.\n\n"
                f"One sentence, under 20 words. {pov_constraint}"
            )
    else:
        # Misses are always brief - don't dwell on failure
        prompt = (
            f"Narrate this combat miss:\n\n"
            f"{location_context}"
            f"{attacker} swings at {defender} with their {weapon_desc} but misses.\n\n"
            f"One sentence, under 15 words. {pov_constraint}"
        )

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

    # Third-person constraint
    pov_constraint = "Use third-person (character names), never \"you\"."

    if is_player:
        # Player deaths deserve more narrative weight
        prompt = (
            f"Narrate a heroic D&D character death:\n\n"
            f"{name} {how_died}.\n\n"
            f"2-3 sentences about their final moments. Dramatic but respectful. "
            f"{pov_constraint}"
        )
    else:
        # Enemy deaths should be brief - killing blow already described the action
        prompt = (
            f"Narrate the defeat of {name}:\n\n"
            f"{name} {how_died}.\n\n"
            f"One brief sentence - the creature falls. {pov_constraint}"
        )

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

    prompt = (
        f"Narrate a D&D combat victory:\n\n"
        f"The party defeats {', '.join(enemies)}. The final blow: {final_blow}.\n\n"
        f"Describe the aftermath in 2-3 sentences. Capture the sense of triumph "
        f"and relief."
    )

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

    prompt = (
        f"Narrate the start of a D&D combat encounter:\n\n"
        f"{party_desc} encounters {enemy_desc}{location_context}.\n\n"
        f"Describe how combat begins in 2-3 dramatic sentences. Do the enemies "
        f"ambush the party, or does the party surprise them? Set the scene for "
        f"the battle to come."
    )

    return prompt
