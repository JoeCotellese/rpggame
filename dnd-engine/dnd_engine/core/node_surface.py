# ABOUTME: Node-surface action dispatch — talk/shop/rest/rumors/job-board/examine on settlement nodes.
# ABOUTME: Routes the fixed action vocabulary into the NPC, rest, quest, and skill-check systems.

from typing import TYPE_CHECKING, Any

from dnd_engine.core.npc import NPC, NPCDisposition

if TYPE_CHECKING:
    from dnd_engine.core.character import Character
    from dnd_engine.core.game_state import GameState


class NodeActionError(Exception):
    """Raised when a node action cannot be dispatched.

    Covers actions not authored on the current node, absent NPCs, and
    NPCs that lack the capability an action needs (e.g. no shop). The
    message names the offending action or NPC.
    """


def npc_view(npc: NPC) -> dict[str, Any]:
    """Client-facing NPC data; disposition is a word, never a number.

    The single NPC shape shared by enter_node and interactions so the two
    payloads cannot drift.
    """
    return {
        "id": npc.id,
        "name": npc.name,
        "display_name": npc.display_name,
        "disposition": npc.get_disposition().value,
    }


class NodeSurfaceActions:
    """
    Dispatches the fixed node-action vocabulary for the current node.

    Pure routing layer: every action resolves through an existing engine
    system (NPCManager/NPC data, party_rest, QuestManager,
    Character.make_skill_check). Results are plain dicts for clients to
    render; disposition is always surfaced as a word, never a number.
    """

    def __init__(self, game_state: "GameState"):
        self.game_state = game_state

    # ------------------------------------------------------------------
    # View

    def interactions(self) -> dict[str, Any]:
        """
        Get the current node's available actions, NPCs, and transition.

        Returns:
            {"actions": [normalized action objects], "npcs": [npc views],
             "transition": transition dict or None}
        """
        node = self.game_state.current_node()
        return {
            "actions": self._normalized_actions(node),
            "npcs": [self._npc_view(npc) for npc in self._npcs_present()],
            "transition": node.get("transition"),
        }

    # ------------------------------------------------------------------
    # Social actions

    def talk(self, npc_id: str) -> dict[str, Any]:
        """
        Open conversation with an NPC at the current node.

        Returns:
            {"npc": npc view, "greeting": disposition-appropriate line}
        """
        self._require_action("talk")
        npc = self._require_npc(npc_id)
        return {"npc": self._npc_view(npc), "greeting": npc.get_greeting()}

    def shop(self, npc_id: str) -> dict[str, Any]:
        """
        Open an NPC's shop with disposition-adjusted prices.

        Returns:
            {"refused": False, "npc": view, "inventory": [...], "buy_rate": x}
            or {"refused": True, "npc": view, "dialogue": refusal line} when
            a hostile shopkeeper refuses service.
        """
        self._require_action("shop")
        npc = self._require_npc(npc_id)
        if not npc.shop or not npc.shop.enabled:
            raise NodeActionError(f"{npc.display_name} has no shop")

        effects = self._disposition_effects(npc)
        if effects.get("refuses_service"):
            return {
                "refused": True,
                "npc": self._npc_view(npc),
                "dialogue": npc.get_greeting(),
            }

        price_modifier = effects.get("price_modifier", 1.0)
        inventory = [
            {
                "item_id": item.item_id,
                "price": self._adjusted_price(item.price, price_modifier),
                "stock": item.stock,
            }
            for item in npc.shop.inventory
        ]
        return {
            "refused": False,
            "npc": self._npc_view(npc),
            "inventory": inventory,
            "buy_rate": npc.shop.buy_rate,
        }

    def rest(self, rest_type: str = "long") -> Any:
        """
        Rest at the current node (routes to the engine's party rest).

        Returns:
            PartyRestResult from GameState.party_rest.
        """
        self._require_action("rest")
        return self.game_state.party_rest(rest_type)

    def gather_rumors(self) -> dict[str, Any]:
        """
        Collect rumors from NPCs at the current node.

        Non-hostile NPCs share their general knowledge and local lore.
        NPCs whose disposition grants extra_hints also share the hooks of
        quests currently available. Hostile NPCs refuse.

        Returns:
            {"rumors": [{"npc_id", "npc_name", "disposition", "text"}],
             "refusals": [{"npc_id", "npc_name", "prose"}]}
        """
        self._require_action("gather_rumors")
        rumors: list[dict[str, Any]] = []
        refusals: list[dict[str, Any]] = []

        for npc in self._npcs_present():
            disposition = npc.get_disposition()
            if disposition == NPCDisposition.HOSTILE:
                refusals.append(
                    {"npc_id": npc.id, "npc_name": npc.name, "prose": npc.get_greeting()}
                )
                continue

            texts = list(npc.knowledge.general) + list(npc.knowledge.local_lore)
            if self._disposition_effects(npc).get("extra_hints"):
                texts.extend(self._quest_hook_texts(npc))

            rumors.extend(
                {
                    "npc_id": npc.id,
                    "npc_name": npc.name,
                    "disposition": disposition.value,
                    "text": text,
                }
                for text in texts
            )

        return {"rumors": rumors, "refusals": refusals}

    def read_job_board(self) -> dict[str, Any]:
        """
        Read the job board: hooks for quests currently available.

        Returns:
            {"postings": [{"quest_id", "name", "description"}]}
        """
        self._require_action("read_job_board")
        quest_manager = self.game_state.quest_manager
        if not quest_manager:
            return {"postings": []}
        return {
            "postings": [
                {"quest_id": quest.id, "name": quest.name, "description": quest.description}
                for quest in quest_manager.get_available_quests()
            ]
        }

    def examine(self, action_id: str, character: "Character") -> dict[str, Any]:
        """
        Resolve a skill-gated examine action with the given character.

        The gate resolves through Character.make_skill_check (the d20-test
        primitive); the authored on_success/on_failure prose is returned so
        a failed roll is still a narrative beat.

        Returns:
            {"success": bool, "prose": authored branch, "check": check dict}
        """
        action = self._find_action(action_id)
        if action is None:
            raise NodeActionError(f"No action {action_id!r} at {self.game_state.current_node_id}")
        if not action["id"].startswith("examine_"):
            raise NodeActionError(f"{action_id!r} is not an examinable action")

        gate = action["gate"]
        skills_data = self.game_state.data_loader.load_skills()
        try:
            check = character.make_skill_check(gate["skill"], gate["dc"], skills_data)
        except KeyError as exc:
            raise NodeActionError(
                f"Unknown skill {gate['skill']!r} authored on {action_id!r}"
            ) from exc
        success = check["success"]
        return {
            "success": success,
            "prose": action["on_success"] if success else action["on_failure"],
            "check": check,
        }

    # ------------------------------------------------------------------
    # Internals

    def _normalized_actions(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        """String actions become {"id": <string>}; objects pass through."""
        return [
            {"id": action} if isinstance(action, str) else action
            for action in node.get("actions", [])
        ]

    def _live_node(self) -> dict[str, Any]:
        """The current node's live dict, for internal read-only lookups.

        Avoids current_node()'s defensive deep copy; never returned to
        callers and never mutated.
        """
        self.game_state._require_node_surface()
        return self.game_state.dungeon["nodes"][self.game_state.current_node_id]

    def _find_action(self, action_id: str) -> dict[str, Any] | None:
        """Look up an authored action by id on the current node."""
        for action in self._normalized_actions(self._live_node()):
            if action["id"] == action_id:
                return action
        return None

    def _require_action(self, action_id: str) -> None:
        if self._find_action(action_id) is None:
            raise NodeActionError(f"No action {action_id!r} at {self.game_state.current_node_id}")

    def _npcs_present(self) -> list[NPC]:
        npc_manager = self.game_state.npc_manager
        if not npc_manager:
            return []
        return npc_manager.get_npcs_in_room(self.game_state.current_node_id)

    def _require_npc(self, npc_id: str) -> NPC:
        for npc in self._npcs_present():
            if npc.id == npc_id:
                return npc
        raise NodeActionError(f"{npc_id!r} is not here")

    def _npc_view(self, npc: NPC) -> dict[str, Any]:
        """See module-level npc_view — one shape for all NPC payloads."""
        return npc_view(npc)

    def _disposition_effects(self, npc: NPC) -> dict[str, Any]:
        if not npc.reputation_modifiers:
            return {}
        effects = npc.reputation_modifiers.get("disposition_effects", {})
        return effects.get(npc.get_disposition().value, {})

    def _quest_hook_texts(self, npc: NPC) -> list[str]:
        """Hook lines for available quests this NPC knows, voiced with the
        authored per-NPC npc_hints wording when present (the same mechanism
        the LLM chat path uses), falling back to the quest description."""
        quest_manager = self.game_state.quest_manager
        if not quest_manager:
            return []
        texts = []
        for quest in quest_manager.get_available_quests():
            if quest.id not in npc.knowledge.quest_hooks:
                continue
            hint = quest.hint_for("available", npc.id)
            texts.append(hint or quest.description)
        return texts

    @staticmethod
    def _adjusted_price(price: int, modifier: float) -> int:
        """Disposition-adjusted price, rounded half-up, never below 1."""
        return max(1, int(price * modifier + 0.5))
