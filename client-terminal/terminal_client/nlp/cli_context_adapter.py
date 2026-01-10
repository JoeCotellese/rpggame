# ABOUTME: Adapter that connects the CommandParser to CLI game state.
# ABOUTME: Implements GameContextProvider protocol to provide game context for fuzzy matching.

from dnd_engine.core.game_state import GameState
from dnd_engine.nlp.command_parser import GameContextProvider


class CLIContextAdapter(GameContextProvider):
    """
    Adapter that provides game context from GameState to CommandParser.

    Implements the GameContextProvider protocol to enable fuzzy matching
    of enemies, items, spells, NPCs, and party members.
    """

    def __init__(self, game_state: GameState) -> None:
        """
        Initialize the context adapter.

        Args:
            game_state: The game state to extract context from
        """
        self.game_state = game_state

    def get_available_enemies(self) -> list[str]:
        """Return list of enemy names currently in combat."""
        if not self.game_state.in_combat or not self.game_state.initiative_tracker:
            return []

        enemies = []
        for entry in self.game_state.initiative_tracker.order:
            # Skip party members
            if entry.creature in self.game_state.party.characters:
                continue
            # Skip dead enemies
            if entry.creature.current_hp <= 0:
                continue
            # Get display name with number
            display_name = self.game_state.initiative_tracker.get_combatant_display_name(
                entry.creature
            )
            enemies.append(display_name)

        return enemies

    def get_available_items(self) -> list[str]:
        """Return list of item names available (room + inventory)."""
        items = []

        # Get items from current room
        room_items = self.game_state.get_room_items()
        for item in room_items:
            if item.get("type") not in ("gold", "currency"):
                item_name = item.get("name", item.get("id", "unknown"))
                items.append(item_name)

        # Get items from party inventories
        for char in self.game_state.party.characters:
            if char.is_alive:
                # Get consumables
                consumables = char.inventory.get_items_by_category("consumables")
                for inv_item in consumables:
                    item_data = self.game_state.data_loader.load_items(
                        self.game_state.campaign_id
                    ).get(inv_item.item_id, {})
                    item_name = item_data.get("name", inv_item.item_id)
                    if item_name not in items:
                        items.append(item_name)

                # Get equipment
                for slot in char.inventory.equipment.values():
                    if slot:
                        item_data = self.game_state.data_loader.load_items(
                            self.game_state.campaign_id
                        ).get(slot.item_id, {})
                        item_name = item_data.get("name", slot.item_id)
                        if item_name not in items:
                            items.append(item_name)

        return items

    def get_available_spells(self) -> list[str]:
        """Return list of spell names the active character can cast."""
        spells = []

        # Get current character (in combat: current combatant, else: first party member)
        if self.game_state.in_combat and self.game_state.initiative_tracker:
            current = self.game_state.initiative_tracker.get_current_combatant()
            if current and current.creature in self.game_state.party.characters:
                char = current.creature
            else:
                return []
        else:
            # Exploration mode - get first living party member
            for char in self.game_state.party.characters:
                if char.is_alive:
                    break
            else:
                return []

        # Get cantrips (always available)
        for spell_id in char.spells.cantrips:
            spell_data = self.game_state.data_loader.load_spells(
                self.game_state.campaign_id
            ).get(spell_id, {})
            spell_name = spell_data.get("name", spell_id)
            spells.append(spell_name)

        # Get prepared/known spells
        if char.spells.prepared_spells:
            for spell_id in char.spells.prepared_spells:
                spell_data = self.game_state.data_loader.load_spells(
                    self.game_state.campaign_id
                ).get(spell_id, {})
                spell_name = spell_data.get("name", spell_id)
                if spell_name not in spells:
                    spells.append(spell_name)
        elif char.spells.known_spells:
            for spell_id in char.spells.known_spells:
                spell_data = self.game_state.data_loader.load_spells(
                    self.game_state.campaign_id
                ).get(spell_id, {})
                spell_name = spell_data.get("name", spell_id)
                if spell_name not in spells:
                    spells.append(spell_name)

        return spells

    def get_available_npcs(self) -> list[str]:
        """Return list of NPC names in the current room."""
        npcs = []
        if self.game_state.npc_manager:
            npc_list = self.game_state.npc_manager.get_npcs_in_room(
                self.game_state.current_room_id
            )
            for npc in npc_list:
                npcs.append(npc.name)
        return npcs

    def get_party_member_names(self) -> list[str]:
        """Return list of party member names."""
        return [char.name for char in self.game_state.party.characters if char.is_alive]

    def is_in_combat(self) -> bool:
        """Return True if currently in combat."""
        return self.game_state.in_combat
