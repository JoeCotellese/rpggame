# ABOUTME: Rich UI utilities for enhanced terminal display
# ABOUTME: Provides reusable rich components for formatting game output

from typing import Any

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.table import Table

from dnd_engine.utils.logging_config import MAX_CONSOLE_WIDTH, init_logging

# Global console instance - initialized via init_console()
console = Console(width=MAX_CONSOLE_WIDTH)


def init_console(debug_mode: bool = False) -> None:
    """
    Initialize the global console with optional debug logging.

    This must be called early in the application startup, before
    any console output is generated.

    Args:
        debug_mode: Whether to enable debug mode with file logging
    """
    global console

    # Initialize logging config
    logging_config = init_logging(debug_mode)

    # Create console (will be dual-output if debug enabled)
    console = logging_config.create_console()


def print_title(title: str, subtitle: str | None = None) -> None:
    """Display a styled title panel.

    Args:
        title: Main title text
        subtitle: Optional subtitle text
    """
    if subtitle:
        content = f"{title}\n[dim]{subtitle}[/dim]"
    else:
        content = title

    panel = Panel(
        Align.center(content), style=Style(color="cyan", bold=True), expand=False, padding=(1, 2)
    )
    console.print(panel)


def print_banner(
    title: str = "D&D 5E Terminal Adventure", version: str = "0.1.0", color: str = "blue"
) -> None:
    """Display a styled banner with title and optional version.

    Args:
        title: Banner title (default: D&D 5E Terminal Adventure)
        version: Optional version string (default: 0.1.0)
        color: Color scheme (blue, green, cyan, magenta)
    """
    text = title
    if version:
        text += f"\nVersion {version}"

    panel = Panel(
        Align.center(text),
        style=Style(color=color, bold=True),
        expand=False,
        box=box.DOUBLE,
        padding=(1, 3),
    )
    console.print(panel)


def create_party_status_table(party_data: list[dict[str, Any]]) -> Table:
    """Create a styled table for party status display.

    Args:
        party_data: List of dicts with character info
                   {name, level, class, hp, max_hp, ac, xp, active_effects, spell_slots}

    Returns:
        Formatted Rich Table
    """
    # Check if any character has spell slots to determine if we need the column
    any_spellcaster = any(char.get("spell_slots") for char in party_data)

    table = Table(title="PARTY STATUS", style="cyan", show_header=True, header_style="bold magenta")
    table.add_column("Character", style="bold")
    table.add_column("Class", style="dim")
    table.add_column("Level", justify="center")
    table.add_column("HP", justify="center")
    table.add_column("AC", justify="center")
    if any_spellcaster:
        table.add_column("Spell Slots", style="cyan", no_wrap=False)
    table.add_column("Active Effects", style="dim", no_wrap=False)
    table.add_column("XP", justify="right")

    for char in party_data:
        # Check if character is dead first
        is_dead = char.get("is_dead", False)

        if is_dead:
            hp_text = "[red bold]💀 DEAD[/red bold]"
        else:
            # Color HP based on status
            hp = char.get("hp", 0)
            max_hp = char.get("max_hp", 1)

            if hp == 0:
                # Unconscious - at 0 HP but not dead yet (making death saves)
                hp_text = "[red bold]⚠ UNCONSCIOUS[/red bold]"
            else:
                hp_percent = hp / max_hp if max_hp > 0 else 0

                if hp_percent <= 0.25:
                    hp_color = "red"
                    hp_symbol = "⚠ "
                elif hp_percent <= 0.5:
                    hp_color = "yellow"
                    hp_symbol = "● "
                else:
                    hp_color = "green"
                    hp_symbol = "✓ "

                hp_text = f"[{hp_color}]{hp_symbol}{hp}/{max_hp}[/{hp_color}]"

        # Format active effects and conditions
        effects_text = []

        # Add spell effects from time_manager
        active_effects = char.get("active_effects", [])
        for effect in active_effects:
            # Build effect display: "Name (duration)"
            effect_name = effect.source
            time_remaining = effect.get_time_remaining_display()
            concentration_marker = " 🎯" if effect.concentration else ""

            effects_text.append(
                f"[magenta]{effect_name}[/magenta] ({time_remaining}){concentration_marker}"
            )

        # Add conditions (paralyzed, stunned, etc.)
        conditions = char.get("conditions", {})
        for condition_name, metadata in conditions.items():
            # Format condition with duration if available
            duration = metadata.get("duration_remaining")
            if duration is not None:
                effects_text.append(f"[red]{condition_name.upper()}[/red] ({duration})")
            else:
                effects_text.append(f"[red]{condition_name.upper()}[/red]")

        effects_display = "\n".join(effects_text) if effects_text else "—"

        # Build row data
        row_data = [
            f"[bold]{char.get('name', 'Unknown')}[/bold]",
            char.get("class", "—"),
            str(char.get("level", 0)),
            hp_text,
            str(char.get("ac", 0)),
        ]

        # Add spell slots column if any character has them
        if any_spellcaster:
            spell_slots = char.get("spell_slots")
            row_data.append(spell_slots if spell_slots else "—")

        row_data.append(effects_display)
        row_data.append(str(char.get("xp", 0)))

        table.add_row(*row_data)

    return table


def create_inventory_table(items: dict[str, list[dict[str, Any]]]) -> Table:
    """Create a styled table for inventory display.

    Args:
        items: Dict with categories (weapons, armor, consumables)
               Each category has list of {name, quantity, equipped, quest_item}

    Returns:
        Formatted Rich Table
    """
    table = Table(title="INVENTORY", style="green", show_header=True, header_style="bold magenta")
    table.add_column("Item", style="bold")
    table.add_column("Category", style="dim")
    table.add_column("Qty", justify="center")
    table.add_column("Status", justify="center")

    for category, item_list in items.items():
        for item in item_list:
            status = "[bold yellow]⚔ EQUIPPED[/bold yellow]" if item.get("equipped") else "—"
            item_name = item.get("name", "Unknown")
            if item.get("quest_item"):
                item_name = f"[bold cyan]★[/bold cyan] {item_name}"
            table.add_row(item_name, category.capitalize(), str(item.get("quantity", 1)), status)

    return table


def create_combat_table(combatants: list[dict[str, Any]]) -> Table:
    """Create a styled table for combat display.

    Args:
        combatants: List of dicts with {name, initiative, hp, max_hp, is_player,
                   active_effects, conditions, death_saves, concentration}

    Returns:
        Formatted Rich Table
    """
    table = Table(
        title="COMBAT INITIATIVE", style="red", show_header=True, header_style="bold yellow"
    )
    table.add_column("Combatant", style="bold")
    table.add_column("Initiative", justify="center")
    table.add_column("HP", justify="center")
    table.add_column("Effects", style="dim", no_wrap=False)
    table.add_column("Status", justify="center")

    for combatant in combatants:
        # Use arrow for current turn
        prefix = "→ " if combatant.get("current_turn") else "  "

        hp = combatant.get("hp", 0)
        max_hp = combatant.get("max_hp", 1)
        hp_text = f"{hp}/{max_hp}"

        # Determine status with death save information
        if hp <= 0:
            # Check for death save data (player characters)
            death_saves = combatant.get("death_saves")
            if death_saves:
                successes = death_saves.get("successes", 0)
                failures = death_saves.get("failures", 0)
                stabilized = death_saves.get("stabilized", False)

                if failures >= 3:
                    status = "[red bold]DEAD[/red bold]"
                    color = "red dim"
                elif stabilized:
                    status = "[yellow]STABILIZED[/yellow]"
                    color = "yellow"
                else:
                    # Unconscious with death saves
                    status = f"[yellow]UNCONSCIOUS[/yellow]\n[dim]Success: {successes}/3, Fail: {failures}/3[/dim]"
                    color = "yellow"
            else:
                # Non-player without death saves
                status = "[red]DEFEATED[/red]"
                color = "red"
        else:
            # Check for incapacitating conditions
            conditions = combatant.get("conditions", [])
            incapacitating = ["paralyzed", "stunned", "unconscious", "petrified"]
            active_incapacitating = [c for c in conditions if c in incapacitating]

            if active_incapacitating:
                # Show primary incapacitating condition
                condition_name = active_incapacitating[0].upper()
                status = f"[yellow]{condition_name}[/yellow]"
                color = "yellow"
            elif conditions:
                # Show other conditions
                condition_name = conditions[0].upper()
                status = f"[cyan]{condition_name}[/cyan]"
                color = "cyan"
            else:
                status = "[green]ACTIVE[/green]"
                color = "white"

            # Add concentration info if present
            concentration = combatant.get("concentration")
            if concentration:
                status += f"\n[magenta]🎯 {concentration}[/magenta]"

        # Format active effects
        active_effects = combatant.get("active_effects", [])
        if active_effects:
            effects_text = []
            for effect in active_effects:
                effect_name = effect.source
                time_remaining = effect.get_time_remaining_display()
                concentration_marker = " 🎯" if effect.concentration else ""
                effects_text.append(
                    f"[magenta]{effect_name}[/magenta] ({time_remaining}){concentration_marker}"
                )
            effects_display = "\n".join(effects_text)
        else:
            effects_display = "—"

        name_style = "bold yellow" if combatant.get("is_player") else "white"

        table.add_row(
            f"{prefix}[{name_style}]{combatant.get('name', 'Unknown')}[/{name_style}]",
            str(combatant.get("initiative", 0)),
            f"[{color}]{hp_text}[/{color}]",
            effects_display,
            status,
        )

    return table


def print_status_message(message: str, message_type: str = "info") -> None:
    """Print a styled status message.

    Args:
        message: Message text
        message_type: Type of message (info, success, warning, error)
    """
    colors = {
        "info": "blue",
        "success": "green",
        "warning": "yellow",
        "error": "red",
    }

    symbols = {
        "info": "ℹ",
        "success": "✓",
        "warning": "⚠",
        "error": "✗",
    }

    color = colors.get(message_type, colors["info"])
    symbol = symbols.get(message_type, "•")
    style = Style(color=color, bold=(message_type == "error"))

    console.print(f"[{color}]{symbol}[/{color}] {message}", style=style)


def print_error(message: str, error: Exception | None = None) -> None:
    """Print an error message with optional exception details.

    Args:
        message: Error message
        error: Optional exception for details
    """
    console.print(f"[bold red]✗ ERROR:[/bold red] {message}")
    if error:
        console.print(f"[dim red]{str(error)}[/dim red]")


def print_room_description(title: str, description: str, exits: list[str]) -> None:
    """Print a formatted room description.

    Args:
        title: Room title
        description: Room description text
        exits: List of available exits
    """
    content = f"{description}\n\n[bold cyan]Exits:[/bold cyan] {', '.join(exits)}"
    panel = Panel(
        content, title=f"[bold]{title}[/bold]", style="cyan", expand=False, padding=(1, 2)
    )
    console.print(panel)


def print_help_section(title: str, commands: list[tuple]) -> None:
    """Print a formatted help section with commands.

    Args:
        title: Section title
        commands: List of (command, description) tuples
    """
    table = Table(title=title, style="magenta", show_header=True, header_style="bold")
    table.add_column("Command", style="bold cyan")
    table.add_column("Description", style="white")

    for command, description in commands:
        table.add_row(command, description)

    console.print(table)


def print_section(title: str, content: str = "") -> None:
    """Print a formatted section with title and optional content.

    When content is empty, prints a styled header without a box.
    When content is provided, prints a full bordered panel.

    Args:
        title: Section title
        content: Optional section content
    """
    if not content or not content.strip():
        # Print styled header without box for empty sections
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
        console.print("[cyan]" + "─" * min(len(title), 60) + "[/cyan]")
        return

    # Render full bordered panel when content exists
    panel = Panel(content, title=f"[bold cyan]{title}[/bold cyan]", style="cyan", expand=False)
    console.print(panel)


def print_list(items: list[str], title: str | None = None, numbered: bool = False) -> None:
    """Print a formatted list of items.

    Args:
        items: List of items to display
        title: Optional title for the list
        numbered: Whether to number the items
    """
    content = ""
    for i, item in enumerate(items):
        if numbered:
            content += f"{i + 1}. {item}\n"
        else:
            content += f"• {item}\n"

    if title:
        panel = Panel(
            content.rstrip(), title=f"[bold cyan]{title}[/bold cyan]", style="cyan", expand=False
        )
        console.print(panel)
    else:
        console.print(content.rstrip())


def print_choice_menu(title: str, options: list[dict[str, str]]) -> None:
    """Print a formatted choice menu.

    Args:
        title: Menu title
        options: List of dicts with 'number' and 'text' keys
    """
    content = ""
    for opt in options:
        num = opt.get("number", "")
        text = opt.get("text", "")
        content += f"[bold cyan]{num}.[/bold cyan] {text}\n"

    panel = Panel(
        content.rstrip(), title=f"[bold yellow]{title}[/bold yellow]", style="yellow", expand=False
    )
    console.print(panel)


def print_message(message: str) -> None:
    """Print a plain message without status symbols.

    Args:
        message: Message text
    """
    console.print(message)


def print_input_prompt(text: str) -> str:
    """Print an input prompt and get user input.

    Args:
        text: Prompt text

    Returns:
        User input
    """
    return console.input(f"[bold cyan]{text}[/bold cyan] ")


def print_mechanics_panel(content: str) -> None:
    """Display game mechanics in a distinct panel.

    Args:
        content: Mechanics text to display (attack rolls, damage, etc.)
    """
    panel = Panel(
        content, title="⚔️  Mechanics", border_style="dim blue", padding=(0, 1), expand=False
    )
    console.print(panel)


def print_combat_action(mechanics: str, narrative: str | None = None) -> None:
    """
    Display combat action with mechanics and optional narrative in a unified sequential flow.

    Args:
        mechanics: Mechanics text (attack rolls, damage, etc.)
        narrative: Optional narrative enhancement
    """
    # Print mechanics first
    console.print(f"[dim blue]⚔️  {mechanics}[/dim blue]")

    # Print narrative if available
    if narrative:
        from rich.markdown import Markdown

        console.print(Markdown(narrative), style="gold1")


def print_narrative_loading() -> None:
    """Display loading state while LLM generates narrative."""
    from rich.text import Text

    loading_text = Text("⏳ Enhancing narrative...", style="dim italic")
    panel = Panel(
        loading_text, title="✨ Narrative", border_style="yellow", padding=(1, 2), expand=False
    )
    console.print(panel)


def print_narrative_panel(content: str) -> None:
    """Display LLM-enhanced narrative in a distinct panel.

    Args:
        content: Narrative text to display
    """
    from rich.markdown import Markdown

    panel = Panel(
        Markdown(content), title="✨ Narrative", border_style="gold1", padding=(1, 2), expand=False
    )
    console.print(panel)


def create_character_sheet_table(character_data: dict[str, Any]) -> Table:
    """Create a styled table for character sheet display.

    Args:
        character_data: Character information dict

    Returns:
        Formatted Rich Table
    """
    table = Table(title="CHARACTER SHEET", style="magenta", show_header=False)
    table.add_column("Attribute", style="bold cyan", width=20)
    table.add_column("Value", style="white")

    # Basic info
    table.add_row("Name", character_data.get("name", "—"))
    table.add_row("Race", character_data.get("race", "—"))
    table.add_row("Class", character_data.get("class", "—"))
    table.add_row("Level", str(character_data.get("level", 0)))

    # Abilities
    table.add_row("", "")  # Empty row for spacing
    abilities = character_data.get("abilities", {})
    for ability, score in abilities.items():
        modifier = (score - 10) // 2
        sign = "+" if modifier >= 0 else ""
        table.add_row(f"{ability.upper()}", f"{score} ({sign}{modifier})")

    # Combat stats
    table.add_row("", "")  # Empty row for spacing
    table.add_row("HP", f"{character_data.get('hp', 0)}/{character_data.get('max_hp', 0)}")
    table.add_row("AC", str(character_data.get("ac", 0)))

    return table
