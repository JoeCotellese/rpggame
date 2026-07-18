# ABOUTME: Rule-based natural language command parser for D&D game.
# ABOUTME: Uses rapidfuzz for fuzzy string matching to handle typos and variations.

from dataclasses import dataclass, field
from typing import Protocol

from rapidfuzz import fuzz, process


@dataclass
class ParseResult:
    """Result of parsing a free-text command."""

    action: str | None = None
    params: dict = field(default_factory=dict)
    error: str | None = None
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    # Entity suggestions when fuzzy match fails (spell, item, target, npc)
    # Keys are entity types, values are lists of candidate names
    entity_suggestions: dict[str, list[str]] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Return True if parsing was successful."""
        return self.action is not None and self.error is None

    @property
    def needs_clarification(self) -> bool:
        """Return True if entity suggestions are available for user selection."""
        return bool(self.entity_suggestions)


class GameContextProvider(Protocol):
    """Protocol for providing game context to the parser."""

    def get_available_enemies(self) -> list[str]:
        """Return list of enemy names currently in combat."""
        ...

    def get_available_items(self) -> list[str]:
        """Return list of item names available (room + inventory)."""
        ...

    def get_available_spells(self) -> list[str]:
        """Return list of spell names the active character can cast."""
        ...

    def get_available_npcs(self) -> list[str]:
        """Return list of NPC names in the current room."""
        ...

    def get_party_member_names(self) -> list[str]:
        """Return list of party member names."""
        ...

    def is_in_combat(self) -> bool:
        """Return True if currently in combat."""
        ...

    def is_node_surface(self) -> bool:
        """Return True when the current location is a settlement node surface."""
        ...

    def get_available_nodes(self) -> list[str]:
        """Return display names of the settlement's nodes (node surfaces only)."""
        ...


class CommandParser:
    """
    Rule-based natural language command parser.

    Uses keyword matching for action detection and fuzzy string matching
    for entity resolution. Designed for <10ms parsing latency.
    """

    # Action keywords mapped to canonical action names
    ACTION_PATTERNS: dict[str, list[str]] = {
        "move": ["go", "walk", "move", "head", "travel", "proceed", "enter"],
        "attack": ["attack", "hit", "strike", "slash", "stab", "fight", "kill", "smash"],
        "cast": ["cast", "invoke", "channel"],
        "take": ["take", "grab", "pick up", "get", "collect", "loot", "pickup"],
        "search": ["search", "look around", "investigate", "check"],
        "look": ["look", "examine", "inspect", "observe", "view"],
        "talk": ["talk", "speak", "chat", "ask", "converse"],
        "use": ["use", "drink", "eat", "consume", "apply", "activate"],
        "equip": ["equip", "wear", "wield", "put on", "don"],
        "unequip": ["unequip", "remove", "take off", "doff"],
        "flee": ["flee", "run", "escape", "retreat", "disengage"],
        "rest": ["rest", "sleep", "camp", "long rest"],
        "inventory": ["inventory", "items", "bag", "backpack", "i"],
        "status": ["status", "health", "stats", "hp", "character"],
        "help": ["help", "commands", "?"],
        "save": ["save", "quicksave"],
        "stabilize": ["stabilize", "aid"],
        "end_turn": ["end", "done", "pass", "wait", "end turn"],
        "shop": ["shop", "buy", "sell", "trade", "merchant", "store"],
        "spells": ["spells", "spellbook", "cantrips", "magic"],
        "prepare": ["prepare", "memorize", "prepare spells"],
        "effects": ["effects", "conditions", "buffs", "debuffs"],
        "time": ["time", "clock", "hour", "day"],
        "unlock": ["unlock", "open", "pick"],
        "enter_node": ["visit", "go to", "head to", "walk to", "travel to"],
        "gather_rumors": ["gather rumors", "rumors", "gossip", "ask around"],
        "read_job_board": [
            "job board",
            "read board",
            "notice board",
            "read the job",
            "read the board",
            "postings",
        ],
        "depart": ["depart", "leave", "set out"],
    }

    # Actions that only exist on a settlement node surface
    NODE_ONLY_ACTIONS = frozenset(["enter_node", "gather_rumors", "read_job_board", "depart"])

    # Grid-only actions that have no meaning on a node surface
    GRID_ONLY_ACTIONS = frozenset(["search", "take", "unlock"])

    # Direction aliases
    DIRECTION_ALIASES: dict[str, str] = {
        "n": "north",
        "s": "south",
        "e": "east",
        "w": "west",
        "u": "up",
        "d": "down",
        "north": "north",
        "south": "south",
        "east": "east",
        "west": "west",
        "up": "up",
        "down": "down",
        "northern": "north",
        "southern": "south",
        "eastern": "east",
        "western": "west",
        "upward": "up",
        "downward": "down",
        "upwards": "up",
        "downwards": "down",
        "upstairs": "up",
        "downstairs": "down",
    }

    # Threshold for fuzzy matching (0-100)
    FUZZY_THRESHOLD = 60
    SPELL_FUZZY_THRESHOLD = 70  # Higher threshold for spells (more precise names)

    # Words to ignore when parsing
    STOP_WORDS = frozenset(
        [
            "the",
            "a",
            "an",
            "to",
            "at",
            "on",
            "with",
            "my",
            "using",
            "towards",
            "toward",
            "into",
            "through",
            "from",
        ]
    )

    # Target indicators (words that precede targets)
    TARGET_INDICATORS = frozenset(["at", "on", "to", "toward", "towards"])

    def __init__(self, context_provider: GameContextProvider | None = None) -> None:
        """
        Initialize the command parser.

        Args:
            context_provider: Provider for game state context (enemies, items, etc.)
        """
        self.context_provider = context_provider
        # Build reverse lookup: keyword -> action
        self._keyword_to_action: dict[str, str] = {}
        for action, keywords in self.ACTION_PATTERNS.items():
            for keyword in keywords:
                self._keyword_to_action[keyword.lower()] = action

    def parse(self, text: str) -> ParseResult:
        """
        Parse a free-text command into an action and parameters.

        Args:
            text: The raw user input text

        Returns:
            ParseResult with action, params, and optional error/suggestions
        """
        if not text or not text.strip():
            return ParseResult(error="Empty command", suggestions=["help"])

        # Normalize input
        text = text.strip().lower()
        tokens = text.split()

        # Try to detect action
        action, action_confidence, remaining_tokens = self._detect_action(tokens)

        if action is None:
            return ParseResult(
                error=f"Unknown command: {text}",
                suggestions=self._suggest_actions(tokens),
            )

        # The same prose keywords resolve per surface: "go"/"head to" mean a
        # direction on a grid but a destination node in a settlement, and
        # "leave"/"depart" mean the settlement transition only on a node surface.
        if action == "move" and self._on_node_surface():
            action = "enter_node"
        elif action in ("enter_node", "depart") and not self._on_node_surface():
            # "leave" during grid combat means fleeing, not walking a direction
            if (
                action == "depart"
                and self.context_provider
                and self.context_provider.is_in_combat()
            ):
                action = "flee"
            else:
                action = "move"

        # Extract parameters based on action type
        params, param_confidence, entity_suggestions = self._extract_params(
            action, remaining_tokens
        )

        # Validate action in current context
        validation_error = self._validate_action_context(action)
        if validation_error:
            return ParseResult(
                action=action,
                params=params,
                error=validation_error,
                confidence=action_confidence * param_confidence,
                entity_suggestions=entity_suggestions,
            )

        return ParseResult(
            action=action,
            params=params,
            confidence=action_confidence * param_confidence,
            entity_suggestions=entity_suggestions,
        )

    def _detect_action(self, tokens: list[str]) -> tuple[str | None, float, list[str]]:
        """
        Detect the action from the first few tokens.

        Returns:
            Tuple of (action_name, confidence, remaining_tokens)
        """
        if not tokens:
            return None, 0.0, []

        # Check for multi-word action patterns first (e.g., "pick up", "long rest")
        for num_words in (3, 2):
            if len(tokens) >= num_words:
                phrase = " ".join(tokens[:num_words])
                if phrase in self._keyword_to_action:
                    return self._keyword_to_action[phrase], 1.0, tokens[num_words:]

        # Check single word exact match
        first_token = tokens[0]
        if first_token in self._keyword_to_action:
            return self._keyword_to_action[first_token], 1.0, tokens[1:]

        # Try fuzzy match on first token against all keywords
        all_keywords = list(self._keyword_to_action.keys())
        match = process.extractOne(first_token, all_keywords, scorer=fuzz.ratio)
        if match and match[1] >= self.FUZZY_THRESHOLD:
            matched_keyword, score, _ = match
            return self._keyword_to_action[matched_keyword], score / 100.0, tokens[1:]

        return None, 0.0, tokens

    def _extract_params(
        self, action: str, tokens: list[str]
    ) -> tuple[dict, float, dict[str, list[str]]]:
        """
        Extract parameters from remaining tokens based on action type.

        Returns:
            Tuple of (params_dict, confidence, entity_suggestions)
            entity_suggestions maps entity type to list of candidate names
        """
        # Filter out stop words (but keep target indicators for parsing)
        filtered = [t for t in tokens if t not in self.STOP_WORDS or t in self.TARGET_INDICATORS]

        if action == "move":
            params, conf = self._extract_direction(filtered)
            return params, conf, {}
        elif action in ("attack", "stabilize"):
            return self._extract_target(filtered, "enemy")
        elif action == "cast":
            return self._extract_spell_and_target(filtered)
        elif action in ("take", "use", "equip", "unequip", "look"):
            # On a node surface, look/examine targets are authored node
            # actions, not inventory items — pass the text through raw so
            # inventory names can't hijack it.
            if action == "look" and self._on_node_surface():
                target = " ".join(t for t in filtered if t not in self.TARGET_INDICATORS)
                if target:
                    return {"item": target}, 0.7, {}
                return {}, 0.5, {}
            return self._extract_item(filtered)
        elif action == "talk":
            return self._extract_npc(filtered)
        elif action == "shop":
            return self._extract_npc(filtered)
        elif action == "unlock":
            params, conf = self._extract_direction(filtered)
            return params, conf, {}
        elif action == "enter_node":
            return self._extract_node(filtered)

        # Actions with no params (inventory, status, help, etc.)
        return {}, 1.0, {}

    def _extract_direction(self, tokens: list[str]) -> tuple[dict, float]:
        """Extract direction from tokens."""
        for token in tokens:
            if token in self.DIRECTION_ALIASES:
                return {"direction": self.DIRECTION_ALIASES[token]}, 1.0

        # Try fuzzy match on direction words
        directions = list(self.DIRECTION_ALIASES.keys())
        for token in tokens:
            match = process.extractOne(token, directions, scorer=fuzz.ratio)
            if match and match[1] >= self.FUZZY_THRESHOLD:
                return {"direction": self.DIRECTION_ALIASES[match[0]]}, match[1] / 100.0

        return {}, 0.5  # No direction found, will prompt user

    def _extract_target(
        self, tokens: list[str], target_type: str
    ) -> tuple[dict, float, dict[str, list[str]]]:
        """Extract target entity from tokens."""
        if not tokens:
            return {}, 0.5, {}

        # Find target after indicator words
        target_start_idx = 0
        for i, token in enumerate(tokens):
            if token in self.TARGET_INDICATORS and i + 1 < len(tokens):
                target_start_idx = i + 1
                break

        target_text = " ".join(tokens[target_start_idx:])
        target_text = " ".join(t for t in target_text.split() if t not in self.TARGET_INDICATORS)

        if not target_text:
            return {}, 0.5, {}

        # Try fuzzy match against available entities
        if self.context_provider:
            if target_type == "enemy":
                candidates = self.context_provider.get_available_enemies()
            elif target_type == "ally":
                candidates = self.context_provider.get_party_member_names()
            else:
                candidates = []

            if candidates:
                match = process.extractOne(target_text, candidates, scorer=fuzz.WRatio)
                if match and match[1] >= self.FUZZY_THRESHOLD:
                    return {"target": match[0]}, match[1] / 100.0, {}

                # No good match - return suggestions for user to pick from
                suggestions = self._get_entity_suggestions(target_text, candidates)
                if suggestions:
                    return (
                        {"target": target_text, "unmatched": True},
                        0.3,
                        {"target": suggestions},
                    )

        # Return raw target if no context or no match
        return {"target": target_text}, 0.7, {}

    def _extract_spell_and_target(
        self, tokens: list[str]
    ) -> tuple[dict, float, dict[str, list[str]]]:
        """Extract spell name and optional target from tokens."""
        if not tokens:
            return {}, 0.5, {}

        # Split on target indicators
        spell_tokens = []
        target_tokens = []
        found_indicator = False

        for token in tokens:
            if token in self.TARGET_INDICATORS:
                found_indicator = True
                continue
            if found_indicator:
                target_tokens.append(token)
            else:
                spell_tokens.append(token)

        spell_text = " ".join(spell_tokens)
        target_text = " ".join(target_tokens)

        params: dict = {}
        confidence = 1.0
        entity_suggestions: dict[str, list[str]] = {}

        # Match spell name
        if spell_text and self.context_provider:
            spells = self.context_provider.get_available_spells()
            if spells:
                match = process.extractOne(spell_text, spells, scorer=fuzz.WRatio)
                if match and match[1] >= self.SPELL_FUZZY_THRESHOLD:
                    params["spell"] = match[0]
                    confidence *= match[1] / 100.0
                else:
                    # No good match - provide spell suggestions
                    params["spell"] = spell_text
                    params["spell_unmatched"] = True
                    confidence *= 0.3
                    suggestions = self._get_entity_suggestions(spell_text, spells)
                    if suggestions:
                        entity_suggestions["spell"] = suggestions
            else:
                params["spell"] = spell_text
        elif spell_text:
            params["spell"] = spell_text

        # Match target if provided
        if target_text:
            if self.context_provider:
                # Try enemies first (most common spell targets in combat)
                if self.context_provider.is_in_combat():
                    enemies = self.context_provider.get_available_enemies()
                    if enemies:
                        match = process.extractOne(target_text, enemies, scorer=fuzz.WRatio)
                        if match and match[1] >= self.FUZZY_THRESHOLD:
                            params["target"] = match[0]
                            confidence *= match[1] / 100.0
                            return params, confidence, entity_suggestions

                # Try party members (for healing/buff spells)
                allies = self.context_provider.get_party_member_names()
                if allies:
                    match = process.extractOne(target_text, allies, scorer=fuzz.WRatio)
                    if match and match[1] >= self.FUZZY_THRESHOLD:
                        params["target"] = match[0]
                        confidence *= match[1] / 100.0
                        return params, confidence, entity_suggestions

            params["target"] = target_text
            confidence *= 0.7

        return params, confidence, entity_suggestions

    def _extract_item(self, tokens: list[str]) -> tuple[dict, float, dict[str, list[str]]]:
        """Extract item name from tokens."""
        if not tokens:
            return {}, 0.5, {}

        # Filter out target indicators for item-only commands
        item_text = " ".join(t for t in tokens if t not in self.TARGET_INDICATORS)

        if not item_text:
            return {}, 0.5, {}

        if self.context_provider:
            items = self.context_provider.get_available_items()
            if items:
                match = process.extractOne(item_text, items, scorer=fuzz.WRatio)
                if match and match[1] >= self.FUZZY_THRESHOLD:
                    return {"item": match[0]}, match[1] / 100.0, {}

                # No good match - provide item suggestions
                suggestions = self._get_entity_suggestions(item_text, items)
                if suggestions:
                    return (
                        {"item": item_text, "item_unmatched": True},
                        0.3,
                        {"item": suggestions},
                    )

        return {"item": item_text}, 0.7, {}

    def _extract_npc(self, tokens: list[str]) -> tuple[dict, float, dict[str, list[str]]]:
        """Extract NPC name from tokens."""
        if not tokens:
            return {}, 0.5, {}

        npc_text = " ".join(t for t in tokens if t not in self.TARGET_INDICATORS)

        if not npc_text:
            return {}, 0.5, {}

        if self.context_provider:
            npcs = self.context_provider.get_available_npcs()
            if npcs:
                match = process.extractOne(npc_text, npcs, scorer=fuzz.WRatio)
                if match and match[1] >= self.FUZZY_THRESHOLD:
                    return {"npc": match[0]}, match[1] / 100.0, {}

                # No good match - provide NPC suggestions
                suggestions = self._get_entity_suggestions(npc_text, npcs)
                if suggestions:
                    return (
                        {"npc": npc_text, "npc_unmatched": True},
                        0.3,
                        {"npc": suggestions},
                    )

        return {"npc": npc_text}, 0.7, {}

    def _extract_node(self, tokens: list[str]) -> tuple[dict, float, dict[str, list[str]]]:
        """Extract a settlement node name from tokens."""
        if not tokens:
            return {}, 0.5, {}

        node_text = " ".join(t for t in tokens if t not in self.TARGET_INDICATORS)

        if not node_text:
            return {}, 0.5, {}

        candidates = self._available_nodes()
        if candidates:
            match = process.extractOne(node_text, candidates, scorer=fuzz.WRatio)
            if match and match[1] >= self.FUZZY_THRESHOLD:
                return {"node": match[0]}, match[1] / 100.0, {}

            # Unlike free-text NPC names, an unknown node can never be acted
            # on, so it is always flagged unmatched (suggestions may be empty).
            suggestions = self._get_entity_suggestions(node_text, candidates)
            return (
                {"node": node_text, "node_unmatched": True},
                0.3,
                {"node": suggestions} if suggestions else {},
            )

        return {"node": node_text, "node_unmatched": True}, 0.3, {}

    def _on_node_surface(self) -> bool:
        """True when the provider reports a node surface.

        Providers without the node protocol methods degrade to grid
        behavior rather than raising.
        """
        checker = getattr(self.context_provider, "is_node_surface", None)
        return bool(checker()) if callable(checker) else False

    def _available_nodes(self) -> list[str]:
        """Node display names from the provider; [] when unsupported."""
        getter = getattr(self.context_provider, "get_available_nodes", None)
        return getter() if callable(getter) else []

    def _get_entity_suggestions(
        self, text: str, candidates: list[str], limit: int = 5
    ) -> list[str]:
        """
        Get fuzzy match suggestions for an entity.

        Args:
            text: The user's input text
            candidates: Available entity names to match against
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested entity names, sorted by match score
        """
        if not candidates:
            return []

        # Get top matches above a low threshold (for suggestions we're more lenient)
        matches = process.extract(text, candidates, scorer=fuzz.WRatio, limit=limit)

        # Return suggestions that have at least some relevance (score >= 30)
        return [match[0] for match in matches if match[1] >= 30]

    def _validate_action_context(self, action: str) -> str | None:
        """
        Validate that an action is appropriate for current game context.

        Returns error message if invalid, None if valid.
        """
        if not self.context_provider:
            return None

        in_combat = self.context_provider.is_in_combat()

        # Node-surface actions: exploration-only, and only in a settlement.
        # Messages use the spaced form of the action name, never internal ids.
        if action in self.NODE_ONLY_ACTIONS:
            display_name = action.replace("_", " ")
            if in_combat:
                return f"'{display_name}' is not available during combat"
            if not self._on_node_surface():
                return f"'{display_name}' is only available in a settlement"
            return None

        if action in self.GRID_ONLY_ACTIONS and self._on_node_surface():
            return f"'{action}' is not available in a settlement"

        # Actions only valid in combat
        combat_only = {"attack", "flee", "stabilize", "end_turn"}
        if action in combat_only and not in_combat:
            return f"'{action}' is only available during combat"

        # Actions only valid outside combat
        exploration_only = {"rest", "shop", "prepare"}
        if action in exploration_only and in_combat:
            return f"'{action}' is not available during combat"

        return None

    def _suggest_actions(self, tokens: list[str]) -> list[str]:
        """Generate suggestions for unknown commands."""
        if not tokens:
            return ["help", "look", "inventory"]

        # Find closest matching actions
        all_keywords = list(self._keyword_to_action.keys())
        matches = process.extract(tokens[0], all_keywords, scorer=fuzz.ratio, limit=3)

        suggestions = []
        for match_keyword, score, _ in matches:
            if score >= 40:  # Lower threshold for suggestions
                action = self._keyword_to_action[match_keyword]
                if action not in suggestions:
                    suggestions.append(action)

        return suggestions if suggestions else ["help", "look", "inventory"]
