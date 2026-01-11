# ABOUTME: Unit tests for Entity classes and sync logic.
# ABOUTME: Tests Entity, MonsterEntity, PartyMemberEntity with creature references.

"""Unit tests for the entity module."""


from client_2d.entities import (
    Entity,
    EntityManager,
    EntityType,
    ItemEntity,
    MonsterEntity,
    PartyMemberEntity,
    VisualState,
)


class MockCreature:
    """Mock creature for testing entity sync without engine dependency."""

    def __init__(
        self,
        name: str = "Test Creature",
        current_hp: int = 10,
        max_hp: int = 10,
        is_alive: bool = True,
        active_conditions: dict | None = None,
    ):
        self.name = name
        self.current_hp = current_hp
        self.max_hp = max_hp
        self._is_alive = is_alive
        self.active_conditions = active_conditions or {}

    @property
    def is_alive(self) -> bool:
        """Return alive status based on HP or override."""
        if self._is_alive is not None:
            return self._is_alive and self.current_hp > 0
        return self.current_hp > 0


class TestVisualState:
    """Tests for VisualState dataclass."""

    def test_default_values(self):
        """Test VisualState has sensible defaults."""
        vs = VisualState()

        assert vs.offset_x == 0.0
        assert vs.offset_y == 0.0
        assert vs.alpha == 255
        assert vs.scale == 1.0
        assert vs.tint == (255, 255, 255)
        assert vs.is_animating is False

    def test_custom_values(self):
        """Test VisualState can be customized."""
        vs = VisualState(
            offset_x=5.0,
            offset_y=-3.0,
            alpha=128,
            scale=1.5,
            tint=(255, 0, 0),
            is_animating=True,
        )

        assert vs.offset_x == 5.0
        assert vs.offset_y == -3.0
        assert vs.alpha == 128
        assert vs.scale == 1.5
        assert vs.tint == (255, 0, 0)
        assert vs.is_animating is True


class TestEntity:
    """Tests for base Entity class."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        entity = Entity(
            entity_id="test_1",
            grid_x=5,
            grid_y=10,
            entity_type=EntityType.MONSTER,
            sub_type="goblin",
        )

        assert entity.entity_id == "test_1"
        assert entity.grid_x == 5
        assert entity.grid_y == 10
        assert entity.entity_type == EntityType.MONSTER
        assert entity.sub_type == "goblin"
        assert entity.is_alive is True
        assert entity.hp == 0
        assert entity.max_hp == 0

    def test_entity_default_visual_state(self):
        """Test entity has default visual state."""
        entity = Entity(
            entity_id="test",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.ITEM,
        )

        assert isinstance(entity.visual, VisualState)
        assert entity.visual.alpha == 255

    def test_entity_without_creature_ref(self):
        """Test sync_from_creature returns False without creature ref."""
        entity = Entity(
            entity_id="test",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.MONSTER,
        )

        changed = entity.sync_from_creature()
        assert changed is False

    def test_entity_sync_from_creature(self):
        """Test entity syncs state from creature reference."""
        creature = MockCreature(
            name="Goblin",
            current_hp=7,
            max_hp=12,
            active_conditions={"poisoned": {}},
        )

        entity = Entity(
            entity_id="goblin_1",
            grid_x=5,
            grid_y=5,
            entity_type=EntityType.MONSTER,
        )

        # Set creature reference
        entity.creature = creature

        # State should be synced immediately
        assert entity.hp == 7
        assert entity.max_hp == 12
        assert entity.is_alive is True
        assert "poisoned" in entity.conditions

    def test_entity_sync_detects_changes(self):
        """Test sync_from_creature returns True when state changes."""
        creature = MockCreature(current_hp=10, max_hp=10)

        entity = Entity(
            entity_id="test",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.MONSTER,
        )
        entity.creature = creature

        # Initial sync happened in setter
        changed = entity.sync_from_creature()
        assert changed is False  # No change since setter synced

        # Modify creature
        creature.current_hp = 5
        changed = entity.sync_from_creature()
        assert changed is True
        assert entity.hp == 5

        # Sync again with no changes
        changed = entity.sync_from_creature()
        assert changed is False

    def test_entity_sync_tracks_death(self):
        """Test entity tracks creature death."""
        creature = MockCreature(current_hp=5, max_hp=10)

        entity = Entity(
            entity_id="dying",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.MONSTER,
        )
        entity.creature = creature

        assert entity.is_alive is True

        # Kill creature
        creature.current_hp = 0
        changed = entity.sync_from_creature()

        assert changed is True
        assert entity.is_alive is False
        assert entity.hp == 0

    def test_entity_sync_tracks_conditions(self):
        """Test entity tracks condition changes."""
        creature = MockCreature(current_hp=10, max_hp=10)

        entity = Entity(
            entity_id="test",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.MONSTER,
        )
        entity.creature = creature

        assert len(entity.conditions) == 0

        # Add condition
        creature.active_conditions["stunned"] = {}
        changed = entity.sync_from_creature()

        assert changed is True
        assert "stunned" in entity.conditions

        # Remove condition
        del creature.active_conditions["stunned"]
        changed = entity.sync_from_creature()

        assert changed is True
        assert "stunned" not in entity.conditions


class TestMonsterEntity:
    """Tests for MonsterEntity class."""

    def test_monster_entity_type(self):
        """Test MonsterEntity has correct type after __post_init__."""
        monster = MonsterEntity(
            entity_id="goblin_1",
            grid_x=10,
            grid_y=5,
            entity_type=EntityType.ITEM,  # Wrong type, should be corrected
            enemy_index=0,
        )

        assert monster.entity_type == EntityType.MONSTER
        assert monster.enemy_index == 0

    def test_monster_entity_defaults(self):
        """Test MonsterEntity default values."""
        monster = MonsterEntity(
            entity_id="test",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.MONSTER,
        )

        assert monster.enemy_index == -1


class TestPartyMemberEntity:
    """Tests for PartyMemberEntity class."""

    def test_party_member_entity_type(self):
        """Test PartyMemberEntity has correct type after __post_init__."""
        party_member = PartyMemberEntity(
            entity_id="fighter_1",
            grid_x=5,
            grid_y=5,
            entity_type=EntityType.ITEM,  # Wrong type, should be corrected
            party_index=0,
            character_class="fighter",
        )

        assert party_member.entity_type == EntityType.PARTY_MEMBER
        assert party_member.party_index == 0
        assert party_member.character_class == "fighter"

    def test_party_member_turn_tracking(self):
        """Test PartyMemberEntity tracks turn status."""
        party_member = PartyMemberEntity(
            entity_id="wizard_1",
            grid_x=5,
            grid_y=5,
            entity_type=EntityType.PARTY_MEMBER,
            is_current_turn=True,
        )

        assert party_member.is_current_turn is True


class TestItemEntity:
    """Tests for ItemEntity class."""

    def test_item_entity_type(self):
        """Test ItemEntity has correct type after __post_init__."""
        item = ItemEntity(
            entity_id="potion_1",
            grid_x=3,
            grid_y=3,
            entity_type=EntityType.MONSTER,  # Wrong type, should be corrected
            item_category="potions",
        )

        assert item.entity_type == EntityType.ITEM
        assert item.item_category == "potions"
        assert item.collected is False

    def test_item_collection_tracking(self):
        """Test ItemEntity tracks collection status."""
        item = ItemEntity(
            entity_id="sword_1",
            grid_x=0,
            grid_y=0,
            entity_type=EntityType.ITEM,
            collected=True,
        )

        assert item.collected is True


class TestEntityManager:
    """Tests for EntityManager class."""

    def test_entity_manager_init_empty(self):
        """Test EntityManager initializes empty."""
        manager = EntityManager()

        assert len(manager.get_all()) == 0
        assert len(manager.get_monsters()) == 0
        assert len(manager.get_party_members()) == 0
        assert len(manager.get_items()) == 0

    def test_entity_manager_clear(self):
        """Test EntityManager clear removes all entities."""
        manager = EntityManager()

        # Add some entities manually
        monster = MonsterEntity(
            entity_id="test_monster",
            grid_x=5,
            grid_y=5,
            entity_type=EntityType.MONSTER,
        )
        manager._add_entity(monster)

        assert len(manager.get_all()) == 1

        manager.clear()

        assert len(manager.get_all()) == 0

    def test_entity_manager_get_at_position(self):
        """Test EntityManager can find entity by position."""
        manager = EntityManager()

        monster = MonsterEntity(
            entity_id="goblin_1",
            grid_x=10,
            grid_y=15,
            entity_type=EntityType.MONSTER,
        )
        manager._add_entity(monster)

        found = manager.get_at_position(10, 15)
        assert found is monster

        not_found = manager.get_at_position(0, 0)
        assert not_found is None

    def test_entity_manager_get_by_id(self):
        """Test EntityManager can find entity by ID."""
        manager = EntityManager()

        item = ItemEntity(
            entity_id="sword_of_doom",
            grid_x=3,
            grid_y=3,
            entity_type=EntityType.ITEM,
        )
        manager._add_entity(item)

        found = manager.get_by_id("sword_of_doom")
        assert found is item

        not_found = manager.get_by_id("nonexistent")
        assert not_found is None

    def test_entity_manager_remove_dead_entities(self):
        """Test EntityManager removes dead monster entities."""
        manager = EntityManager()

        # Create a living monster
        living_creature = MockCreature(current_hp=10, max_hp=10)
        living_monster = MonsterEntity(
            entity_id="living",
            grid_x=5,
            grid_y=5,
            entity_type=EntityType.MONSTER,
        )
        living_monster.creature = living_creature
        manager._add_entity(living_monster)

        # Create a dead monster
        dead_creature = MockCreature(current_hp=0, max_hp=10)
        dead_monster = MonsterEntity(
            entity_id="dead",
            grid_x=10,
            grid_y=10,
            entity_type=EntityType.MONSTER,
        )
        dead_monster.creature = dead_creature
        manager._add_entity(dead_monster)

        assert len(manager.get_monsters()) == 2

        # Remove dead entities
        removed = manager.remove_dead_entities()

        assert len(removed) == 1
        assert removed[0] is dead_monster
        assert len(manager.get_monsters()) == 1
        assert manager.get_by_id("living") is living_monster
        assert manager.get_by_id("dead") is None

    def test_entity_manager_sync_from_engine(self):
        """Test EntityManager syncs all entities and returns changed ones."""
        manager = EntityManager()

        # Create monsters with creature refs
        creature1 = MockCreature(current_hp=10, max_hp=10)
        monster1 = MonsterEntity(
            entity_id="m1",
            grid_x=5,
            grid_y=5,
            entity_type=EntityType.MONSTER,
        )
        monster1.creature = creature1
        manager._add_entity(monster1)

        creature2 = MockCreature(current_hp=8, max_hp=8)
        monster2 = MonsterEntity(
            entity_id="m2",
            grid_x=10,
            grid_y=10,
            entity_type=EntityType.MONSTER,
        )
        monster2.creature = creature2
        manager._add_entity(monster2)

        # No changes initially
        changed = manager.sync_from_engine(None)
        assert len(changed) == 0

        # Modify one creature
        creature1.current_hp = 5

        changed = manager.sync_from_engine(None)
        assert len(changed) == 1
        assert changed[0] is monster1
        assert monster1.hp == 5

    def test_entity_manager_collapse_party(self):
        """Test EntityManager removes party member entities."""
        manager = EntityManager()

        # Add party members
        for i in range(4):
            party_member = PartyMemberEntity(
                entity_id=f"party_{i}",
                grid_x=i,
                grid_y=i,
                entity_type=EntityType.PARTY_MEMBER,
                party_index=i,
            )
            manager._add_entity(party_member)

        # Add a monster (should not be removed)
        monster = MonsterEntity(
            entity_id="monster_1",
            grid_x=10,
            grid_y=10,
            entity_type=EntityType.MONSTER,
        )
        manager._add_entity(monster)

        assert len(manager.get_party_members()) == 4
        assert len(manager.get_monsters()) == 1

        manager.collapse_party()

        assert len(manager.get_party_members()) == 0
        assert len(manager.get_monsters()) == 1  # Monster still there
