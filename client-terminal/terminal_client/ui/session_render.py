# ABOUTME: Turns a Session ActionResult into the terminal client's player-facing output.
# ABOUTME: The single place facade events become printed lines, so nothing prints twice.

"""Rendering for session events.

The terminal client used to run D&D's turn structure itself — advancing
initiative, draining enemy turns, rolling death saves — and print as it went.
The engine's `Session` owns all of that now and reports it as an
`ActionResult`, so the client's job shrinks to turning those events into the
same text players already read.

Two rules keep the output honest:

- Events the CLI already subscribes to on the `EventBus` are ignored here. The
  session's recorder captures bus events *and* those subscribers still fire, so
  rendering them again would print each line twice.
- An `ENEMY_TURN` event describes a whole monster turn, and the facade follows
  it with the synthesized `ATTACK_ROLL` / `DAMAGE_DEALT` / `CHARACTER_DEATH`
  events for the same swing. Those are swallowed: the enemy-turn display has
  already shown that attack in full.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_engine.core.combat import AttackResult
from dnd_engine.utils.events import EventType
from terminal_client.ui.rich_ui import (
    console,
    print_error,
    print_section,
    print_status_message,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from dnd_engine.session import ActionResult, GameEvent

# The synthesized events that restate an attack an ENEMY_TURN already rendered.
_ATTACK_ECHO = frozenset({EventType.ATTACK_ROLL, EventType.DAMAGE_DEALT, EventType.CHARACTER_DEATH})


class SessionEventRenderer:
    """Prints what the session reports, using the CLI's own display helpers."""

    #: Event types `CLI.__init__` subscribes to directly. Rendering them here
    #: would double every line the existing handlers already print.
    BUS_OWNED = frozenset(
        {
            EventType.COMBAT_START,
            EventType.COMBAT_END,
            EventType.COMBAT_FLED,
            EventType.BOSS_DEFEATED,
            EventType.DUNGEON_COMPLETED,
            EventType.ITEM_ACQUIRED,
            EventType.GOLD_ACQUIRED,
            EventType.ROOM_ENTER,
            EventType.LEVEL_UP,
            EventType.FEATURE_GRANTED,
            EventType.LONG_REST,
            EventType.SKILL_CHECK,
            EventType.QUEST_ACTIVATED,
            EventType.QUEST_COMPLETED,
        }
    )

    def __init__(self, cli: Any) -> None:
        """Hold the CLI whose display helpers and lookups this renderer uses.

        Args:
            cli: The owning :class:`~terminal_client.ui.cli.CLI`. Narrative
                enhancement, combat history and creature lookups all live there
                and are reused rather than reimplemented.
        """
        self._cli = cli
        self._echo_events_to_swallow = 0

    def render_event(self, event: GameEvent) -> None:
        """Print one event as the engine produces it.

        This is the streaming entry point, and the one the CLI wires to the
        session. Rendering event by event rather than batching a whole
        `ActionResult` is what keeps output in the order things happened: the
        CLI also subscribes to the bus directly, and those handlers print
        mid-resolution.
        """
        if self._echo_events_to_swallow and event.type in _ATTACK_ECHO:
            self._echo_events_to_swallow -= 1
            return
        self._echo_events_to_swallow = 0

        if event.type is EventType.ENEMY_TURN:
            self.render_enemy_turn(event.data)
            self._echo_events_to_swallow = _echo_event_count(event.data)
            return

        self._render_event(event)

    def render(self, result: ActionResult) -> None:
        """Print everything in one accepted action's result, in order.

        For callers holding a finished result rather than streaming. Rejections
        are the CLI's to display: whether a refused turn is worth a line depends
        on why it was asked for, which this class cannot see.
        """
        self._echo_events_to_swallow = 0
        for event in result.events:
            self.render_event(event)

    def _render_event(self, event: GameEvent) -> None:
        """Dispatch a single event to its display.

        A bus-owned type is suppressed only when it actually came from the bus.
        The session records bus events without a message and always gives its
        own synthesized events one, so that is the discriminator — and it
        matters, because the two overlap: freeform adjudication synthesizes a
        `SKILL_CHECK` carrying the roll, while the CLI also subscribes to
        `SKILL_CHECK` on the bus.
        """
        if event.type in self.BUS_OWNED and event.message is None:
            return

        handler = {
            EventType.DEATH_SAVE: self._render_death_save,
            EventType.TURN_END: self._render_turn_end,
            EventType.DAMAGE_TAKEN: self._render_ongoing_damage,
            EventType.CONDITION_REMOVED: self._render_condition_change,
            EventType.CONDITION_APPLIED: self._render_condition_change,
            EventType.OPPORTUNITY_ATTACK: self._render_message,
            EventType.REACTION_DECLINED: self._render_message,
        }.get(event.type)

        if handler is not None:
            handler(event.data, event.message)
        elif event.message:
            print_status_message(event.message, "info")

    # ------------------------------------------------------------------
    # Individual displays
    # ------------------------------------------------------------------

    def _render_message(self, data: dict[str, Any], message: str | None) -> None:
        """Show the facade's own wording for events that arrive pre-rendered."""
        if message:
            print_status_message(message, "info")

    def _render_death_save(self, data: dict[str, Any], message: str | None) -> None:
        """Report a death saving throw and its consequences."""
        name = data.get("character", "")

        print_section(f"{name}'s Turn - Death Save")
        print_status_message(
            f"{name} is unconscious and must make a death saving throw!", "warning"
        )

        if data.get("natural_20"):
            print_status_message(f"Natural 20! {name} regains 1 HP and consciousness!", "success")
        elif data.get("natural_1"):
            # A natural 1 counts as two failures; the tally can read past 3.
            failures_display = min(data.get("failures", 0), 3)
            print_status_message(
                f"Natural 1! Two failures recorded. Failures: {failures_display}/3", "warning"
            )
        elif data.get("success"):
            print_status_message(
                f"Success! (rolled {data.get('roll')}) Successes: {data.get('successes')}/3",
                "info",
            )
        else:
            failures_display = min(data.get("failures", 0), 3)
            print_status_message(
                f"Failure (rolled {data.get('roll')}) Failures: {failures_display}/3", "warning"
            )

        if data.get("conscious"):
            print_status_message(f"{name} is conscious again with 1 HP!", "success")
        elif data.get("stabilized"):
            print_status_message(
                f"{name} is stabilized! They no longer need to make death saves.", "success"
            )
        elif data.get("dead"):
            print_error(f"{name} has died...")
            self._remove_from_initiative(name)

    def _remove_from_initiative(self, name: str) -> None:
        """Drop a dead character from the initiative display.

        The facade skips the dead by their `is_dead` flag, so this changes no
        rules — but leaving them in the tracker would keep them listed in the
        combat status table, which is not what a player saw before.
        """
        character = self._cli._find_party_member_by_name(name)
        tracker = getattr(self._cli.game_state, "initiative_tracker", None)
        if character is not None and tracker is not None:
            tracker.remove_combatant(character)

    def _render_turn_end(self, data: dict[str, Any], message: str | None) -> None:
        """Report a turn the facade passed over on the player's behalf."""
        actor = data.get("actor", "")
        reason = data.get("reason")

        if reason == "stabilized":
            print_status_message(
                f"{actor} is unconscious but stabilized (no action needed).", "info"
            )
            return

        if reason == "incapacitated":
            conditions = data.get("conditions") or []
            condition_names = ", ".join(c.upper() for c in conditions)
            if condition_names:
                print_status_message(f"{actor} is {condition_names} and cannot act!", "warning")
            else:
                print_status_message(f"{actor} cannot act this turn!", "warning")
            return

        if data.get("error"):
            print_error(f"{actor}: {data['error']}")

    def _render_ongoing_damage(self, data: dict[str, Any], message: str | None) -> None:
        """Report a start-of-turn condition effect, and any death it caused."""
        if message:
            print_status_message(message, "warning")
        if data.get("creature_died"):
            condition = str(data.get("condition", "")).replace("_", " ")
            print_status_message(f"💀 {data.get('actor', '')} is killed by {condition}!", "warning")

    def _render_condition_change(self, data: dict[str, Any], message: str | None) -> None:
        """Report end-of-turn condition outcomes."""
        actor = data.get("actor", "")
        condition = data.get("condition", "")
        outcome = data.get("type")

        if outcome == "repeat_save_success":
            save_result = data.get("save_result") or {}
            ability = str(save_result.get("ability", "")).upper()
            print_status_message(
                f"✓ {actor} succeeds on {ability} save - {condition.upper()} removed!",
                "success",
            )
            return

        if outcome in {"duration_expired", "condition_expired"}:
            # Surprise wears off at the end of the first round every fight;
            # announcing it was noise, so it never was announced.
            if condition != "surprised":
                print_status_message(f"⏱ {condition.upper()} on {actor} has expired!", "info")
            return

        if message:
            print_status_message(message, "info")

    # ------------------------------------------------------------------
    # Enemy turns
    # ------------------------------------------------------------------

    def render_enemy_turn(self, data: dict[str, Any]) -> None:
        """Display one monster's whole turn from its `ENEMY_TURN` payload."""
        enemy_name = data.get("enemy_display_name") or data.get("enemy_name", "")
        action = data.get("action_taken")

        for effect in data.get("turn_start_effects") or []:
            print_status_message(effect.get("message", ""), "warning")
            if effect.get("creature_died"):
                condition = str(effect.get("condition_id", "")).replace("_", " ")
                print_status_message(f"💀 {enemy_name} is killed by {condition}!", "warning")

        if action == "died_start_of_turn":
            # Any death message was already printed with the effect above.
            return

        if action == "incapacitated":
            condition_text = ", ".join(data.get("incapacitating_conditions") or [])
            print_status_message(
                f"⚠️  {enemy_name} is {condition_text} and cannot act this turn!", "warning"
            )
            self._render_turn_end_effects(data)
            return

        if action == "condition_removal":
            self._render_enemy_condition_removal(enemy_name, data)
            return

        if action == "no_targets":
            return  # Nothing to say — combat is about to end.

        if action == "no_valid_attack":
            if data.get("error"):
                print_error(f"{enemy_name} has no valid attack actions!")
            return

        if action == "attack":
            self._render_enemy_attack(enemy_name, data)

    def _render_enemy_condition_removal(self, enemy_name: str, data: dict[str, Any]) -> None:
        """Report a monster spending its turn shaking off a condition."""
        removal = data.get("condition_removal")
        if not removal:
            return

        if removal.get("condition_id") == "on_fire":
            print_status_message(
                f"🔥 {enemy_name} is on fire with low HP! Attempting to extinguish...", "info"
            )
        print_status_message(
            removal.get("message", ""), "success" if removal.get("success") else "warning"
        )

    def _render_enemy_attack(self, enemy_name: str, data: dict[str, Any]) -> None:
        """Report a monster's attack: narrative, mechanics, then consequences."""
        print_status_message(f"{enemy_name}'s turn...", "info")

        target_name = data.get("target_name")
        self._render_concentration_break(target_name, data.get("concentration_broken"))
        self._render_saving_throw(target_name, data)

        attack_payload = data.get("attack_result")
        attack_result = _rebuild_attack_result(attack_payload)

        if attack_result is not None and attack_result.hit:
            self._render_attack_narrative(data, attack_result)

        if attack_result is not None:
            target = self._cli._find_party_member_by_name(target_name)
            self._cli._record_combat_action(
                attack_result,
                defender_hp=getattr(target, "current_hp", None),
                defender_max_hp=getattr(target, "max_hp", None),
            )
            console.print(f"[cyan]⚔️  {data.get('attack_text') or str(attack_result)}[/cyan]")

        if data.get("target_killed"):
            self._render_death(target_name)

        self._render_turn_end_effects(data)

    def _render_concentration_break(
        self, target_name: str | None, broken: dict[str, Any] | None
    ) -> None:
        """Report a target losing concentration on a spell."""
        if not broken:
            return
        save_result = broken.get("save_result") or {}
        console.print(
            f"[yellow]💫 {target_name}'s concentration on "
            f"{broken.get('spell_name')} is broken! "
            f"(CON save: {save_result.get('total')} vs DC {broken.get('dc')})[/yellow]"
        )

    def _render_saving_throw(self, target_name: str | None, data: dict[str, Any]) -> None:
        """Report a saving throw the attack forced, and what it cost."""
        if not data.get("saving_throw_triggered"):
            return
        ability = data.get("save_ability")
        dc = data.get("save_dc")
        if not ability or not dc:
            return

        if data.get("save_succeeded") is False and data.get("conditions_applied"):
            target = self._cli._find_party_member_by_name(target_name)
            for condition in data["conditions_applied"]:
                duration = 0
                if target is not None and hasattr(target, "active_conditions"):
                    metadata = target.active_conditions.get(condition, {})
                    duration = metadata.get("duration_remaining", 0)
                print_status_message(
                    f"💀 {target_name} fails {ability} save (DC {dc}) - "
                    f"{condition.upper()} for {duration} rounds!",
                    "error",
                )
        elif data.get("save_succeeded") is True:
            print_status_message(
                f"✓ {target_name} succeeds on {ability} save (DC {dc})!", "success"
            )

    def _render_attack_narrative(self, data: dict[str, Any], attack_result: AttackResult) -> None:
        """Ask the LLM to describe a landed blow, if narrative is enabled."""
        if not self._cli.llm_enhancer:
            return

        enemy = self._cli._find_enemy_by_name(data.get("enemy_name", ""))
        target = self._cli._find_party_member_by_name(data.get("target_name"))
        if not enemy or not target:
            return

        attack_context = self._cli.context_builder.build_attack_context(
            enemy, target, attack_result, action_data=data.get("action_data")
        )
        with console.status("", spinner="dots"):
            narrative = self._cli.llm_enhancer.get_combat_narrative_sync(
                action_data=attack_context, timeout=20.0
            )
        if narrative:
            self._cli.display_narrative_panel(narrative)

    def _render_death(self, target_name: str | None) -> None:
        """Announce a party member dropping, with narrative when enabled."""
        from dnd_engine.core.character import Character

        target = self._cli._find_party_member_by_name(target_name)
        if self._cli.llm_enhancer and target:
            with console.status("", spinner="dots"):
                death_narrative = self._cli.llm_enhancer.get_death_narrative_sync(
                    character_data={
                        "name": target_name,
                        "is_player": isinstance(target, Character),
                    },
                    timeout=20.0,
                )
            if death_narrative:
                self._cli.display_narrative_panel(death_narrative)

        print_status_message(f"{target_name} has fallen!", "warning")

    def _render_turn_end_effects(self, data: dict[str, Any]) -> None:
        """Report conditions that ran out at the end of a monster's turn."""
        enemy_name = data.get("enemy_name", "")
        for effect in data.get("turn_end_effects") or []:
            if effect.get("effect_type") != "condition_expired":
                continue
            condition = effect.get("condition_id", "")
            # Surprise expiring is not worth a line — see the same rule above.
            if condition == "surprised":
                continue
            print_status_message(f"⏱ {condition.upper()} on {enemy_name} has expired!", "info")


def _echo_event_count(enemy_turn: dict[str, Any]) -> int:
    """How many synthesized events restate the attack an `ENEMY_TURN` described.

    The facade emits `ATTACK_ROLL` for every attack, `DAMAGE_DEALT` only for a
    hit that dealt damage, and `CHARACTER_DEATH` only when the target dropped.
    Counting them exactly is what keeps the suppression scoped to this turn: an
    open-ended "swallow until something else arrives" would still be armed when
    the next attack from another source came through, and would eat it.
    """
    attack = enemy_turn.get("attack_result")
    if not attack:
        return 0

    count = 1
    if attack.get("hit") and attack.get("damage"):
        count += 1
    if enemy_turn.get("target_killed"):
        count += 1
    return count


def _rebuild_attack_result(payload: dict[str, Any] | None) -> AttackResult | None:
    """Rebuild the engine's `AttackResult` from its serialised form.

    The combat-history recorder and the narrative context builder both take the
    real dataclass. Rebuilding it here keeps them unchanged and keeps the event
    payload the single source of what happened.
    """
    if not payload:
        return None
    fields = {f.name for f in AttackResult.__dataclass_fields__.values()}
    return AttackResult(**{k: v for k, v in payload.items() if k in fields})


__all__ = ["SessionEventRenderer"]
