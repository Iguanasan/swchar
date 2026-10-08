"""Prerequisite checking and Edge validation engine for Savage Worlds Wild Cards."""

from swchar.models.character import Character
from swchar.models.edges import Edge, Rank, get_edge


class PrerequisiteChecker:
    """Rules engine verifying character eligibility against Edge requirements."""

    @classmethod
    def can_take_edge(
        cls, character: Character, edge: Edge | str
    ) -> tuple[bool, list[str]]:
        """Determine whether a character satisfies all prerequisites for an Edge.

        Args:
            character: Character Wild Card to evaluate.
            edge: Edge instance or Edge name string to validate.

        Returns:
            tuple[bool, list[str]]: (can_take, list_of_reasons_if_unsatisfied)
        """
        if isinstance(edge, str):
            try:
                edge_obj = get_edge(edge)
            except KeyError:
                return False, [f"Unknown edge '{edge}'."]
        else:
            edge_obj = edge

        reasons: list[str] = []

        # 1. Rank prerequisite
        char_rank = getattr(character, "rank", Rank.NOVICE)
        if char_rank < edge_obj.rank:
            reasons.append(
                f"Requires rank {edge_obj.rank.value} (character is {char_rank.value})."
            )

        # 2. Attribute prerequisites
        if edge_obj.prerequisites.attributes:
            for attr_name, min_die in edge_obj.prerequisites.attributes.items():
                char_die = character.attributes[attr_name]
                if char_die < min_die:
                    reasons.append(
                        f"Requires {attr_name.value} {min_die} (character has {char_die})."
                    )

        # 3. Skill prerequisites
        if edge_obj.prerequisites.skills:
            for skill_name, min_die in edge_obj.prerequisites.skills.items():
                skill = character.get_skill(skill_name)
                if skill is None:
                    reasons.append(
                        f"Requires skill {skill_name} at {min_die} (character is untrained)."
                    )
                elif skill.die < min_die:
                    reasons.append(
                        f"Requires skill {skill_name} at {min_die} (character has {skill.die})."
                    )

        # 4. Edge dependency prerequisites
        if edge_obj.prerequisites.edges:
            char_edge_names = [
                (e.name if hasattr(e, "name") else str(e)).strip().lower()
                for e in getattr(character, "edges", [])
            ]
            for req_edge in edge_obj.prerequisites.edges:
                if req_edge.strip().lower() not in char_edge_names:
                    reasons.append(f"Requires prerequisite Edge: {req_edge}.")

        # 5. Arcane Background prerequisite
        if edge_obj.prerequisites.requires_arcane:
            has_arcane_edge = any(
                "arcane background"
                in (e.name if hasattr(e, "name") else str(e)).strip().lower()
                for e in getattr(character, "edges", [])
            )
            has_arcana = character.arcana is not None and bool(character.arcana)
            if not (has_arcane_edge or has_arcana):
                reasons.append("Requires Arcane Background.")

        return len(reasons) == 0, reasons

    @classmethod
    def is_eligible(cls, character: Character, edge: Edge | str) -> bool:
        """Convenience query returning boolean eligibility for an Edge."""
        can_take, _ = cls.can_take_edge(character, edge)
        return can_take

    @classmethod
    def validate_character_edges(cls, character: Character) -> list[str]:
        """Validate all edges currently selected on the character.

        Returns:
            list[str]: Validation error messages for any unmet Edge prerequisites.
        """
        errors: list[str] = []
        for edge_item in getattr(character, "edges", []):
            edge_name = (
                edge_item.name if hasattr(edge_item, "name") else str(edge_item)
            )
            can_take, reasons = cls.can_take_edge(character, edge_item)
            if not can_take:
                reason_str = "; ".join(reasons)
                errors.append(
                    f"Edge '{edge_name}' prerequisites not met: {reason_str}"
                )
        return errors
