"""XML serialization engine for Savage Worlds Adventure Edition characters."""

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName
from swchar.models.character import Character
from swchar.models.edges import EDGES
from swchar.rules.derived_stats import DerivedStatsCalculator
from swchar.rules.encumbrance import EncumbranceCalculator


class XmlSerializationError(Exception):
    """Base exception for all XML serialization and deserialization errors."""


class XmlSyntaxError(XmlSerializationError):
    """Raised when XML syntax is malformed or unparseable."""


class XmlValidationError(XmlSerializationError):
    """Raised when XML document violates schema or data integrity constraints."""


class CharacterXmlSerializer:
    """Serializes Savage Worlds Wild Card characters into canonical XML."""

    @classmethod
    def to_xml_string(cls, character: Character) -> str:
        """Serialize a Character domain instance into canonical, schema-compliant XML string.

        Args:
            character: The Character Wild Card aggregate root to serialize.

        Returns:
            Well-formatted XML string including XML declaration.
        """
        root = ET.Element("SavageWorldsCharacter", version="1.0", system="SWADE")

        cls._build_identity(root, character)
        cls._build_attributes(root, character)
        cls._build_skills(root, character)
        cls._build_hindrances(root, character)
        cls._build_edges(root, character)
        cls._build_derived_stats(root, character)
        cls._build_arcana(root, character)
        cls._build_inventory(root, character)

        ET.indent(root, space="  ")
        xml_body = ET.tostring(root, encoding="utf-8").decode("utf-8")
        xml_body = xml_body.replace(" />", "/>")
        return f'<?xml version="1.0" encoding="utf-8"?>\n{xml_body}\n'

    @classmethod
    def export_to_file(cls, character: Character, file_path: Path | str) -> None:
        """Serialize a Character and write it to an XML file.

        Args:
            character: Character Wild Card to export.
            file_path: Destination file path (Path object or string).
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        xml_content = cls.to_xml_string(character)
        path.write_text(xml_content, encoding="utf-8")

    @classmethod
    def _build_identity(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Identity> XML section."""
        ident = ET.SubElement(root, "Identity")
        ET.SubElement(ident, "Id").text = str(character.id)
        ET.SubElement(ident, "Name").text = character.name
        ET.SubElement(ident, "Concept").text = character.concept

        ancestry_name = (
            character.ancestry.name
            if hasattr(character.ancestry, "name")
            else str(character.ancestry)
        )
        ET.SubElement(ident, "Ancestry").text = ancestry_name

        rank_val = (
            character.rank.value
            if hasattr(character.rank, "value")
            else str(character.rank)
        )
        ET.SubElement(ident, "Rank").text = rank_val
        ET.SubElement(ident, "Bennies").text = str(
            character.bennies if character.bennies is not None else 3
        )

        cash_elem = ET.SubElement(ident, "Cash", currency="USD")
        cash_elem.text = f"{float(character.cash):.2f}"

    @classmethod
    def _build_attributes(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Attributes> XML section with all 5 core traits."""
        attrs = ET.SubElement(root, "Attributes")
        attr_order = [
            (AttributeName.AGILITY.value, character.attributes.agility),
            (AttributeName.SMARTS.value, character.attributes.smarts),
            (AttributeName.SPIRIT.value, character.attributes.spirit),
            (AttributeName.STRENGTH.value, character.attributes.strength),
            (AttributeName.VIGOR.value, character.attributes.vigor),
        ]
        for name, die in attr_order:
            ET.SubElement(attrs, "Attribute", name=name, die=str(die))

    @classmethod
    def _build_skills(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Skills> XML section."""
        skills = ET.SubElement(root, "Skills")
        for skill in character.skills.values():
            attr_val = (
                skill.attribute.value
                if hasattr(skill.attribute, "value")
                else str(skill.attribute)
            )
            ET.SubElement(
                skills,
                "Skill",
                name=skill.name,
                attribute=attr_val,
                die=str(skill.die),
                core="true" if skill.core else "false",
            )

    @classmethod
    def _build_hindrances(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Hindrances> XML section and <HindranceRewards>."""
        hindrances = ET.SubElement(root, "Hindrances")
        for h in character.hindrances:
            hname = h.name if hasattr(h, "name") else str(h)
            htype = (
                h.severity.value
                if hasattr(h, "severity") and hasattr(h.severity, "value")
                else "Minor"
            )
            ET.SubElement(hindrances, "Hindrance", name=hname, type=htype)

        rewards_elem = ET.SubElement(hindrances, "HindranceRewards")
        hr = getattr(character, "hindrance_rewards", None)
        attr_bonus = getattr(hr, "attribute_bonuses", 0) if hr else 0
        skill_bonus = getattr(hr, "skill_bonuses", 0) if hr else 0
        edge_bonus = getattr(hr, "edge_bonuses", 0) if hr else 0
        cash_bonus = getattr(hr, "cash_bonuses", 0) if hr else 0

        ET.SubElement(rewards_elem, "AttributePointsBonus").text = str(attr_bonus)
        ET.SubElement(rewards_elem, "SkillPointsBonus").text = str(skill_bonus)
        ET.SubElement(rewards_elem, "ExtraEdgesBonus").text = str(edge_bonus)
        ET.SubElement(rewards_elem, "CashBonus").text = str(cash_bonus)

    @classmethod
    def _build_edges(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Edges> XML section."""
        edges = ET.SubElement(root, "Edges")
        for e in character.edges:
            if hasattr(e, "name"):
                ename = e.name
                ecat = (
                    e.category.value
                    if hasattr(e.category, "value")
                    else str(e.category)
                )
                eorigin = getattr(e, "origin", "Creation")
            else:
                ename = str(e)
                if ename in EDGES:
                    ecat = EDGES[ename].category.value
                else:
                    ecat = "Background"
                eorigin = "Creation"
            ET.SubElement(edges, "Edge", name=ename, category=ecat, origin=eorigin)

    @classmethod
    def _build_derived_stats(cls, root: ET.Element, character: Character) -> None:
        """Construct the <DerivedStats> XML section."""
        derived = ET.SubElement(root, "DerivedStats")

        pace_res = DerivedStatsCalculator.calculate_pace(character)
        ET.SubElement(derived, "Pace").text = str(pace_res.pace)
        ET.SubElement(derived, "RunningDie").text = str(pace_res.running_die)

        parry_bonus = sum(
            int(getattr(item, "parry_bonus", 0) or 0)
            for item in character.inventory
            if getattr(item, "is_equipped", False)
        )
        parry_val = DerivedStatsCalculator.calculate_parry(
            character, parry_bonus=parry_bonus
        )
        ET.SubElement(derived, "Parry").text = str(parry_val)

        armor_val = sum(
            int(getattr(item, "armor_bonus", 0) or 0)
            for item in character.inventory
            if getattr(item, "is_equipped", False)
        )
        toughness_res = DerivedStatsCalculator.calculate_toughness(
            character, torso_armor=armor_val
        )
        ET.SubElement(
            derived,
            "Toughness",
            total=str(toughness_res.total),
            base=str(toughness_res.base),
            armor=str(toughness_res.armor),
        )

        load_limit = DerivedStatsCalculator.calculate_load_limit(character)
        ll_text = (
            str(int(load_limit))
            if load_limit == int(load_limit)
            else f"{load_limit:g}"
        )
        load_elem = ET.SubElement(derived, "LoadLimit", unit="lbs")
        load_elem.text = ll_text

        carried_weight = EncumbranceCalculator.calculate_carried_weight(
            character.inventory
        )
        cw_text = (
            str(int(carried_weight))
            if carried_weight == int(carried_weight)
            else f"{carried_weight:g}"
        )
        cw_elem = ET.SubElement(derived, "CarriedWeight", unit="lbs")
        cw_elem.text = cw_text

        enc_res = EncumbranceCalculator.calculate_encumbrance_penalty(
            load_limit, carried_weight
        )
        ET.SubElement(derived, "EncumbrancePenalty").text = str(enc_res.penalty)

    @classmethod
    def _build_arcana(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Arcana> XML section."""
        arcana_elem = ET.SubElement(root, "Arcana")
        arcana = getattr(character, "arcana", None)
        bg = getattr(arcana, "background", "None") if arcana else "None"
        if hasattr(bg, "value"):
            bg = bg.value
        bg_str = str(bg)

        if not arcana or bg_str.lower() == "none":
            ET.SubElement(arcana_elem, "Background", name="None")
        else:
            ET.SubElement(arcana_elem, "Background", name=bg_str)
            ET.SubElement(arcana_elem, "PowerPoints").text = str(
                getattr(arcana, "power_points", 0)
            )
            powers_elem = ET.SubElement(arcana_elem, "Powers")
            for p in getattr(arcana, "powers", []):
                ptrap = getattr(p, "trappings", getattr(p, "trapping", ""))
                p_attrs: dict[str, str] = {"name": p.name}
                if ptrap:
                    p_attrs["trappings"] = str(ptrap)
                pp_val = getattr(p, "power_points", None)
                if pp_val is not None:
                    p_attrs["power_points"] = str(pp_val)
                dmg = getattr(p, "damage", "")
                if dmg:
                    p_attrs["damage"] = str(dmg)
                rng = getattr(p, "range", "")
                if rng:
                    p_attrs["range"] = str(rng)
                dur = getattr(p, "duration", "")
                if dur:
                    p_attrs["duration"] = str(dur)
                ET.SubElement(powers_elem, "Power", **p_attrs)

    @classmethod
    def _build_inventory(cls, root: ET.Element, character: Character) -> None:
        """Construct the <Inventory> XML section."""
        inv_elem = ET.SubElement(root, "Inventory")
        for item in character.inventory:
            item_elem = ET.SubElement(inv_elem, "Item")
            iname = getattr(item, "name", "")
            icat = getattr(item, "category", "Adventuring Gear")
            if hasattr(icat, "value"):
                icat = icat.value

            ET.SubElement(item_elem, "Name").text = iname
            ET.SubElement(item_elem, "Category").text = str(icat)

            w = float(getattr(item, "weight", 0.0))
            c = float(getattr(item, "cost", 0.0))
            w_str = f"{w:.1f}" if f"{w:.1f}".endswith(".0") or len(str(w).split(".")[-1]) == 1 else f"{w:g}"
            c_str = f"{c:.1f}" if f"{c:.1f}".endswith(".0") or len(str(c).split(".")[-1]) == 1 else f"{c:g}"

            ET.SubElement(item_elem, "Weight").text = w_str
            ET.SubElement(item_elem, "Cost").text = c_str
            ET.SubElement(item_elem, "Quantity").text = str(
                getattr(item, "quantity", 1)
            )

            is_eq = getattr(item, "is_equipped", False)
            ET.SubElement(item_elem, "Equipped").text = "true" if is_eq else "false"

            dmg = getattr(item, "damage", None)
            if dmg:
                ET.SubElement(item_elem, "Damage").text = str(dmg)

            rng = getattr(item, "range", None)
            if rng:
                ET.SubElement(item_elem, "Range").text = str(rng)

            mstr = getattr(item, "min_str", None)
            if mstr:
                ET.SubElement(item_elem, "MinStr").text = str(mstr)

            ab = getattr(item, "armor_bonus", 0)
            if ab:
                ET.SubElement(item_elem, "ArmorBonus").text = str(ab)

            pb = getattr(item, "parry_bonus", 0)
            if pb:
                ET.SubElement(item_elem, "ParryBonus").text = str(pb)

            notes = getattr(item, "notes", "")
            if notes:
                ET.SubElement(item_elem, "Notes").text = str(notes)


__all__ = [
    "XmlSerializationError",
    "XmlSyntaxError",
    "XmlValidationError",
    "CharacterXmlSerializer",
]
