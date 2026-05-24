# ABOUTME: Integration tests for EntityManager with real engine state.
# ABOUTME: Tests combat flow with entity sync, death removal, and party spread.

"""Integration tests for entity system with engine integration."""

import pytest
from client_2d.entities import EntityManager, EntityType


class TestEnemyIndexMapping:
    """Tests for enemy index mapping between display and engine indices.

    Bug context: When enemy at index 0 dies, get_enemies() returns remaining
    enemies but their "index" field contains the actual engine index, not
    their position in the filtered list. UI must use this index for attacks.
    """

    @pytest.fixture
    def engine_in_combat(self):
        """Create engine adapter already in combat with multiple enemies."""
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

    def test_get_enemies_returns_actual_indices(self, engine_in_combat):
        """Test that get_enemies() index field contains actual engine index."""
        enemies = engine_in_combat.get_enemies()

        assert len(enemies) > 0

        # Each enemy should have an index matching their position in active_enemies
        for enemy_info in enemies:
            idx = enemy_info["index"]
            actual_enemy = engine_in_combat.game_state.active_enemies[idx]
            assert actual_enemy.name == enemy_info["name"]
            assert actual_enemy.is_alive

    def test_attack_with_display_index_after_kill(self, engine_in_combat):
        """Test that using display index maps correctly after enemy dies.

        This tests the bug fix: if enemy 0 dies, display shows remaining
        enemies as [0, 1, 2...] but their actual indices might be [1, 2, 3...].
        """
        # Kill the first enemy by attacking repeatedly
        max_attacks = 30
        attacks = 0
        killed_first = False

        initial_enemies = engine_in_combat.get_enemies()
        if len(initial_enemies) < 2:
            pytest.skip("Need at least 2 enemies for this test")

        first_enemy_original_index = initial_enemies[0]["index"]

        while attacks < max_attacks and engine_in_combat.in_combat:
            if engine_in_combat.is_player_turn():
                # Always attack first enemy in display list
                enemies = engine_in_combat.get_enemies()
                if not enemies:
                    break

                # Use actual index from get_enemies, not display position
                actual_index = enemies[0]["index"]
                result = engine_in_combat.execute_attack(target_index=actual_index)
                attacks += 1

                if result["success"] and result.get("target_killed"):
                    if actual_index == first_enemy_original_index:
                        killed_first = True
                        break

                engine_in_combat.advance_turn()
            else:
                engine_in_combat.process_enemy_turn()
                engine_in_combat.advance_turn()

        if not killed_first:
            pytest.skip("Could not kill first enemy")

        # Now get remaining enemies
        remaining = engine_in_combat.get_enemies()
        if not remaining:
            pytest.skip("All enemies died")

        # The first enemy in display (index 0) should have actual index > 0
        # because the original index 0 enemy is dead
        first_remaining = remaining[0]

        # Attack using the actual index should succeed
        if engine_in_combat.in_combat and engine_in_combat.is_player_turn():
            result = engine_in_combat.execute_attack(
                target_index=first_remaining["index"]
            )
            # Should not fail with "Target is dead"
            assert result["success"] or "dead" not in result.get("error", "").lower()

    def test_display_index_zero_maps_to_correct_enemy(self, engine_in_combat):
        """Test that display index 0 always targets first LIVING enemy."""
        enemies = engine_in_combat.get_enemies()
        if not enemies:
            pytest.skip("No enemies")

        # Display index 0 should map to first living enemy
        display_zero_actual_index = enemies[0]["index"]
        target = engine_in_combat.game_state.active_enemies[display_zero_actual_index]

        assert target.is_alive
        assert target.name == enemies[0]["name"]


class TestEntityManagerEngineIntegration:
    """Integration tests for EntityManager with real engine."""

    @pytest.fixture
    def engine_adapter(self):
        """Create a real EngineAdapter for integration testing."""
        from client_2d.integration.engine_adapter import EngineAdapter

        adapter = EngineAdapter()
        adapter.load_party_from_vault()
        adapter.initialize_game(
            dungeon_name="cellar",
            campaign_id="poisoned_laboratory",
            start_room="cellar.storage",  # Room with rats
        )
        adapter.start_game()
        return adapter

    @pytest.fixture
    def layout_loader(self):
        """Create a real LayoutLoader."""
        from client_2d.integration.layout_loader import LayoutLoader

        return LayoutLoader()

    def test_load_from_room_creates_monster_entities(
        self, engine_adapter, layout_loader
    ):
        """Test EntityManager creates monster entities from engine state."""
        manager = EntityManager()

        # Load room layout
        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        # Load entities
        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        # Should have monster entities for active enemies
        monsters = manager.get_monsters()
        assert len(monsters) > 0

        # Each monster should have a creature reference
        for monster in monsters:
            assert monster.entity_type == EntityType.MONSTER
            assert monster._creature_ref is not None
            assert monster.hp > 0
            assert monster.is_alive is True

    def test_load_from_room_creates_item_entities(
        self, engine_adapter, layout_loader
    ):
        """Test EntityManager creates item entities from room data."""
        manager = EntityManager()

        # Load room with items
        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        # Check item entities exist if room has items
        items = manager.get_items()
        if room_data and room_data.get("items"):
            visible_items = [i for i in room_data["items"] if i.get("visible", True)]
            assert len(items) == len(visible_items)

    def test_sync_from_engine_after_damage(self, engine_adapter, layout_loader):
        """Test entity sync updates HP after combat damage."""
        manager = EntityManager()

        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        monsters = manager.get_monsters()
        if not monsters:
            pytest.skip("No monsters in room")

        # Get initial HP from first monster
        first_monster = monsters[0]
        initial_hp = first_monster.hp

        # Execute attack through engine
        if engine_adapter.in_combat and engine_adapter.is_player_turn():
            result = engine_adapter.execute_attack(target_index=0)

            if result["success"] and result["hit"]:
                # Sync should detect HP change
                changed = manager.sync_from_engine(engine_adapter)
                assert len(changed) > 0

                # Monster HP should be updated
                assert first_monster.hp < initial_hp

    def test_remove_dead_after_kill(self, engine_adapter, layout_loader):
        """Test dead entities are removed after being killed."""
        manager = EntityManager()

        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        initial_monster_count = len(manager.get_monsters())
        if initial_monster_count == 0:
            pytest.skip("No monsters in room")

        # Attack until a monster dies or we run out of turns
        max_attacks = 20
        attacks = 0
        killed_one = False

        while attacks < max_attacks and engine_adapter.in_combat:
            if engine_adapter.is_player_turn():
                result = engine_adapter.execute_attack(target_index=0)
                attacks += 1

                if result["success"]:
                    manager.sync_from_engine(engine_adapter)

                    if result.get("target_killed"):
                        killed_one = True
                        removed = manager.remove_dead_entities()
                        assert len(removed) > 0
                        assert len(manager.get_monsters()) < initial_monster_count
                        break

                    engine_adapter.advance_turn()
            else:
                engine_adapter.process_enemy_turn()
                engine_adapter.advance_turn()

        if not killed_one:
            pytest.skip("Could not kill monster in allowed attacks")

    def test_spread_party_creates_party_entities(
        self, engine_adapter, layout_loader
    ):
        """Test party spread creates PartyMemberEntity objects."""
        manager = EntityManager()

        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        # Spread party for combat
        positions = manager.spread_party_for_combat(
            engine=engine_adapter,
            center_x=10,
            center_y=7,
            layout=layout,
            character_textures={},
        )

        # Should have party member entities
        party_members = manager.get_party_members()
        assert len(party_members) > 0
        assert len(positions) == len(party_members)

        # Each should have creature reference
        for pm in party_members:
            assert pm.entity_type == EntityType.PARTY_MEMBER
            assert pm._creature_ref is not None
            assert pm.character_class != ""

    def test_spread_party_avoids_existing_monster_tile(
        self, engine_adapter, layout_loader
    ):
        """Regression for #576: ``spread_party_for_combat`` must skip tiles
        already held by a monster instead of overlaying party members on
        them.

        Without this guarantee, ``session.spawn_monster`` followed by the
        automatic spread-into-combat step lands the front-left fighter
        on the just-spawned monster, hiding the monster on the ASCII map
        and breaking the occupancy invariant the #574 gate was added to
        protect.
        """
        from client_2d.entities.entity import MonsterEntity

        manager = EntityManager()

        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        # Start from an empty manager (no room monsters) so we can pin a
        # single monster onto the front-left formation tile and assert
        # that the spread step routes around it.
        manager.clear()

        center_x, center_y = 10, 7
        front_left = (center_x - 1, center_y)

        blocker = MonsterEntity(
            entity_id="monster_blocker",
            grid_x=front_left[0],
            grid_y=front_left[1],
            entity_type=EntityType.MONSTER,
            sub_type="goblin",
        )
        manager._add_entity(blocker)

        positions = manager.spread_party_for_combat(
            engine=engine_adapter,
            center_x=center_x,
            center_y=center_y,
            layout=layout,
            character_textures={},
        )

        # The blocking monster's tile must not appear in the formation
        # positions, and no party member should be sitting on it.
        assert front_left not in positions, (
            f"spread_party_for_combat placed a party member onto the "
            f"monster's tile {front_left}; positions={positions}"
        )
        for pm in manager.get_party_members():
            assert (pm.grid_x, pm.grid_y) != front_left, (
                f"party member {pm.entity_id} landed on monster tile "
                f"{front_left}"
            )

        # The blocker itself must remain at its tile, untouched.
        still_there = manager.get_at_position(*front_left)
        assert still_there is blocker, (
            f"blocker monster was displaced or evicted by the spread step; "
            f"get_at_position({front_left}) -> {still_there}"
        )

    def test_collapse_party_removes_party_entities(
        self, engine_adapter, layout_loader
    ):
        """Test collapse_party removes all party member entities."""
        manager = EntityManager()

        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        # Spread party
        manager.spread_party_for_combat(
            engine=engine_adapter,
            center_x=10,
            center_y=7,
            layout=layout,
            character_textures={},
        )

        assert len(manager.get_party_members()) > 0
        monster_count = len(manager.get_monsters())

        # Collapse party
        manager.collapse_party()

        # Party members gone, monsters remain
        assert len(manager.get_party_members()) == 0
        assert len(manager.get_monsters()) == monster_count

    def test_update_party_turn_status(self, engine_adapter, layout_loader):
        """Test party turn status updates correctly."""
        manager = EntityManager()

        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        # Spread party for combat
        manager.spread_party_for_combat(
            engine=engine_adapter,
            center_x=10,
            center_y=7,
            layout=layout,
            character_textures={},
        )

        # Update turn status
        manager.update_party_turn_status(engine_adapter)

        # Check that at most one party member has is_current_turn=True
        current_turn_count = sum(
            1 for pm in manager.get_party_members() if pm.is_current_turn
        )

        # Either 0 (enemy turn) or 1 (player turn)
        assert current_turn_count <= 1

    def test_room_clear_on_transition(self, engine_adapter, layout_loader):
        """Test clear() removes all entities for room transition."""
        manager = EntityManager()

        room_data = layout_loader.get_room_data(
            "cellar", "cellar.storage", "poisoned_laboratory"
        )
        layout = layout_loader.load_room_with_fallback(
            dungeon_name="cellar",
            room_id="cellar.storage",
            campaign_id="poisoned_laboratory",
            default_width=20,
            default_height=15,
            exits={"south": "cellar.stairs"},
        )

        manager.load_from_room(
            engine=engine_adapter,
            layout=layout,
            room_data=room_data,
            monster_textures={},
            item_textures={},
        )

        assert len(manager.get_all()) > 0

        # Clear for room transition
        manager.clear()

        assert len(manager.get_all()) == 0
        assert len(manager.get_monsters()) == 0
        assert len(manager.get_items()) == 0
        assert len(manager.get_party_members()) == 0
