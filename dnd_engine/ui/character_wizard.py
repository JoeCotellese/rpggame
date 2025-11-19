# ABOUTME: Character creation wizard for interactive character building
# ABOUTME: Supports custom, template-based, and random character generation with navigation

from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.creature import Abilities
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.systems.inventory import EquipmentSlot
from dnd_engine.ui.rich_ui import (
    console,
    print_banner,
    print_section,
    print_choice_menu,
    print_message,
    print_status_message,
    print_input_prompt,
    print_error
)
from rich.table import Table
from rich import box


class CreationPath(Enum):
    """Character creation path options"""
    CUSTOM = "custom"
    TEMPLATE = "template"
    RANDOM = "random"


class CharacterCreationWizard:
    """
    Multi-step wizard for creating D&D characters.

    Supports three creation paths:
    1. Custom - Step-by-step with full control (enhanced with Back/Review)
    2. Template - Quick-build from predefined archetypes
    3. Random - Fully randomized character generation

    All paths end with a comprehensive summary/confirmation screen.
    """

    def __init__(
        self,
        character_factory: Optional[CharacterFactory] = None,
        data_loader: Optional[DataLoader] = None,
        dice_roller: Optional[DiceRoller] = None
    ):
        """
        Initialize the character creation wizard.

        Args:
            character_factory: CharacterFactory instance for utilities
            data_loader: DataLoader for accessing game data
            dice_roller: DiceRoller instance (creates new if not provided)
        """
        self.factory = character_factory or CharacterFactory()
        self.data_loader = data_loader or DataLoader()
        self.dice_roller = dice_roller or DiceRoller()

        # Load game data
        self.races_data = self.data_loader.load_races()
        self.classes_data = self.data_loader.load_classes()
        self.items_data = self.data_loader.load_items()
        self.skills_data = self.data_loader.load_skills()
        self.spells_data = self.data_loader.load_spells()
        self.templates_data = self._load_templates()

        # Wizard state
        self.creation_path: Optional[CreationPath] = None
        self.name: Optional[str] = None
        self.race: Optional[str] = None
        self.character_class: Optional[str] = None
        self.abilities: Optional[Dict[str, int]] = None
        self.rolled_scores: Optional[List[int]] = None
        self.skill_proficiencies: List[str] = []
        self.expertise_skills: List[str] = []
        self.selected_spells: List[str] = []
        self.level: int = 1

    def _load_templates(self) -> Dict[str, Any]:
        """Load character templates from JSON."""
        try:
            import json
            from pathlib import Path

            templates_path = self.data_loader.data_path / "srd" / "character_templates.json"
            with open(templates_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print_error(f"Warning: Could not load character templates: {e}")
            return {}

    def run(self) -> Optional[Character]:
        """
        Run the character creation wizard.

        Returns:
            Created Character object, or None if cancelled
        """
        console.clear()
        print_banner("Character Creation", color="cyan")
        console.print()

        # Step 1: Choose creation path
        if not self._step_choose_path():
            return None

        # Branch based on chosen path
        if self.creation_path == CreationPath.CUSTOM:
            character = self._run_custom_path()
        elif self.creation_path == CreationPath.TEMPLATE:
            character = self._run_template_path()
        elif self.creation_path == CreationPath.RANDOM:
            character = self._run_random_path()
        else:
            return None

        return character

    def _step_choose_path(self) -> bool:
        """
        Step 1: Choose creation path.

        Returns:
            True to continue, False to cancel
        """
        print_section("Choose Creation Method")
        console.print()

        options = [
            {
                "number": "1",
                "text": "Custom Character (step-by-step)"
            },
            {
                "number": "2",
                "text": "Quick Build Template"
            },
            {
                "number": "3",
                "text": "Random Character"
            },
            {
                "number": "B",
                "text": "Back/Cancel"
            }
        ]

        print_choice_menu("Creation Options", options)
        console.print()

        while True:
            choice = console.input("[bold cyan]Choose [1-3] or [B]:[/bold cyan] ").strip().lower()

            if choice == "1":
                self.creation_path = CreationPath.CUSTOM
                return True
            elif choice == "2":
                self.creation_path = CreationPath.TEMPLATE
                return True
            elif choice == "3":
                self.creation_path = CreationPath.RANDOM
                return True
            elif choice == "b":
                return False
            else:
                print_error("Invalid choice. Please enter 1, 2, 3, or B.")

    def _run_custom_path(self) -> Optional[Character]:
        """
        Run the custom character creation path with Back/Review navigation.

        Returns:
            Created Character or None if cancelled
        """
        # Custom path steps
        steps = [
            ("Name", self._custom_step_name),
            ("Race", self._custom_step_race),
            ("Class", self._custom_step_class),
            ("Abilities", self._custom_step_abilities),
            ("Skills", self._custom_step_skills),
        ]

        current_step = 0

        while current_step < len(steps):
            console.print()
            step_name, step_func = steps[current_step]
            print_section(f"Step {current_step + 1}/{len(steps)}: {step_name}")
            console.print()

            result = step_func()

            if result == "next":
                current_step += 1
            elif result == "back":
                if current_step > 0:
                    current_step -= 1
                else:
                    print_status_message("Already at first step", "warning")
            elif result == "cancel":
                return None
            elif result == "review":
                self._show_progress_summary()

        # Show final summary and confirm
        return self._finalize_character()

    def _custom_step_name(self) -> str:
        """Custom path: Get character name."""
        while True:
            name = console.input("[bold cyan]Character Name:[/bold cyan] ").strip()

            if not name:
                print_error("Name cannot be empty")
                continue

            self.name = name
            print_status_message(f"✓ Name: {self.name}", "success")

            return self._get_navigation_choice(allow_back=False)

    def _custom_step_race(self) -> str:
        """Custom path: Choose race."""
        race_list = list(self.races_data.keys())

        options = []
        for i, race_id in enumerate(race_list, 1):
            race = self.races_data[race_id]
            bonuses = ", ".join([f"+{v} {k.upper()[:3]}" for k, v in race["ability_bonuses"].items()])
            options.append({"number": str(i), "text": f"{race['name']} ({bonuses})"})

        print_choice_menu("Choose Your Race", options)
        console.print()

        while True:
            choice = console.input(f"[bold cyan]Enter number [1-{len(race_list)}]:[/bold cyan] ").strip()

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(race_list):
                    self.race = race_list[idx]
                    race_data = self.races_data[self.race]
                    print_status_message(f"✓ Race: {race_data['name']}", "success")

                    return self._get_navigation_choice()
                else:
                    print_error(f"Please enter a number between 1 and {len(race_list)}")
            except ValueError:
                print_error("Please enter a valid number")

    def _custom_step_class(self) -> str:
        """Custom path: Choose class."""
        class_list = list(self.classes_data.keys())

        options = []
        for i, class_id in enumerate(class_list, 1):
            cls = self.classes_data[class_id]
            options.append({"number": str(i), "text": f"{cls['name']} ({cls['description']})"})

        print_choice_menu("Choose Your Class", options)
        console.print()

        while True:
            choice = console.input(f"[bold cyan]Enter number [1-{len(class_list)}]:[/bold cyan] ").strip()

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(class_list):
                    self.character_class = class_list[idx]
                    class_data = self.classes_data[self.character_class]
                    print_status_message(f"✓ Class: {class_data['name']}", "success")

                    return self._get_navigation_choice()
                else:
                    print_error(f"Please enter a number between 1 and {len(class_list)}")
            except ValueError:
                print_error("Please enter a valid number")

    def _custom_step_abilities(self) -> str:
        """Custom path: Roll and assign abilities."""
        # Roll abilities
        print_message("[bold]Rolling ability scores (4d6 drop lowest)...[/bold]")
        console.print()

        all_rolls = self.factory.roll_all_abilities(self.dice_roller)
        scores = []
        roll_display = []

        for i, (score, dice) in enumerate(all_rolls, 1):
            dropped = min(dice)
            roll_display.append(f"Roll {i}: {sorted(dice, reverse=True)} = {score} (dropped {dropped})")
            scores.append(score)

        print_message("\n".join(roll_display))
        console.print()
        print_status_message(f"Your rolled scores: {sorted(scores, reverse=True)}", "info")
        console.print()

        self.rolled_scores = scores

        # Auto-assign based on class priorities
        class_data = self.classes_data[self.character_class]
        self.abilities = self.factory.auto_assign_abilities(scores, class_data)

        print_message(f"[bold]Auto-assigned for {class_data['name']}:[/bold]")
        self._display_abilities(self.abilities)
        console.print()

        # Allow swaps
        while True:
            swap_choice = console.input("[bold cyan]Swap abilities? [y/N]:[/bold cyan] ").strip().lower()

            if swap_choice in ["n", "no", ""]:
                break
            elif swap_choice in ["y", "yes"]:
                if self._swap_abilities_interactive():
                    console.print()
                    print_message("[bold]Updated abilities:[/bold]")
                    self._display_abilities(self.abilities)
                    console.print()
            else:
                print_error("Please enter 'y' or 'n'")

        # Apply racial bonuses
        abilities_before = self.abilities.copy()
        self.abilities = self.factory.apply_racial_bonuses(self.abilities, self.races_data[self.race])

        console.print()
        print_message(f"[bold]After {self.races_data[self.race]['name']} racial bonuses:[/bold]")
        self._display_abilities(self.abilities, before=abilities_before)

        return self._get_navigation_choice()

    def _custom_step_skills(self) -> str:
        """Custom path: Select skill proficiencies."""
        class_data = self.classes_data[self.character_class]

        # Select skill proficiencies
        self.skill_proficiencies = self.factory.select_skill_proficiencies(
            class_data,
            self.skills_data
        )

        # If Rogue, select expertise
        if self.character_class == "rogue":
            console.print()
            self.expertise_skills = self.factory.select_expertise_skills(
                self.skill_proficiencies,
                self.skills_data
            )

        return self._get_navigation_choice()

    def _swap_abilities_interactive(self) -> bool:
        """
        Interactive ability swap.

        Returns:
            True if swap was made, False if cancelled
        """
        ability1 = console.input("[bold cyan]First ability (STR/DEX/CON/INT/WIS/CHA):[/bold cyan] ").strip().lower()
        ability2 = console.input("[bold cyan]Second ability (STR/DEX/CON/INT/WIS/CHA):[/bold cyan] ").strip().lower()

        # Map short forms to full names
        ability_map = {
            "str": "strength", "dex": "dexterity", "con": "constitution",
            "int": "intelligence", "wis": "wisdom", "cha": "charisma"
        }

        ability1_full = ability_map.get(ability1, ability1)
        ability2_full = ability_map.get(ability2, ability2)

        try:
            self.abilities = self.factory.swap_abilities(self.abilities, ability1_full, ability2_full)
            print_status_message(
                f"Swapped {ability1_full.upper()} <-> {ability2_full.upper()}",
                "success"
            )
            return True
        except ValueError as e:
            print_error(str(e))
            return False

    def _display_abilities(self, abilities: Dict[str, int], before: Optional[Dict[str, int]] = None) -> None:
        """Display ability scores in a formatted way."""
        ability_display = []

        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = abilities[ability]
            modifier = self.factory.calculate_ability_modifier(score)
            sign = "+" if modifier >= 0 else ""

            if before:
                original = before[ability]
                bonus = score - original
                if bonus > 0:
                    ability_display.append(
                        f"{ability.upper()[:3]}: {original} + {bonus} = {score} ({sign}{modifier})"
                    )
                else:
                    ability_display.append(f"{ability.upper()[:3]}: {score} ({sign}{modifier})")
            else:
                ability_display.append(f"{ability.upper()[:3]}: {score} ({sign}{modifier})")

        print_message("\n".join(ability_display))

    def _get_navigation_choice(self, allow_back: bool = True) -> str:
        """
        Get navigation choice from user.

        Args:
            allow_back: Whether to allow Back option

        Returns:
            "next", "back", "review", or "cancel"
        """
        console.print()

        options_text = "[N]ext"
        if allow_back:
            options_text += ", [B]ack"
        options_text += ", [R]eview, [C]ancel"

        while True:
            choice = console.input(f"[bold cyan]{options_text}:[/bold cyan] ").strip().lower()

            if choice in ["n", "next", ""]:
                return "next"
            elif choice in ["b", "back"] and allow_back:
                return "back"
            elif choice in ["r", "review"]:
                return "review"
            elif choice in ["c", "cancel"]:
                confirm = console.input("[bold]Cancel character creation? [y/N]:[/bold] ").strip().lower()
                if confirm in ["y", "yes"]:
                    return "cancel"
            else:
                valid_options = ["N", "R", "C"]
                if allow_back:
                    valid_options.insert(1, "B")
                print_error(f"Invalid choice. Please enter {', '.join(valid_options)}")

    def _show_progress_summary(self) -> None:
        """Show current progress summary."""
        console.print()
        print_section("Current Progress")
        console.print()

        if self.name:
            console.print(f"[bold]Name:[/bold] {self.name}")
        if self.race:
            console.print(f"[bold]Race:[/bold] {self.races_data[self.race]['name']}")
        if self.character_class:
            console.print(f"[bold]Class:[/bold] {self.classes_data[self.character_class]['name']}")
        if self.abilities:
            console.print()
            console.print("[bold]Abilities:[/bold]")
            self._display_abilities(self.abilities)
        if self.skill_proficiencies:
            console.print()
            skills = [self.skills_data[s].get("name", s.title()) for s in self.skill_proficiencies]
            console.print(f"[bold]Skills:[/bold] {', '.join(skills)}")

        console.print()
        console.input("[dim]Press Enter to continue...[/dim]")

    def _run_template_path(self) -> Optional[Character]:
        """
        Run the template-based character creation path.

        Returns:
            Created Character or None if cancelled
        """
        console.print()
        print_section("Quick Build Templates")
        console.print()

        if not self.templates_data:
            print_error("No templates available")
            return None

        template_list = list(self.templates_data.keys())

        # Display templates
        for i, template_id in enumerate(template_list, 1):
            template = self.templates_data[template_id]
            console.print(f"[bold][{i}] {template['name']}[/bold]")
            console.print(f"    {template['description']}")

            # Show ability preview
            abilities = template['abilities']
            ability_str = ", ".join([f"{k.upper()[:3]} {v}" for k, v in abilities.items()])
            console.print(f"    [dim]Abilities: {ability_str}[/dim]")
            console.print()

        console.print(f"[B] Back/Cancel")
        console.print()

        while True:
            choice = console.input(f"[bold cyan]Select template [1-{len(template_list)}] or [B]:[/bold cyan] ").strip().lower()

            if choice == "b":
                return None

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(template_list):
                    template_id = template_list[idx]
                    return self._create_from_template(template_id)
                else:
                    print_error(f"Please enter a number between 1 and {len(template_list)}")
            except ValueError:
                print_error("Please enter a valid number")

    def _create_from_template(self, template_id: str) -> Optional[Character]:
        """
        Create character from template.

        Args:
            template_id: ID of template to use

        Returns:
            Created Character or None if cancelled
        """
        template = self.templates_data[template_id]

        console.print()
        print_status_message(f"Creating {template['name']}...", "info")
        console.print()

        # Set wizard state from template
        self.race = template['race']
        self.character_class = template['class']
        self.abilities = template['abilities'].copy()

        # Apply racial bonuses
        self.abilities = self.factory.apply_racial_bonuses(
            self.abilities,
            self.races_data[self.race]
        )

        # Get character name
        console.print(f"[bold]Template:[/bold] {template['name']}")
        console.print(f"[bold]Race:[/bold] {self.races_data[self.race]['name']}")
        console.print(f"[bold]Class:[/bold] {self.classes_data[self.character_class]['name']}")
        console.print()

        self.name = console.input("[bold cyan]Character Name:[/bold cyan] ").strip()
        while not self.name:
            print_error("Name cannot be empty")
            self.name = console.input("[bold cyan]Character Name:[/bold cyan] ").strip()

        # Auto-select skills from template
        self.skill_proficiencies = template.get('skill_choices', [])
        self.expertise_skills = template.get('expertise_choices', [])

        # Handle spells for spellcasters
        if 'spell_preferences' in template:
            spell_prefs = template['spell_preferences']
            self.selected_spells = spell_prefs.get('cantrips', []) + spell_prefs.get('level_1', [])

        # Show final summary and confirm
        return self._finalize_character()

    def _run_random_path(self) -> Optional[Character]:
        """
        Run the random character generation path.

        Returns:
            Created Character or None if cancelled
        """
        console.print()
        print_section("Random Character Generator")
        console.print()

        while True:
            # Generate random character
            self._generate_random_character()

            # Show preview
            self._show_random_preview()
            console.print()

            choice = console.input("[bold cyan][A]ccept, [R]egenerate, or [C]ancel:[/bold cyan] ").strip().lower()

            if choice in ["a", "accept"]:
                # Get name
                console.print()
                self.name = console.input("[bold cyan]Character Name (or Enter for random):[/bold cyan] ").strip()
                if not self.name:
                    self.name = self._generate_random_name()
                    print_status_message(f"Random name: {self.name}", "info")

                return self._finalize_character()
            elif choice in ["r", "regenerate"]:
                console.print()
                continue
            elif choice in ["c", "cancel"]:
                return None
            else:
                print_error("Please enter A, R, or C")

    def _generate_random_character(self) -> None:
        """Generate a random character with standard array."""
        # Use dice roller's random instance for determinism
        rng = self.dice_roller.random

        # Random race
        race_list = list(self.races_data.keys())
        self.race = rng.choice(race_list)

        # Random class
        class_list = list(self.classes_data.keys())
        self.character_class = rng.choice(class_list)

        # Standard array randomly assigned
        standard_array = [15, 14, 13, 12, 10, 8]
        rng.shuffle(standard_array)

        ability_names = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        self.abilities = dict(zip(ability_names, standard_array))

        # Apply racial bonuses
        self.abilities = self.factory.apply_racial_bonuses(
            self.abilities,
            self.races_data[self.race]
        )

        # Random skills
        class_data = self.classes_data[self.character_class]
        skill_profs = class_data.get("skill_proficiencies", {})
        num_skills = skill_profs.get("choose", 0)
        available_skills = skill_profs.get("from", [])

        if num_skills > 0 and available_skills:
            self.skill_proficiencies = rng.sample(available_skills, min(num_skills, len(available_skills)))
        else:
            self.skill_proficiencies = []

        # Random expertise for Rogue
        self.expertise_skills = []
        if self.character_class == "rogue" and len(self.skill_proficiencies) >= 2:
            self.expertise_skills = rng.sample(self.skill_proficiencies, 2)

    def _show_random_preview(self) -> None:
        """Show preview of randomly generated character."""
        console.print(f"[bold]Race:[/bold] {self.races_data[self.race]['name']}")
        console.print(f"[bold]Class:[/bold] {self.classes_data[self.character_class]['name']}")
        console.print()
        console.print("[bold]Abilities:[/bold]")
        self._display_abilities(self.abilities)

        if self.skill_proficiencies:
            console.print()
            skills = [self.skills_data[s].get("name", s.title()) for s in self.skill_proficiencies]
            console.print(f"[bold]Skills:[/bold] {', '.join(skills)}")

    def _generate_random_name(self) -> str:
        """Generate a random character name."""
        # Simple random name generator using dice roller's random for determinism
        rng = self.dice_roller.random

        first_names = [
            "Thorin", "Aria", "Kael", "Luna", "Draven", "Elara",
            "Finn", "Nyx", "Rowan", "Zara", "Ash", "Nova"
        ]
        last_names = [
            "Ironforge", "Stormwind", "Brightblade", "Shadowmoon", "Fireborn",
            "Frostbeard", "Swiftarrow", "Goldleaf", "Stonefist", "Ravenwood"
        ]

        return f"{rng.choice(first_names)} {rng.choice(last_names)}"

    def _finalize_character(self) -> Optional[Character]:
        """
        Show final summary and create character.

        Returns:
            Created Character or None if user cancels
        """
        console.print()
        print_section("Character Summary")
        console.print()

        # Build comprehensive summary
        self._show_character_summary()

        console.print()
        choice = console.input("[bold cyan][C]onfirm, [E]dit Name, [S]tart Over, [X]Cancel:[/bold cyan] ").strip().lower()

        if choice in ["c", "confirm", ""]:
            return self._create_character()
        elif choice in ["e", "edit"]:
            self.name = console.input("[bold cyan]New Name:[/bold cyan] ").strip()
            while not self.name:
                print_error("Name cannot be empty")
                self.name = console.input("[bold cyan]New Name:[/bold cyan] ").strip()
            return self._finalize_character()
        elif choice in ["s", "start"]:
            # Restart wizard
            return self.run()
        elif choice in ["x", "cancel"]:
            return None
        else:
            print_error("Invalid choice")
            return self._finalize_character()

    def _show_character_summary(self) -> None:
        """Display comprehensive character summary."""
        race_data = self.races_data[self.race]
        class_data = self.classes_data[self.character_class]

        # Basic info
        console.print(f"[bold cyan]Name:[/bold cyan] {self.name}")
        console.print(f"[bold cyan]Race:[/bold cyan] {race_data['name']}")
        console.print(f"[bold cyan]Class:[/bold cyan] {class_data['name']} (Level {self.level})")
        console.print()

        # Abilities
        console.print("[bold]Ability Scores:[/bold]")
        self._display_abilities(self.abilities)
        console.print()

        # Calculate derived stats
        abilities_obj = Abilities(
            strength=self.abilities["strength"],
            dexterity=self.abilities["dexterity"],
            constitution=self.abilities["constitution"],
            intelligence=self.abilities["intelligence"],
            wisdom=self.abilities["wisdom"],
            charisma=self.abilities["charisma"]
        )

        con_modifier = abilities_obj.con_mod
        hp = self.factory.calculate_hp(class_data, con_modifier)

        # Get AC from starting equipment
        starting_equipment = class_data.get("starting_equipment", [])
        armor_id = None
        for item_id in starting_equipment:
            if item_id in self.items_data.get("armor", {}):
                armor_id = item_id
                break

        armor_data = self.items_data["armor"].get(armor_id) if armor_id else None
        ac = self.factory.calculate_ac(armor_data, abilities_obj.dex_mod)

        # Combat stats
        console.print("[bold]Combat Stats:[/bold]")
        console.print(f"  HP: {hp}")
        console.print(f"  AC: {ac}")
        console.print(f"  Initiative: +{abilities_obj.dex_mod}")
        console.print()

        # Skills
        if self.skill_proficiencies:
            console.print("[bold]Skill Proficiencies:[/bold]")
            for skill_id in self.skill_proficiencies:
                skill_name = self.skills_data[skill_id].get("name", skill_id.title())
                if skill_id in self.expertise_skills:
                    console.print(f"  {skill_name} [bold](Expertise)[/bold]")
                else:
                    console.print(f"  {skill_name}")
            console.print()

        # Equipment preview
        if starting_equipment:
            console.print("[bold]Starting Equipment:[/bold]")
            weapon_id = None
            for item_id in starting_equipment:
                if item_id in self.items_data.get("weapons", {}):
                    weapon_id = item_id
                    weapon_data = self.items_data["weapons"][weapon_id]
                    console.print(f"  Weapon: {weapon_data['name']}")
                    break

            if armor_data:
                console.print(f"  Armor: {armor_data['name']}")

            # Count consumables
            consumable_count = sum(1 for item_id in starting_equipment
                                 if item_id in self.items_data.get("consumables", {}))
            if consumable_count > 0:
                console.print(f"  + {consumable_count} consumable items")

    def _create_character(self) -> Character:
        """
        Create the final Character object.

        Returns:
            Fully initialized Character
        """
        console.print()
        with console.status("[cyan]Creating character...[/cyan]", spinner="dots"):
            race_data = self.races_data[self.race]
            class_data = self.classes_data[self.character_class]

            # Create abilities object
            abilities_obj = Abilities(
                strength=self.abilities["strength"],
                dexterity=self.abilities["dexterity"],
                constitution=self.abilities["constitution"],
                intelligence=self.abilities["intelligence"],
                wisdom=self.abilities["wisdom"],
                charisma=self.abilities["charisma"]
            )

            # Calculate stats
            con_modifier = abilities_obj.con_mod
            hp = self.factory.calculate_hp(class_data, con_modifier)

            # Get AC
            starting_equipment = class_data.get("starting_equipment", [])
            armor_id = None
            for item_id in starting_equipment:
                if item_id in self.items_data.get("armor", {}):
                    armor_id = item_id
                    break

            armor_data = self.items_data["armor"].get(armor_id) if armor_id else None
            ac = self.factory.calculate_ac(armor_data, abilities_obj.dex_mod)

            # Get proficiencies from class
            weapon_proficiencies = class_data.get("weapon_proficiencies", [])
            armor_proficiencies = class_data.get("armor_proficiencies", [])

            # Create character
            character_class_enum = CharacterClass[self.character_class.upper()]

            character = Character(
                name=self.name,
                character_class=character_class_enum,
                level=self.level,
                abilities=abilities_obj,
                max_hp=hp,
                ac=ac,
                xp=0,
                skill_proficiencies=self.skill_proficiencies,
                expertise_skills=self.expertise_skills,
                weapon_proficiencies=weapon_proficiencies,
                armor_proficiencies=armor_proficiencies
            )

            # Set race
            character.race = self.race

            # Set saving throw proficiencies
            character.saving_throw_proficiencies = class_data.get("saving_throw_proficiencies", [])

            # Initialize class resources
            self.factory.initialize_class_resources(character, class_data, self.level)

            # Initialize spellcasting (for spellcasting classes)
            self.factory.initialize_spellcasting(character, class_data, self.spells_data, interactive=False)

            # If we have pre-selected spells (from template), use those
            if self.selected_spells:
                character.known_spells = self.selected_spells
                character.prepared_spells = [s for s in self.selected_spells if not s.endswith("_0")]

            # Apply starting equipment
            self.factory.apply_starting_equipment(character, class_data, self.items_data)

        print_status_message(f"✓ {self.name} created successfully!", "success")

        return character
