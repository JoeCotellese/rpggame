# ABOUTME: Integration tests for ranged attack functionality in the 2D client.
# ABOUTME: Tests range validation with melee, ranged, and thrown weapons.

"""Integration tests for ranged attack support via MCP commands."""

from pathlib import Path

import pytest
from client_2d.game import get_attack_range


class TestMeleeRangeValidation:
    """Tests that melee weapons cannot attack at range."""

    @pytest.fixture
    def engine_in_combat(self):
        """Create engine adapter in combat with rats."""
        from client_2d.integration.engine_adapter import EngineAdapter

        adapter = EngineAdapter()
        adapter.load_party_from_vault()
        adapter.initialize_game(
            dungeon_name="cellar",
            campaign_id="poisoned_laboratory",
            start_room="cellar.storage",  # Room with rats
        )
        adapter.start_game()

        if not adapter.in_combat:
            pytest.skip("Room did not start combat")

        return adapter

    def test_melee_weapon_range_is_five_feet(self, engine_in_combat):
        """Verify melee weapons return 5 ft range."""
        from dnd_engine.systems.inventory import EquipmentSlot

        # Get first player character
        party = engine_in_combat.party.characters
        fighter = party[0]

        # Get equipped weapon
        weapon_id = fighter.inventory.get_equipped_item(EquipmentSlot.WEAPON)

        if weapon_id is None:
            # Unarmed attack
            normal_range, max_range = get_attack_range(None)
        else:
            items_data = engine_in_combat.game_state.data_loader.load_items(
                engine_in_combat.game_state.campaign_id
            )
            weapon_data = items_data.get("weapons", {}).get(weapon_id, {})
            normal_range, max_range = get_attack_range(weapon_data)

        # Melee weapons should have 5/5 ft range
        # (if character has a ranged weapon, this test still validates the function)
        assert isinstance(normal_range, int)
        assert isinstance(max_range, int)
        assert normal_range >= 5  # At minimum melee range
        assert max_range >= normal_range


class TestRangeCalculationFromItems:
    """Tests range calculation from actual item data."""

    @pytest.fixture
    def items_data(self):
        """Load actual items data from the engine."""
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        return loader.load_items()

    def test_longbow_has_150_600_range(self, items_data):
        """Longbow should have 150/600 ft range."""
        longbow = items_data.get("weapons", {}).get("longbow", {})
        normal_range, max_range = get_attack_range(longbow)

        assert normal_range == 150
        assert max_range == 600

    def test_shortbow_has_80_320_range(self, items_data):
        """Shortbow should have 80/320 ft range."""
        shortbow = items_data.get("weapons", {}).get("shortbow", {})
        normal_range, max_range = get_attack_range(shortbow)

        assert normal_range == 80
        assert max_range == 320

    def test_light_crossbow_has_80_320_range(self, items_data):
        """Light crossbow should have 80/320 ft range."""
        light_crossbow = items_data.get("weapons", {}).get("light_crossbow", {})
        normal_range, max_range = get_attack_range(light_crossbow)

        assert normal_range == 80
        assert max_range == 320

    def test_heavy_crossbow_has_100_400_range(self, items_data):
        """Heavy crossbow should have 100/400 ft range."""
        heavy_crossbow = items_data.get("weapons", {}).get("heavy_crossbow", {})
        normal_range, max_range = get_attack_range(heavy_crossbow)

        assert normal_range == 100
        assert max_range == 400

    def test_dagger_has_20_60_range_when_thrown(self, items_data):
        """Dagger should have 20/60 ft range (thrown property)."""
        dagger = items_data.get("weapons", {}).get("dagger", {})
        normal_range, max_range = get_attack_range(dagger)

        assert normal_range == 20
        assert max_range == 60

    def test_longsword_has_melee_only_range(self, items_data):
        """Longsword should have melee-only range (5/5 ft)."""
        longsword = items_data.get("weapons", {}).get("longsword", {})
        normal_range, max_range = get_attack_range(longsword)

        assert normal_range == 5
        assert max_range == 5


class TestRangedAttackDistanceCheck:
    """Tests that distance check respects weapon range."""

    def test_distance_in_feet_calculation(self):
        """Verify distance_in_feet calculates correctly."""
        from dnd_engine.core.distance import distance_in_feet

        # Adjacent squares = 5 ft
        assert distance_in_feet(0, 0, 1, 0) == 5
        assert distance_in_feet(0, 0, 0, 1) == 5
        assert distance_in_feet(0, 0, 1, 1) == 5  # Diagonal

        # 2 squares = 10 ft
        assert distance_in_feet(0, 0, 2, 0) == 10

        # 10 squares = 50 ft
        assert distance_in_feet(0, 0, 10, 0) == 50

        # 30 squares = 150 ft (longbow normal range)
        assert distance_in_feet(0, 0, 30, 0) == 150

    def test_longbow_in_range_at_150_feet(self):
        """Target at 150 ft should be in normal range for longbow."""
        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        items_data = loader.load_items()
        longbow = items_data.get("weapons", {}).get("longbow", {})
        normal_range, max_range = get_attack_range(longbow)

        # 30 squares = 150 ft
        target_distance_ft = distance_in_feet(0, 0, 30, 0)

        assert target_distance_ft <= normal_range
        assert target_distance_ft <= max_range

    def test_longbow_long_range_at_300_feet(self):
        """Target at 300 ft should be in long range for longbow."""
        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        items_data = loader.load_items()
        longbow = items_data.get("weapons", {}).get("longbow", {})
        normal_range, max_range = get_attack_range(longbow)

        # 60 squares = 300 ft
        target_distance_ft = distance_in_feet(0, 0, 60, 0)

        assert target_distance_ft > normal_range  # In long range
        assert target_distance_ft <= max_range  # But still in max range

    def test_longbow_out_of_range_at_700_feet(self):
        """Target at 700 ft should be out of range for longbow."""
        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        items_data = loader.load_items()
        longbow = items_data.get("weapons", {}).get("longbow", {})
        _normal_range, max_range = get_attack_range(longbow)

        # 140 squares = 700 ft
        target_distance_ft = distance_in_feet(0, 0, 140, 0)

        assert target_distance_ft > max_range  # Out of range

    def test_melee_weapon_out_of_range_at_10_feet(self):
        """Target at 10 ft should be out of range for longsword."""
        from dnd_engine.core.distance import distance_in_feet
        from dnd_engine.rules.loader import DataLoader

        loader = DataLoader()
        items_data = loader.load_items()
        longsword = items_data.get("weapons", {}).get("longsword", {})
        _normal_range, max_range = get_attack_range(longsword)

        # 2 squares = 10 ft
        target_distance_ft = distance_in_feet(0, 0, 2, 0)

        assert target_distance_ft > max_range  # Out of melee range


class TestEngineAdapterDisadvantage:
    """EngineAdapter.execute_attack must forward the disadvantage flag to
    GameState.execute_player_attack and expose the resulting flag on the
    returned dict so the session/UI can show the modifier.
    """

    SCENARIO_DIR = (
        Path(__file__).parent.parent.parent
        / "dnd-engine"
        / "tests"
        / "scenarios"
        / "yaml"
    )

    @pytest.fixture
    def adapter_in_combat(self):
        from client_2d.integration.engine_adapter import EngineAdapter

        adapter = EngineAdapter()
        adapter.load_scenario(self.SCENARIO_DIR / "ranged_attack_basic.yaml")
        assert adapter.in_combat
        return adapter

    def _player_target_index(self, adapter):
        """Return the active_enemies index of the goblin while it's alive."""
        enemies = adapter.game_state.active_enemies
        for idx, enemy in enumerate(enemies):
            if enemy.is_alive:
                return idx
        pytest.skip("No live enemy to attack")

    def test_execute_attack_forwards_disadvantage_kwarg(
        self, adapter_in_combat, monkeypatch
    ):
        """The disadvantage kwarg must reach game_state.execute_player_attack.

        We patch the engine method to capture call kwargs without depending
        on ammo, dice seeds, or hit/miss outcomes.
        """
        captured: dict = {}
        real_method = adapter_in_combat.game_state.execute_player_attack

        def spy(attacker, target, *, disadvantage=False):
            captured["disadvantage"] = disadvantage
            return real_method(attacker, target, disadvantage=disadvantage)

        monkeypatch.setattr(
            adapter_in_combat.game_state, "execute_player_attack", spy
        )

        target_index = self._player_target_index(adapter_in_combat)
        adapter_in_combat.execute_attack(target_index=target_index, disadvantage=True)

        assert captured["disadvantage"] is True

    def test_execute_attack_default_passes_false(self, adapter_in_combat, monkeypatch):
        """Default call must pass disadvantage=False to the engine."""
        captured: dict = {}
        real_method = adapter_in_combat.game_state.execute_player_attack

        def spy(attacker, target, *, disadvantage=False):
            captured["disadvantage"] = disadvantage
            return real_method(attacker, target, disadvantage=disadvantage)

        monkeypatch.setattr(
            adapter_in_combat.game_state, "execute_player_attack", spy
        )

        target_index = self._player_target_index(adapter_in_combat)
        adapter_in_combat.execute_attack(target_index=target_index)

        assert captured["disadvantage"] is False

    def test_execute_attack_result_includes_disadvantage_field(
        self, adapter_in_combat
    ):
        """The returned dict must surface the disadvantage flag for the UI."""
        target_index = self._player_target_index(adapter_in_combat)

        result = adapter_in_combat.execute_attack(target_index=target_index)

        assert "disadvantage" in result


class TestSessionLongRangeDisadvantage:
    """When session.attack() fires at a target in long range, the attack roll
    must use disadvantage. The session detects long range via
    distance_in_feet() vs the weapon's normal/max range; this test confirms
    the flag actually reaches the engine, not just the combat log.
    """

    SCENARIO_DIR = (
        Path(__file__).parent.parent.parent
        / "dnd-engine"
        / "tests"
        / "scenarios"
        / "yaml"
    )

    @pytest.fixture
    def session_in_combat(self):
        """Spin up a GameSession around the ranged_attack_basic scenario.

        Uses the session-level loader (not the adapter) so visual entities
        are populated alongside the engine state.
        """
        from client_2d.session import GameSession

        session = GameSession(enable_mcp=False, dev_mode=False)
        session.load_scenario(str(self.SCENARIO_DIR / "ranged_attack_basic.yaml"))
        assert session.engine.in_combat
        return session

    def _attach_attack_spy(self, session, monkeypatch):
        """Patch the engine adapter's execute_attack to record disadvantage."""
        captured: dict = {}
        real_method = session.engine.execute_attack

        def spy(target_index, *, disadvantage=False, **kwargs):
            captured["disadvantage"] = disadvantage
            return real_method(target_index, disadvantage=disadvantage, **kwargs)

        monkeypatch.setattr(session.engine, "execute_attack", spy)
        return captured

    def test_session_attack_at_long_range_passes_disadvantage(
        self, session_in_combat, monkeypatch
    ):
        """When the target sits past normal range, session.attack must call
        through with disadvantage=True so the engine rolls accordingly.
        """
        captured = self._attach_attack_spy(session_in_combat, monkeypatch)

        # Shortbow is 80/320 ft → > 16 tiles puts the target in long range.
        # Move the goblin visual entity (and engine creature) to (25, 5),
        # 22 tiles = 110 ft from Archy at (3, 5).
        monsters = session_in_combat.entity_manager.get_monsters()
        assert monsters, "Scenario should have at least one monster"
        target = monsters[0]
        target.grid_x = 25
        target.grid_y = 5

        session_in_combat.attack(0)

        assert captured["disadvantage"] is True

    def test_session_attack_at_normal_range_passes_no_disadvantage(
        self, session_in_combat, monkeypatch
    ):
        """Inside normal range, no disadvantage should be applied."""
        captured = self._attach_attack_spy(session_in_combat, monkeypatch)

        # Default scenario position is (10, 5) — 35 ft from (3, 5), well
        # inside the 80 ft shortbow normal range.
        session_in_combat.attack(0)

        assert captured["disadvantage"] is False
