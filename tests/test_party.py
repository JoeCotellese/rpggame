# ABOUTME: Unit tests for the Party class
# ABOUTME: Tests party membership, living members check, and character lookup

import pytest
from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.party import Party


@pytest.fixture
def test_abilities():
    """Create test abilities."""
    return Abilities(
        strength=15,
        dexterity=14,
        constitution=13,
        intelligence=10,
        wisdom=12,
        charisma=8
    )


@pytest.fixture
def fighter1(test_abilities):
    """Create first test fighter."""
    return Character(
        name="Fighter One",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=test_abilities,
        max_hp=12,
        ac=16
    )


@pytest.fixture
def fighter2(test_abilities):
    """Create second test fighter."""
    return Character(
        name="Fighter Two",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=test_abilities,
        max_hp=12,
        ac=16
    )


@pytest.fixture
def fighter3(test_abilities):
    """Create third test fighter."""
    return Character(
        name="Fighter Three",
        character_class=CharacterClass.FIGHTER,
        level=1,
        abilities=test_abilities,
        max_hp=12,
        ac=16
    )


@pytest.fixture
def empty_party():
    """Create an empty party."""
    return Party()


@pytest.fixture
def party_with_characters(fighter1, fighter2, fighter3):
    """Create a party with three characters."""
    return Party(characters=[fighter1, fighter2, fighter3])


class TestPartyInitialization:
    """Test Party initialization."""

    def test_empty_party_initialization(self):
        """Test creating an empty party."""
        party = Party()
        assert len(party.characters) == 0
        assert len(party) == 0

    def test_party_with_characters_initialization(self, fighter1, fighter2):
        """Test creating a party with characters."""
        party = Party(characters=[fighter1, fighter2])
        assert len(party.characters) == 2
        assert len(party) == 2
        assert fighter1 in party.characters
        assert fighter2 in party.characters


class TestAddCharacter:
    """Test adding characters to the party."""

    def test_add_character_to_empty_party(self, empty_party, fighter1):
        """Test adding a character to an empty party."""
        empty_party.add_character(fighter1)
        assert len(empty_party.characters) == 1
        assert fighter1 in empty_party.characters

    def test_add_multiple_characters(self, empty_party, fighter1, fighter2, fighter3):
        """Test adding multiple characters."""
        empty_party.add_character(fighter1)
        empty_party.add_character(fighter2)
        empty_party.add_character(fighter3)
        assert len(empty_party.characters) == 3
        assert all(char in empty_party.characters for char in [fighter1, fighter2, fighter3])

    def test_add_duplicate_character(self, empty_party, fighter1):
        """Test that adding the same character twice doesn't duplicate."""
        empty_party.add_character(fighter1)
        empty_party.add_character(fighter1)
        assert len(empty_party.characters) == 1


class TestRemoveCharacter:
    """Test removing characters from the party."""

    def test_remove_character(self, party_with_characters, fighter1):
        """Test removing a character from the party."""
        party_with_characters.remove_character(fighter1)
        assert len(party_with_characters.characters) == 2
        assert fighter1 not in party_with_characters.characters

    def test_remove_nonexistent_character(self, party_with_characters, test_abilities):
        """Test removing a character that's not in the party."""
        new_fighter = Character(
            name="Not In Party",
            character_class=CharacterClass.FIGHTER,
            level=1,
            abilities=test_abilities,
            max_hp=12,
            ac=16
        )
        initial_count = len(party_with_characters.characters)
        party_with_characters.remove_character(new_fighter)
        assert len(party_with_characters.characters) == initial_count

    def test_remove_all_characters(self, party_with_characters, fighter1, fighter2, fighter3):
        """Test removing all characters from the party."""
        party_with_characters.remove_character(fighter1)
        party_with_characters.remove_character(fighter2)
        party_with_characters.remove_character(fighter3)
        assert len(party_with_characters.characters) == 0


class TestGetLivingMembers:
    """Test getting living party members."""

    def test_all_alive(self, party_with_characters):
        """Test getting living members when all are alive."""
        living = party_with_characters.get_living_members()
        assert len(living) == 3

    def test_some_dead(self, party_with_characters, fighter1, fighter2):
        """Test getting living members when some are dead."""
        fighter1.take_damage(fighter1.max_hp)  # Kill fighter1
        living = party_with_characters.get_living_members()
        assert len(living) == 2
        assert fighter1 not in living
        assert fighter2 in living

    def test_all_dead(self, party_with_characters, fighter1, fighter2, fighter3):
        """Test getting living members when all are dead."""
        fighter1.take_damage(fighter1.max_hp)
        fighter2.take_damage(fighter2.max_hp)
        fighter3.take_damage(fighter3.max_hp)
        living = party_with_characters.get_living_members()
        assert len(living) == 0

    def test_empty_party_living_members(self, empty_party):
        """Test getting living members from an empty party."""
        living = empty_party.get_living_members()
        assert len(living) == 0


class TestIsWiped:
    """Test checking if the party is wiped out."""

    def test_party_not_wiped_all_alive(self, party_with_characters):
        """Test is_wiped when all members are alive."""
        assert not party_with_characters.is_wiped()

    def test_party_not_wiped_some_alive(self, party_with_characters, fighter1):
        """Test is_wiped when some members are alive."""
        fighter1.take_damage(fighter1.max_hp)  # Kill fighter1
        assert not party_with_characters.is_wiped()

    def test_party_wiped_all_dead(self, party_with_characters, fighter1, fighter2, fighter3):
        """Test is_wiped when all members are dead."""
        fighter1.take_damage(fighter1.max_hp)
        fighter2.take_damage(fighter2.max_hp)
        fighter3.take_damage(fighter3.max_hp)
        assert party_with_characters.is_wiped()

    def test_empty_party_is_wiped(self, empty_party):
        """Test is_wiped for an empty party."""
        assert empty_party.is_wiped()


class TestGetCharacterByName:
    """Test finding characters by name."""

    def test_find_existing_character(self, party_with_characters, fighter1):
        """Test finding a character that exists in the party."""
        found = party_with_characters.get_character_by_name("Fighter One")
        assert found == fighter1

    def test_find_character_case_insensitive(self, party_with_characters, fighter2):
        """Test finding a character with different case."""
        found = party_with_characters.get_character_by_name("FIGHTER TWO")
        assert found == fighter2

    def test_find_nonexistent_character(self, party_with_characters):
        """Test finding a character that doesn't exist."""
        found = party_with_characters.get_character_by_name("Not Exists")
        assert found is None

    def test_find_in_empty_party(self, empty_party):
        """Test finding a character in an empty party."""
        found = empty_party.get_character_by_name("Fighter One")
        assert found is None


class TestPartyStringRepresentation:
    """Test party string representation."""

    def test_empty_party_str(self, empty_party):
        """Test string representation of empty party."""
        assert "empty" in str(empty_party).lower()

    def test_party_with_characters_str(self, party_with_characters):
        """Test string representation of party with characters."""
        party_str = str(party_with_characters)
        assert "3 members" in party_str
        assert "Fighter One" in party_str
        assert "Fighter Two" in party_str
        assert "Fighter Three" in party_str

    def test_party_str_shows_hp(self, party_with_characters, fighter1):
        """Test that string representation shows HP."""
        party_str = str(party_with_characters)
        assert "12/12" in party_str  # HP format

    def test_party_str_with_damaged_member(self, party_with_characters, fighter1):
        """Test string representation with a damaged member."""
        fighter1.take_damage(5)
        party_str = str(party_with_characters)
        assert "7/12" in party_str  # Damaged HP format
