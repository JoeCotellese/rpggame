# ABOUTME: Unit tests for spell dataclass and helper methods
# ABOUTME: Tests spell properties, helper methods, and data validation

import pytest
from dnd_engine.core.spell import (
    Spell,
    SpellSchool,
    SpellComponents,
    SpellDamage,
    SpellHealing,
    SavingThrow,
    DurationType,
)


class TestSpellDataclass:
    """Test the Spell dataclass and its helper methods"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create a basic damage cantrip
        self.fire_bolt = Spell(
            id="fire_bolt",
            name="Fire Bolt",
            level=0,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=120,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="You hurl a mote of fire at a creature.",
            damage=SpellDamage(
                dice="1d10",
                damage_type="fire",
                higher_levels="Increases by 1d10 at 5th, 11th, and 17th level"
            ),
            attack_type="ranged",
            classes=["wizard", "sorcerer"]
        )

        # Create a healing spell
        self.cure_wounds = Spell(
            id="cure_wounds",
            name="Cure Wounds",
            level=1,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=-1,  # Touch
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.INSTANTANEOUS,
            description="A creature you touch regains hit points.",
            healing=SpellHealing(
                dice="1d8",
                higher_levels="Increases by 1d8 per slot level above 1st"
            ),
            classes=["cleric", "paladin"]
        )

        # Create a utility cantrip
        self.light = Spell(
            id="light",
            name="Light",
            level=0,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=-1,  # Touch
            components=SpellComponents(
                verbal=True,
                material=True,
                material_description="a firefly or phosphorescent moss"
            ),
            duration=DurationType.TIMED,
            duration_value="1 hour",
            description="You touch one object that sheds bright light.",
            classes=["wizard", "cleric"]
        )

        # Create an AoE spell with saving throw
        self.fireball = Spell(
            id="fireball",
            name="Fireball",
            level=3,
            school=SpellSchool.EVOCATION,
            casting_time="1 action",
            range_ft=150,
            components=SpellComponents(
                verbal=True,
                somatic=True,
                material=True,
                material_description="a tiny ball of bat guano and sulfur"
            ),
            duration=DurationType.INSTANTANEOUS,
            description="An explosion of flame erupts.",
            damage=SpellDamage(
                dice="8d6",
                damage_type="fire",
                higher_levels="Increases by 1d6 per slot level above 3rd"
            ),
            saving_throw=SavingThrow(ability="dexterity", on_success="half"),
            area_of_effect="20-foot radius sphere",
            classes=["wizard", "sorcerer"]
        )

        # Create a concentration spell
        self.mage_hand = Spell(
            id="mage_hand",
            name="Mage Hand",
            level=0,
            school=SpellSchool.CONJURATION,
            casting_time="1 action",
            range_ft=30,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.CONCENTRATION,
            duration_value="1 minute",
            concentration=True,
            description="A spectral, floating hand appears.",
            classes=["wizard"]
        )

    def test_spell_creation(self):
        """Test creating a spell with required fields"""
        assert self.fire_bolt.id == "fire_bolt"
        assert self.fire_bolt.name == "Fire Bolt"
        assert self.fire_bolt.level == 0
        assert self.fire_bolt.school == SpellSchool.EVOCATION

    def test_is_cantrip(self):
        """Test cantrip detection"""
        assert self.fire_bolt.is_cantrip() is True
        assert self.cure_wounds.is_cantrip() is False
        assert self.fireball.is_cantrip() is False

    def test_requires_attack_roll(self):
        """Test attack roll detection"""
        assert self.fire_bolt.requires_attack_roll() is True
        assert self.fireball.requires_attack_roll() is False
        assert self.cure_wounds.requires_attack_roll() is False

    def test_requires_saving_throw(self):
        """Test saving throw detection"""
        assert self.fireball.requires_saving_throw() is True
        assert self.fire_bolt.requires_saving_throw() is False

    def test_has_damage(self):
        """Test damage detection"""
        assert self.fire_bolt.has_damage() is True
        assert self.fireball.has_damage() is True
        assert self.cure_wounds.has_damage() is False
        assert self.light.has_damage() is False

    def test_has_healing(self):
        """Test healing detection"""
        assert self.cure_wounds.has_healing() is True
        assert self.fire_bolt.has_healing() is False
        assert self.fireball.has_healing() is False

    def test_is_aoe(self):
        """Test area of effect detection"""
        assert self.fireball.is_aoe() is True
        assert self.fire_bolt.is_aoe() is False
        assert self.cure_wounds.is_aoe() is False

    def test_get_range_description(self):
        """Test range description helper"""
        assert self.fire_bolt.get_range_description() == "120 feet"
        assert self.cure_wounds.get_range_description() == "Touch"

        # Test self range
        self_spell = Spell(
            id="test",
            name="Test",
            level=0,
            school=SpellSchool.ABJURATION,
            casting_time="1 action",
            range_ft=0,
            components=SpellComponents(),
            duration=DurationType.INSTANTANEOUS,
            description="Test"
        )
        assert self_spell.get_range_description() == "Self"

    def test_get_components_description(self):
        """Test components description helper"""
        assert "V" in self.fire_bolt.get_components_description()
        assert "S" in self.fire_bolt.get_components_description()
        assert "M" not in self.fire_bolt.get_components_description()

        # Test with material component
        components_desc = self.light.get_components_description()
        assert "V" in components_desc
        assert "M (a firefly or phosphorescent moss)" in components_desc

    def test_get_duration_description(self):
        """Test duration description helper"""
        assert self.fire_bolt.get_duration_description() == "Instantaneous"
        assert self.light.get_duration_description() == "1 hour"
        assert self.mage_hand.get_duration_description() == "Concentration, up to 1 minute"

    def test_spell_components_dataclass(self):
        """Test SpellComponents dataclass"""
        components = SpellComponents(
            verbal=True,
            somatic=True,
            material=True,
            material_description="a pinch of sulfur",
            material_cost=50,
            material_consumed=True
        )
        assert components.verbal is True
        assert components.somatic is True
        assert components.material is True
        assert components.material_description == "a pinch of sulfur"
        assert components.material_cost == 50
        assert components.material_consumed is True

    def test_spell_damage_dataclass(self):
        """Test SpellDamage dataclass"""
        damage = SpellDamage(
            dice="2d6",
            damage_type="fire",
            higher_levels="Increases by 1d6 per level"
        )
        assert damage.dice == "2d6"
        assert damage.damage_type == "fire"
        assert damage.higher_levels == "Increases by 1d6 per level"

    def test_spell_healing_dataclass(self):
        """Test SpellHealing dataclass"""
        healing = SpellHealing(
            dice="1d8",
            higher_levels="Increases by 1d8 per level"
        )
        assert healing.dice == "1d8"
        assert healing.higher_levels == "Increases by 1d8 per level"

    def test_saving_throw_dataclass(self):
        """Test SavingThrow dataclass"""
        save = SavingThrow(ability="dexterity", on_success="half")
        assert save.ability == "dexterity"
        assert save.on_success == "half"

    def test_spell_schools_enum(self):
        """Test all eight spell schools"""
        schools = [
            SpellSchool.ABJURATION,
            SpellSchool.CONJURATION,
            SpellSchool.DIVINATION,
            SpellSchool.ENCHANTMENT,
            SpellSchool.EVOCATION,
            SpellSchool.ILLUSION,
            SpellSchool.NECROMANCY,
            SpellSchool.TRANSMUTATION
        ]
        assert len(schools) == 8
        assert all(isinstance(school, SpellSchool) for school in schools)

    def test_spell_with_ritual(self):
        """Test spell with ritual casting"""
        detect_magic = Spell(
            id="detect_magic",
            name="Detect Magic",
            level=1,
            school=SpellSchool.DIVINATION,
            casting_time="1 action",
            range_ft=0,
            components=SpellComponents(verbal=True, somatic=True),
            duration=DurationType.CONCENTRATION,
            duration_value="10 minutes",
            concentration=True,
            ritual=True,
            description="You sense the presence of magic.",
            classes=["wizard", "cleric"]
        )
        assert detect_magic.ritual is True

    def test_spell_with_expensive_material(self):
        """Test spell with costly material component"""
        revivify = Spell(
            id="revivify",
            name="Revivify",
            level=3,
            school=SpellSchool.NECROMANCY,
            casting_time="1 action",
            range_ft=-1,
            components=SpellComponents(
                verbal=True,
                somatic=True,
                material=True,
                material_description="diamonds worth 300 gp, which the spell consumes",
                material_cost=300,
                material_consumed=True
            ),
            duration=DurationType.INSTANTANEOUS,
            description="You touch a creature that has died within the last minute.",
            classes=["cleric", "paladin"]
        )
        assert revivify.components.material_cost == 300
        assert revivify.components.material_consumed is True

    def test_spell_default_source(self):
        """Test that spells have default source attribution"""
        assert self.fire_bolt.source == "D&D 5E SRD (CC BY 4.0)"

    def test_spell_classes_list(self):
        """Test that spell classes are properly assigned"""
        assert "wizard" in self.fire_bolt.classes
        assert "sorcerer" in self.fire_bolt.classes
        assert "cleric" in self.cure_wounds.classes
        assert "paladin" in self.cure_wounds.classes
