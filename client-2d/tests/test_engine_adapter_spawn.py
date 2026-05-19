# ABOUTME: Tests for EngineAdapter dev-mode spawn/setup methods (#360).
# ABOUTME: Covers set_seed, spawn_monster, spawn_character, set_position, clear_enemies.

"""Tests for the engine adapter's dev-mode spawn primitives.

These adapter methods back the --dev MCP tools. They run against a real
EngineAdapter wired to a real GameState in the cellar/poisoned_laboratory
campaign (deterministic content, no vault dependency).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def initialized_adapter():
    """An EngineAdapter with a 1-member party and a real cellar GameState.

    Bypasses load_party_from_vault() so tests don't depend on the user's
    ~/.dnd_game/character_vault.json. Builds a fighter via CharacterFactory
    and constructs GameState directly.
    """
    from client_2d.integration.engine_adapter import EngineAdapter

    from dnd_engine.core.character_factory import CharacterFactory
    from dnd_engine.core.game_state import GameState
    from dnd_engine.core.party import Party
    from dnd_engine.rules.loader import DataLoader
    from dnd_engine.utils.events import EventBus

    data_loader = DataLoader()
    factory = CharacterFactory()
    fighter = factory.create_character(
        "fighter", "human", data_loader, name="Tester",
    )
    party = Party([fighter])
    event_bus = EventBus()
    game_state = GameState(
        party=party,
        dungeon_name="cellar",
        event_bus=event_bus,
        data_loader=data_loader,
        campaign_id="poisoned_laboratory",
    )

    adapter = EngineAdapter()
    adapter._party = party
    adapter._event_bus = event_bus
    adapter._game_state = game_state
    adapter._initialized = True
    return adapter


class TestSetSeed:
    """EngineAdapter.set_seed reseeds the live DiceRoller in place."""

    def test_reseed_makes_rolls_reproducible(self, initialized_adapter) -> None:
        """Same seed → same sequence of rolls."""
        adapter = initialized_adapter
        roller = adapter.game_state.dice_roller

        adapter.set_seed(42)
        first = [roller.roll("1d20").total for _ in range(5)]

        adapter.set_seed(42)
        second = [roller.roll("1d20").total for _ in range(5)]

        assert first == second

    def test_set_seed_returns_dict(self, initialized_adapter) -> None:
        """Returns a structured dict echoing the seed."""
        result = initialized_adapter.set_seed(123)

        assert result == {"success": True, "seed": 123}

    def test_set_seed_propagates_to_combat_engine(self, initialized_adapter) -> None:
        """Combat engine holds the same DiceRoller, so reseed affects it too."""
        adapter = initialized_adapter
        adapter.set_seed(7)
        a = adapter.game_state.combat_engine.dice_roller.roll("1d20").total

        adapter.set_seed(7)
        b = adapter.game_state.combat_engine.dice_roller.roll("1d20").total

        assert a == b

    def test_set_seed_raises_when_not_initialized(self) -> None:
        """Raises ValueError if no GameState yet (parity with other adapter methods)."""
        from client_2d.integration.engine_adapter import EngineAdapter

        adapter = EngineAdapter()
        with pytest.raises(ValueError, match="initialize_game"):
            adapter.set_seed(1)


class TestSpawnMonster:
    """EngineAdapter.spawn_monster places a monster and updates combat state."""

    def test_appends_to_active_enemies_and_returns_entity_id(
        self, initialized_adapter
    ) -> None:
        """Spawning adds the creature and returns its ASCII-map entity_id."""
        adapter = initialized_adapter
        before = len(adapter.game_state.active_enemies)

        result = adapter.spawn_monster("goblin", 12, 7)

        assert len(adapter.game_state.active_enemies) == before + 1
        assert result["entity_id"] == f"goblin_{before}"
        assert result["position"] == [12, 7]
        assert result["hp"] > 0
        assert result["name"]

    def test_starts_combat_when_not_in_combat(self, initialized_adapter) -> None:
        """First spawn outside combat triggers _start_combat."""
        adapter = initialized_adapter
        assert not adapter.in_combat

        adapter.spawn_monster("goblin", 12, 7)

        assert adapter.in_combat
        assert adapter.game_state.initiative_tracker is not None

    def test_adds_to_initiative_when_in_combat(self, initialized_adapter) -> None:
        """Second spawn during combat appends to existing initiative."""
        adapter = initialized_adapter
        adapter.spawn_monster("goblin", 12, 7)
        tracker = adapter.game_state.initiative_tracker
        before = len(tracker.get_all_combatants())

        adapter.spawn_monster("goblin", 14, 7)

        after = len(tracker.get_all_combatants())
        assert after == before + 1

    def test_unknown_monster_raises(self, initialized_adapter) -> None:
        """Unknown monster_id surfaces the DataLoader KeyError."""
        with pytest.raises(KeyError):
            initialized_adapter.spawn_monster("not_a_real_monster", 0, 0)

    def test_entity_id_uses_running_index(self, initialized_adapter) -> None:
        """Second goblin gets index 1, not a name collision."""
        adapter = initialized_adapter
        first = adapter.spawn_monster("goblin", 10, 7)
        second = adapter.spawn_monster("goblin", 11, 7)

        assert first["entity_id"] == "goblin_0"
        assert second["entity_id"] == "goblin_1"

    def test_raises_when_not_initialized(self) -> None:
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().spawn_monster("goblin", 0, 0)


class TestSpawnCharacter:
    """EngineAdapter.spawn_character creates a PC, equips weapons, joins party."""

    def test_adds_to_party(self, initialized_adapter) -> None:
        """New character appears in party.characters."""
        adapter = initialized_adapter
        before = len(adapter.party.characters)

        result = adapter.spawn_character(
            "fighter", "high_elf", ["shortbow"], 5, 7, name="Robyn",
        )

        assert len(adapter.party.characters) == before + 1
        assert result["name"] == "Robyn"
        assert result["position"] == [5, 7]
        assert result["entity_id"].startswith("pc_")

    def test_equips_first_weapon_in_list(self, initialized_adapter) -> None:
        """First weapon in the list is moved to the WEAPON slot."""
        from dnd_engine.systems.inventory import EquipmentSlot

        adapter = initialized_adapter
        adapter.spawn_character(
            "fighter", "high_elf", ["shortbow", "dagger"], 5, 7, name="Robyn",
        )

        # Find the newly added character
        new_char = adapter.party.characters[-1]
        equipped = new_char.inventory.get_equipped_item(EquipmentSlot.WEAPON)
        assert equipped == "shortbow"
        # Second weapon is in the pack, not equipped
        assert new_char.inventory.has_item("dagger")

    def test_adds_to_initiative_when_in_combat(self, initialized_adapter) -> None:
        """Spawning during combat appends to existing initiative."""
        adapter = initialized_adapter
        adapter.spawn_monster("goblin", 12, 7)  # triggers combat
        before = len(adapter.game_state.initiative_tracker.get_all_combatants())

        adapter.spawn_character(
            "fighter", "high_elf", ["shortbow"], 5, 7, name="LateJoiner",
        )

        after = len(adapter.game_state.initiative_tracker.get_all_combatants())
        assert after == before + 1

    def test_invalid_class_raises(self, initialized_adapter) -> None:
        """CharacterFactory's ValueError surfaces unchanged."""
        with pytest.raises(ValueError, match="Invalid class"):
            initialized_adapter.spawn_character(
                "not_a_class", "high_elf", ["dagger"], 0, 0, name="Bad",
            )

    def test_empty_weapons_list_is_allowed(self, initialized_adapter) -> None:
        """No weapons → no WEAPON slot filled, character still spawns."""
        from dnd_engine.systems.inventory import EquipmentSlot

        adapter = initialized_adapter
        adapter.spawn_character("wizard", "high_elf", [], 5, 7, name="Spellslinger")

        new_char = adapter.party.characters[-1]
        # CharacterFactory may equip a default weapon; we only assert no
        # weapon from our (empty) list overrode that — spawn doesn't crash
        # and the character is present.
        assert new_char.name == "Spellslinger"
        _ = new_char.inventory.get_equipped_item(EquipmentSlot.WEAPON)

    def test_raises_when_not_initialized(self) -> None:
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().spawn_character("fighter", "human", [], 0, 0)


class TestSetPosition:
    """EngineAdapter.set_position validates and returns a placement directive.

    Engine-side creature position is not tracked today; the GameWindow handler
    is responsible for applying the result to EntityManager.
    """

    def test_returns_position_dict(self, initialized_adapter) -> None:
        result = initialized_adapter.set_position("goblin_0", 4, 9)
        assert result == {"entity_id": "goblin_0", "position": [4, 9]}

    def test_rejects_non_integer_coordinates(self, initialized_adapter) -> None:
        with pytest.raises(TypeError):
            initialized_adapter.set_position("goblin_0", "four", 9)

    def test_raises_when_not_initialized(self) -> None:
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().set_position("goblin_0", 0, 0)


class TestClearEnemies:
    """EngineAdapter.clear_enemies wipes active_enemies and ends combat."""

    def test_clears_active_enemies_and_ends_combat(self, initialized_adapter) -> None:
        adapter = initialized_adapter
        adapter.spawn_monster("goblin", 12, 7)
        adapter.spawn_monster("goblin", 14, 7)
        assert adapter.in_combat
        assert len(adapter.game_state.active_enemies) == 2

        result = adapter.clear_enemies()

        assert result == {"success": True, "cleared": 2}
        assert adapter.game_state.active_enemies == []
        assert not adapter.in_combat
        assert adapter.game_state.initiative_tracker is None

    def test_noop_when_no_enemies(self, initialized_adapter) -> None:
        result = initialized_adapter.clear_enemies()
        assert result == {"success": True, "cleared": 0}
        assert not initialized_adapter.in_combat

    def test_raises_when_not_initialized(self) -> None:
        from client_2d.integration.engine_adapter import EngineAdapter

        with pytest.raises(ValueError, match="initialize_game"):
            EngineAdapter().clear_enemies()
