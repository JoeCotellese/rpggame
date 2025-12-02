# ABOUTME: Character creation wizard for interactive character building
# ABOUTME: Supports custom, template-based, and random character generation with questionary UI

from enum import Enum
from typing import Any

import questionary

from dnd_engine.core.character import Character, CharacterClass
from dnd_engine.core.character_factory import CharacterFactory
from dnd_engine.core.creature import Abilities
from dnd_engine.core.dice import DiceRoller
from dnd_engine.rules.loader import DataLoader
from dnd_engine.ui.rich_ui import (
    console,
    print_banner,
    print_error,
    print_message,
    print_section,
    print_status_message,
)


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
        character_factory: CharacterFactory | None = None,
        data_loader: DataLoader | None = None,
        dice_roller: DiceRoller | None = None
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
        self.creation_path: CreationPath | None = None
        self.name: str | None = None
        self.race: str | None = None
        self.character_class: str | None = None
        self.abilities: dict[str, int] | None = None
        self.rolled_scores: list[int] | None = None
        self.skill_proficiencies: list[str] = []
        self.expertise_skills: list[str] = []
        self.selected_spells: list[str] = []
        self.level: int = 1

    def _load_templates(self) -> dict[str, Any]:
        """Load character templates from JSON."""
        try:
            import json

            templates_path = self.data_loader.data_path / "srd" / "character_templates.json"
            with open(templates_path) as f:
                return json.load(f)
        except Exception as e:
            print_error(f"Warning: Could not load character templates: {e}")
            return {}

    def run(self) -> Character | None:
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

        choices = [
            questionary.Choice(
                title="Custom Character - Step-by-step with full control",
                value=CreationPath.CUSTOM
            ),
            questionary.Choice(
                title="Quick Build Template - Pre-configured archetypes",
                value=CreationPath.TEMPLATE
            ),
            questionary.Choice(
                title="Random Character - Fully randomized generation",
                value=CreationPath.RANDOM
            ),
            questionary.Choice(title="← Back/Cancel", value=None),
        ]

        try:
            selected = questionary.select(
                "How would you like to create your character?",
                choices=choices,
                use_arrow_keys=True,
            ).ask()

            if selected is None:
                return False

            self.creation_path = selected
            return True
        except (EOFError, KeyboardInterrupt):
            return False

    def _run_custom_path(self) -> Character | None:
        """
        Run the custom character creation path with Back/Review navigation.

        Step order follows D&D Beyond pattern: Race → Class → Abilities → Skills → Name
        Name comes last so players can choose thematic names after seeing their character.

        Returns:
            Created Character or None if cancelled
        """
        # Custom path steps - name moved to end per UX best practice
        steps = [
            ("Race", self._custom_step_race),
            ("Class", self._custom_step_class),
            ("Abilities", self._custom_step_abilities),
            ("Skills", self._custom_step_skills),
            ("Name", self._custom_step_name),
        ]

        current_step = 0

        while current_step < len(steps):
            console.print()

            # Display visual progress indicator
            self._display_progress_bar(current_step, len(steps), steps)

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

    def _display_progress_bar(
        self, current_step: int, total_steps: int, steps: list[tuple[str, Any]]
    ) -> None:
        """Display a visual progress indicator for the wizard steps."""
        step_names = [s[0] for s in steps]

        # Build progress display with step indicators
        progress_parts = []
        for i, name in enumerate(step_names):
            if i < current_step:
                progress_parts.append(f"[green]✓ {name}[/green]")
            elif i == current_step:
                progress_parts.append(f"[cyan bold]→ {name}[/cyan bold]")
            else:
                progress_parts.append(f"[dim]○ {name}[/dim]")

        console.print(" │ ".join(progress_parts))
        console.print()

    def _custom_step_name(self) -> str:
        """Custom path: Get character name (final step after all choices made)."""
        # Show what character they're naming for context
        if self.race and self.character_class:
            race_name = self.races_data[self.race]["name"]
            class_name = self.classes_data[self.character_class]["name"]
            console.print(
                f"[dim]You're naming your {race_name} {class_name}.[/dim]"
            )
            console.print()

        try:
            name = questionary.text(
                "What is your character's name?",
                validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty",
            ).ask()

            if name is None:
                return "cancel"

            self.name = name.strip()
            print_status_message(f"✓ Name: {self.name}", "success")

            return self._get_navigation_choice(allow_back=True)
        except (EOFError, KeyboardInterrupt):
            return "cancel"

    def _custom_step_race(self) -> str:
        """Custom path: Choose race with questionary."""
        race_list = list(self.races_data.keys())

        # Build choices with race info
        choices = []
        for race_id in race_list:
            race = self.races_data[race_id]
            bonuses = ", ".join(
                [f"+{v} {k.upper()[:3]}" for k, v in race["ability_bonuses"].items()]
            )
            traits = race.get("traits", [])
            traits_str = f" - {', '.join(traits[:2])}" if traits else ""
            display = f"{race['name']} ({bonuses}){traits_str}"
            choices.append(questionary.Choice(title=display, value=race_id))

        choices.append(questionary.Choice(title="← Back", value="back"))

        try:
            selected = questionary.select(
                "Choose your race:",
                choices=choices,
                use_arrow_keys=True,
            ).ask()

            if selected is None:
                return "cancel"
            if selected == "back":
                return "back"

            self.race = selected
            race_data = self.races_data[self.race]
            print_status_message(f"✓ Race: {race_data['name']}", "success")

            return self._get_navigation_choice()
        except (EOFError, KeyboardInterrupt):
            return "cancel"

    def _custom_step_class(self) -> str:
        """Custom path: Choose class with questionary."""
        class_list = list(self.classes_data.keys())

        # Build choices with class info
        choices = []
        for class_id in class_list:
            cls = self.classes_data[class_id]
            hit_die = cls.get("hit_die", "1d8")
            display = f"{cls['name']} ({cls['description']}) - {hit_die}"
            choices.append(questionary.Choice(title=display, value=class_id))

        choices.append(questionary.Choice(title="← Back", value="back"))

        try:
            selected = questionary.select(
                "Choose your class:",
                choices=choices,
                use_arrow_keys=True,
            ).ask()

            if selected is None:
                return "cancel"
            if selected == "back":
                return "back"

            self.character_class = selected
            class_data = self.classes_data[self.character_class]
            print_status_message(f"✓ Class: {class_data['name']}", "success")

            return self._get_navigation_choice()
        except (EOFError, KeyboardInterrupt):
            return "cancel"

    def _custom_step_abilities(self) -> str:
        """Custom path: Roll and assign abilities with questionary UI."""
        try:
            # Roll abilities
            print_message("[bold]Rolling ability scores (4d6 drop lowest)...[/bold]")
            console.print()

            all_rolls = self.factory.roll_all_abilities(self.dice_roller)
            scores = []
            roll_display = []

            for i, (score, dice) in enumerate(all_rolls, 1):
                dropped = min(dice)
                roll_display.append(
                    f"Roll {i}: {sorted(dice, reverse=True)} = {score} (dropped {dropped})"
                )
                scores.append(score)

            print_message("\n".join(roll_display))
            console.print()
            print_status_message(
                f"Your rolled scores: {sorted(scores, reverse=True)}", "info"
            )
            console.print()

            self.rolled_scores = scores

            # Auto-assign based on class priorities
            class_data = self.classes_data[self.character_class]
            self.abilities = self.factory.auto_assign_abilities(scores, class_data)

            print_message(f"[bold]Auto-assigned for {class_data['name']}:[/bold]")
            self._display_abilities(self.abilities)
            console.print()

            # Allow swaps with questionary
            while True:
                swap_choice = questionary.confirm(
                    "Would you like to swap any abilities?", default=False
                ).ask()

                if swap_choice is None:
                    return "cancel"
                if not swap_choice:
                    break

                if self._swap_abilities_interactive():
                    console.print()
                    print_message("[bold]Updated abilities:[/bold]")
                    self._display_abilities(self.abilities)
                    console.print()

            # Apply racial bonuses
            abilities_before = self.abilities.copy()
            self.abilities = self.factory.apply_racial_bonuses(
                self.abilities, self.races_data[self.race]
            )

            console.print()
            print_message(
                f"[bold]After {self.races_data[self.race]['name']} racial bonuses:[/bold]"
            )
            self._display_abilities(self.abilities, before=abilities_before)

            return self._get_navigation_choice()
        except (EOFError, KeyboardInterrupt):
            return "cancel"

    def _custom_step_skills(self) -> str:
        """Custom path: Select skill proficiencies with questionary checkbox."""
        try:
            class_data = self.classes_data[self.character_class]

            # Select skill proficiencies using questionary
            self.skill_proficiencies = self._select_skills_questionary(
                class_data, self.skills_data
            )

            if self.skill_proficiencies is None:
                return "cancel"

            # If Rogue, select expertise
            if self.character_class == "rogue" and self.skill_proficiencies:
                console.print()
                self.expertise_skills = self._select_expertise_questionary(
                    self.skill_proficiencies, self.skills_data
                )
                if self.expertise_skills is None:
                    return "cancel"

            return self._get_navigation_choice()
        except (EOFError, KeyboardInterrupt):
            return "cancel"

    def _select_skills_questionary(
        self, class_data: dict[str, Any], skills_data: dict[str, Any]
    ) -> list[str] | None:
        """
        Select skill proficiencies using questionary checkbox.

        Args:
            class_data: Class definition with skill_proficiencies
            skills_data: Skills data from skills.json

        Returns:
            List of selected skill IDs, or None if cancelled
        """
        skill_profs = class_data.get("skill_proficiencies")
        if not skill_profs:
            return []

        num_to_choose = skill_profs.get("choose", 0)
        available_skills = skill_profs.get("from", [])

        if num_to_choose == 0 or not available_skills:
            return []

        # Build choices with skill descriptions
        choices = []
        for skill_id in available_skills:
            skill_info = skills_data.get(skill_id, {})
            ability = skill_info.get("ability", "?").upper()[:3]
            skill_name = skill_info.get("name", skill_id.title())
            display = f"{skill_name} ({ability})"
            choices.append(questionary.Choice(title=display, value=skill_id))

        def validate_selection(selected: list) -> bool | str:
            if len(selected) != num_to_choose:
                return f"Please select exactly {num_to_choose} skills"
            return True

        selected = questionary.checkbox(
            f"Select {num_to_choose} skill proficiencies:",
            choices=choices,
            validate=validate_selection,
            instruction="(Space to toggle, Enter to confirm)",
        ).ask()

        if selected is None:
            return None

        # Display selected skills
        for skill_id in selected:
            skill_name = skills_data[skill_id].get("name", skill_id.title())
            print_status_message(f"✓ {skill_name}", "success")

        return selected

    def _select_expertise_questionary(
        self, skill_proficiencies: list[str], skills_data: dict[str, Any]
    ) -> list[str] | None:
        """
        Select expertise skills using questionary checkbox (Rogue feature).

        Args:
            skill_proficiencies: List of skills the character is proficient in
            skills_data: Skills data from skills.json

        Returns:
            List of selected expertise skill IDs, or None if cancelled
        """
        if not skill_proficiencies:
            return []

        num_expertise = min(2, len(skill_proficiencies))

        print_message(
            "[bold]Rogue Expertise:[/bold] Choose skills to gain double proficiency bonus."
        )
        console.print()

        # Build choices from proficient skills
        choices = []
        for skill_id in skill_proficiencies:
            skill_info = skills_data.get(skill_id, {})
            ability = skill_info.get("ability", "?").upper()[:3]
            skill_name = skill_info.get("name", skill_id.title())
            display = f"{skill_name} ({ability})"
            choices.append(questionary.Choice(title=display, value=skill_id))

        def validate_selection(selected: list) -> bool | str:
            if len(selected) != num_expertise:
                return f"Please select exactly {num_expertise} skills for expertise"
            return True

        selected = questionary.checkbox(
            f"Select {num_expertise} skills for Expertise:",
            choices=choices,
            validate=validate_selection,
            instruction="(Space to toggle, Enter to confirm)",
        ).ask()

        if selected is None:
            return None

        # Display selected expertise
        for skill_id in selected:
            skill_name = skills_data[skill_id].get("name", skill_id.title())
            print_status_message(f"✓ Expertise: {skill_name}", "success")

        return selected

    def _swap_abilities_interactive(self) -> bool:
        """
        Interactive ability swap using questionary select.

        Returns:
            True if swap was made, False if cancelled
        """
        # Build choices showing current values
        ability_choices = []
        for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            score = self.abilities[ability]
            modifier = self.factory.calculate_ability_modifier(score)
            sign = "+" if modifier >= 0 else ""
            display = f"{ability.upper()[:3]}: {score} ({sign}{modifier})"
            ability_choices.append(questionary.Choice(title=display, value=ability))

        try:
            ability1 = questionary.select(
                "Select first ability to swap:",
                choices=ability_choices,
                use_arrow_keys=True,
            ).ask()

            if ability1 is None:
                return False

            # Filter out the first choice for second selection
            remaining_choices = [c for c in ability_choices if c.value != ability1]

            ability2 = questionary.select(
                f"Swap {ability1.upper()[:3]} with:",
                choices=remaining_choices,
                use_arrow_keys=True,
            ).ask()

            if ability2 is None:
                return False

            self.abilities = self.factory.swap_abilities(
                self.abilities, ability1, ability2
            )
            print_status_message(
                f"Swapped {ability1.upper()[:3]} ↔ {ability2.upper()[:3]}", "success"
            )
            return True
        except ValueError as e:
            print_error(str(e))
            return False
        except (EOFError, KeyboardInterrupt):
            return False

    def _display_abilities(self, abilities: dict[str, int], before: dict[str, int] | None = None) -> None:
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
        Get navigation choice from user using questionary.

        Args:
            allow_back: Whether to allow Back option

        Returns:
            "next", "back", "review", or "cancel"
        """
        console.print()

        choices = [questionary.Choice(title="Continue →", value="next")]
        if allow_back:
            choices.append(questionary.Choice(title="← Back", value="back"))
        choices.append(questionary.Choice(title="Review Progress", value="review"))
        choices.append(questionary.Choice(title="Cancel", value="cancel"))

        try:
            selected = questionary.select(
                "What would you like to do?",
                choices=choices,
                use_arrow_keys=True,
            ).ask()

            if selected is None:
                return "cancel"

            if selected == "cancel":
                confirm = questionary.confirm(
                    "Cancel character creation?", default=False
                ).ask()
                if confirm:
                    return "cancel"
                return self._get_navigation_choice(allow_back)

            return selected
        except (EOFError, KeyboardInterrupt):
            return "cancel"

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

    def _run_template_path(self) -> Character | None:
        """
        Run the template-based character creation path with questionary.

        Returns:
            Created Character or None if cancelled
        """
        console.print()
        print_section("Quick Build Templates")
        console.print()

        if not self.templates_data:
            print_error("No templates available")
            return None

        # Build choices with template descriptions
        choices = []
        for template_id, template in self.templates_data.items():
            race_name = self.races_data.get(template["race"], {}).get("name", template["race"])
            class_name = self.classes_data.get(template["class"], {}).get("name", template["class"])
            display = f"{template['name']} - {race_name} {class_name}"
            choices.append(
                questionary.Choice(title=display, value=template_id)
            )

        choices.append(questionary.Choice(title="← Back/Cancel", value=None))

        try:
            selected = questionary.select(
                "Choose a character template:",
                choices=choices,
                use_arrow_keys=True,
            ).ask()

            if selected is None:
                return None

            return self._create_from_template(selected)
        except (EOFError, KeyboardInterrupt):
            return None

    def _create_from_template(self, template_id: str) -> Character | None:
        """
        Create character from template with questionary UI.

        Args:
            template_id: ID of template to use

        Returns:
            Created Character or None if cancelled
        """
        try:
            template = self.templates_data[template_id]

            console.print()
            print_status_message(f"Creating {template['name']}...", "info")
            console.print()

            # Set wizard state from template
            self.race = template["race"]
            self.character_class = template["class"]
            self.abilities = template["abilities"].copy()

            # Apply racial bonuses
            self.abilities = self.factory.apply_racial_bonuses(
                self.abilities, self.races_data[self.race]
            )

            # Show template details
            console.print(f"[bold]Template:[/bold] {template['name']}")
            console.print(f"[bold]Race:[/bold] {self.races_data[self.race]['name']}")
            console.print(
                f"[bold]Class:[/bold] {self.classes_data[self.character_class]['name']}"
            )
            console.print(f"[dim]{template['description']}[/dim]")
            console.print()

            # Get character name using questionary
            name = questionary.text(
                "What is your character's name?",
                validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty",
            ).ask()

            if name is None:
                return None

            self.name = name.strip()

            # Auto-select skills from template
            self.skill_proficiencies = template.get("skill_choices", [])
            self.expertise_skills = template.get("expertise_choices", [])

            # Handle spells for spellcasters
            if "spell_preferences" in template:
                spell_prefs = template["spell_preferences"]
                self.selected_spells = (
                    spell_prefs.get("cantrips", []) + spell_prefs.get("level_1", [])
                )

            # Show final summary and confirm
            return self._finalize_character()
        except (EOFError, KeyboardInterrupt):
            return None

    def _run_random_path(self) -> Character | None:
        """
        Run the random character generation path with questionary UI.

        Returns:
            Created Character or None if cancelled
        """
        console.print()
        print_section("Random Character Generator")
        console.print()

        try:
            while True:
                # Generate random character
                self._generate_random_character()

                # Show preview
                self._show_random_preview()
                console.print()

                choice = questionary.select(
                    "What would you like to do?",
                    choices=[
                        questionary.Choice(title="Accept this character", value="accept"),
                        questionary.Choice(title="Regenerate", value="regenerate"),
                        questionary.Choice(title="← Cancel", value="cancel"),
                    ],
                    use_arrow_keys=True,
                ).ask()

                if choice is None or choice == "cancel":
                    return None

                if choice == "accept":
                    # Get name using questionary
                    console.print()
                    name = questionary.text(
                        "Character name (leave empty for random):",
                    ).ask()

                    if name is None:
                        return None

                    if not name.strip():
                        self.name = self._generate_random_name()
                        print_status_message(f"Random name: {self.name}", "info")
                    else:
                        self.name = name.strip()

                    return self._finalize_character()

                # choice == "regenerate" - loop continues
                console.print()

        except (EOFError, KeyboardInterrupt):
            return None

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
        self.abilities = dict(zip(ability_names, standard_array, strict=True))

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

    def _finalize_character(self) -> Character | None:
        """
        Show final summary and create character with questionary confirmation.

        Returns:
            Created Character or None if user cancels
        """
        console.print()
        print_section("Character Summary")
        console.print()

        # Build comprehensive summary
        self._show_character_summary()

        try:
            console.print()
            choice = questionary.select(
                "What would you like to do?",
                choices=[
                    questionary.Choice(title="✓ Confirm and Create", value="confirm"),
                    questionary.Choice(title="Edit Name", value="edit"),
                    questionary.Choice(title="Start Over", value="restart"),
                    questionary.Choice(title="Cancel", value="cancel"),
                ],
                use_arrow_keys=True,
            ).ask()

            if choice is None or choice == "cancel":
                return None

            if choice == "confirm":
                return self._create_character()
            elif choice == "edit":
                new_name = questionary.text(
                    "Enter new name:",
                    default=self.name,
                    validate=lambda x: len(x.strip()) > 0 or "Name cannot be empty",
                ).ask()
                if new_name is None:
                    return None
                self.name = new_name.strip()
                return self._finalize_character()
            elif choice == "restart":
                # Restart wizard
                return self.run()

            return None
        except (EOFError, KeyboardInterrupt):
            return None

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
                charisma=self.abilities["charisma"],
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
                armor_proficiencies=armor_proficiencies,
            )

            # Set race and racial traits
            character.race = self.race
            character.darkvision_range = race_data.get("darkvision_range", 0)

            # Set saving throw proficiencies
            character.saving_throw_proficiencies = class_data.get(
                "saving_throw_proficiencies", []
            )

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
