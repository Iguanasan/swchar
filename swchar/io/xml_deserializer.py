"""XML deserialization engine for Savage Worlds Adventure Edition characters."""

from pathlib import Path
from typing import Any
import uuid
import xml.etree.ElementTree as ET

from swchar.core.dice import DieType
from swchar.models.ancestry import get_ancestry
from swchar.models.arcana import Arcana, Power
from swchar.models.attributes import AttributeName
from swchar.models.character import Character
from swchar.models.edges import Rank
from swchar.models.hindrances import Hindrance, HindranceEconomy, HindranceSeverity
from swchar.models.items import InventoryItem
from swchar.models.skills import Skill
from swchar.io.xml_serializer import (
    XmlSerializationError,
    XmlSyntaxError,
    XmlValidationError,
)


class CharacterXmlDeserializer:
    """Deserializes Savage Worlds Wild Card characters from XML documents."""

    @classmethod
    def from_xml_string(cls, xml_text: str) -> Character:
        """Parse an XML string and reconstruct a fully-populated Character domain instance.

        Args:
            xml_text: XML string representation of a character.

        Returns:
            Character instance with complete fidelity.

        Raises:
            XmlSyntaxError: If XML syntax is malformed or empty.
            XmlValidationError: If schema, structure, or trait constraints are violated.
        """
        if not xml_text or not xml_text.strip():
            raise XmlSyntaxError("XML string cannot be empty or whitespace only.")

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as err:
            raise XmlSyntaxError(f"Malformed XML syntax: {err}") from err

        if root.tag != "SavageWorldsCharacter":
            raise XmlValidationError(
                f"Invalid root element: expected <SavageWorldsCharacter>, got <{root.tag}>."
            )

        char = cls._parse_identity(root)
        cls._parse_attributes(root, char)
        cls._parse_skills(root, char)
        cls._parse_hindrances(root, char)
        cls._parse_edges(root, char)
        cls._parse_arcana(root, char)
        cls._parse_inventory(root, char)

        return char

    @classmethod
    def import_from_file(cls, file_path: Path | str) -> Character:
        """Read XML from file and deserialize into a Character instance.

        Args:
            file_path: Path to the XML file.

        Returns:
            Reconstructed Character domain instance.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            XmlSerializationError: If deserialization fails.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        content = path.read_text(encoding="utf-8")
        return cls.from_xml_string(content)

    from_xml_file = import_from_file

    @classmethod
    def _parse_identity(cls, root: ET.Element) -> Character:
        """Validate and parse the <Identity> block into a Character instance."""
        ident = root.find("Identity")
        if ident is None:
            raise XmlValidationError("Missing required <Identity> section.")

        ancestry_elem = ident.find("Ancestry")
        if ancestry_elem is None or not ancestry_elem.text or not ancestry_elem.text.strip():
            raise XmlValidationError("Missing required <Ancestry> element in <Identity>.")

        ancestry_name = ancestry_elem.text.strip()
        try:
            ancestry = get_ancestry(ancestry_name)
        except KeyError as err:
            raise XmlValidationError(f"Unknown ancestry: '{ancestry_name}'.") from err

        char_id = ident.findtext("Id")
        name = ident.findtext("Name") or ""
        concept = ident.findtext("Concept") or ""

        rank_text = ident.findtext("Rank") or "Novice"
        rank = Rank.NOVICE
        for r in Rank:
            if r.value.lower() == rank_text.strip().lower() or r.name.lower() == rank_text.strip().lower():
                rank = r
                break

        bennies: int | None = None
        bennies_text = ident.findtext("Bennies")
        if bennies_text is not None and bennies_text.strip():
            try:
                bennies = int(bennies_text.strip())
            except ValueError as err:
                raise XmlValidationError(f"Invalid Bennies value: {bennies_text}") from err

        cash = 500.0
        cash_elem = ident.find("Cash")
        if cash_elem is not None and cash_elem.text and cash_elem.text.strip():
            try:
                cash = float(cash_elem.text.strip())
            except ValueError as err:
                raise XmlValidationError(f"Invalid Cash value: {cash_elem.text}") from err

        return Character(
            id=char_id if char_id else str(uuid.uuid4()),
            name=name,
            concept=concept,
            ancestry=ancestry,
            rank=rank,
            bennies=bennies,
            cash=cash,
        )

    @classmethod
    def _parse_attributes(cls, root: ET.Element, char: Character) -> None:
        """Validate and parse the <Attributes> block."""
        attrs_elem = root.find("Attributes")
        if attrs_elem is None:
            raise XmlValidationError("Missing required <Attributes> section.")

        for attr_elem in attrs_elem.findall("Attribute"):
            aname = attr_elem.attrib.get("name")
            adie = attr_elem.attrib.get("die")
            if not aname or not adie:
                raise XmlValidationError(
                    "Each <Attribute> must specify 'name' and 'die' attributes."
                )

            try:
                die = DieType.from_string(adie)
            except ValueError as err:
                raise XmlValidationError(
                    f"Invalid die rating '{adie}' for attribute '{aname}': {err}"
                ) from err

            norm_name = aname.strip().lower()
            if norm_name == "agility":
                char.attributes.agility = die
            elif norm_name == "smarts":
                char.attributes.smarts = die
            elif norm_name == "spirit":
                char.attributes.spirit = die
            elif norm_name == "strength":
                char.attributes.strength = die
            elif norm_name == "vigor":
                char.attributes.vigor = die
            else:
                raise XmlValidationError(f"Unknown attribute name: '{aname}'.")

    @classmethod
    def _parse_skills(cls, root: ET.Element, char: Character) -> None:
        """Validate and parse the <Skills> block."""
        skills_elem = root.find("Skills")
        if skills_elem is not None:
            char.skills.clear()
            for s_elem in skills_elem.findall("Skill"):
                sname = s_elem.attrib.get("name")
                adie = s_elem.attrib.get("die")
                aattr = s_elem.attrib.get("attribute")
                acore = s_elem.attrib.get("core", "false")
                if not sname or not adie or not aattr:
                    raise XmlValidationError(
                        "Each <Skill> must specify 'name', 'attribute', and 'die'."
                    )

                try:
                    die = DieType.from_string(adie)
                except ValueError as err:
                    raise XmlValidationError(
                        f"Invalid die rating '{adie}' for skill '{sname}': {err}"
                    ) from err

                attr_enum: AttributeName | None = None
                for a in AttributeName:
                    if a.value.lower() == aattr.strip().lower() or a.name.lower() == aattr.strip().lower():
                        attr_enum = a
                        break
                if attr_enum is None:
                    raise XmlValidationError(
                        f"Unknown attribute '{aattr}' for skill '{sname}'."
                    )

                core = acore.strip().lower() in ("true", "1")
                char.skills[sname] = Skill(
                    name=sname,
                    attribute=attr_enum,
                    die=die,
                    core=core,
                )

    @classmethod
    def _parse_hindrances(cls, root: ET.Element, char: Character) -> None:
        """Validate and parse the <Hindrances> block and <HindranceRewards>."""
        hindrances_elem = root.find("Hindrances")
        if hindrances_elem is not None:
            char.hindrances.clear()
            for h_elem in hindrances_elem.findall("Hindrance"):
                hname = h_elem.attrib.get("name")
                htype = h_elem.attrib.get("type", "Minor")
                if not hname:
                    raise XmlValidationError("<Hindrance> missing 'name' attribute.")
                sev = (
                    HindranceSeverity.MAJOR
                    if htype.strip().lower() == "major"
                    else HindranceSeverity.MINOR
                )
                char.hindrances.append(Hindrance(name=hname, severity=sev))

            rewards_elem = hindrances_elem.find("HindranceRewards")
            if rewards_elem is not None:
                try:
                    attr_b = int(float(rewards_elem.findtext("AttributePointsBonus") or "0"))
                    skill_b = int(float(rewards_elem.findtext("SkillPointsBonus") or "0"))
                    edge_b = int(float(rewards_elem.findtext("ExtraEdgesBonus") or "0"))
                    raw_cash = float(rewards_elem.findtext("CashBonus") or "0")
                    cash_b = int(raw_cash // 500) if raw_cash >= 500 else int(raw_cash)
                except ValueError as err:
                    raise XmlValidationError(
                        f"Invalid numeric value in <HindranceRewards>: {err}"
                    ) from err

                char.hindrance_rewards = HindranceEconomy(
                    attribute_bonuses=attr_b,
                    skill_bonuses=skill_b,
                    edge_bonuses=edge_b,
                    cash_bonuses=cash_b,
                )

    @classmethod
    def _parse_edges(cls, root: ET.Element, char: Character) -> None:
        """Validate and parse the <Edges> block."""
        edges_elem = root.find("Edges")
        if edges_elem is not None:
            char.edges.clear()
            for e_elem in edges_elem.findall("Edge"):
                ename = e_elem.attrib.get("name")
                if not ename:
                    raise XmlValidationError("<Edge> missing 'name' attribute.")
                char.edges.append(ename)

    @classmethod
    def _parse_arcana(cls, root: ET.Element, char: Character) -> None:
        """Validate and parse the <Arcana> block."""
        arcana_elem = root.find("Arcana")
        if arcana_elem is not None:
            bg_elem = arcana_elem.find("Background")
            bg_name = bg_elem.attrib.get("name") if bg_elem is not None else "None"
            if not bg_name or bg_name.strip().lower() == "none":
                char.arcana = None
            else:
                pp_text = arcana_elem.findtext("PowerPoints") or "0"
                try:
                    pp = int(pp_text.strip())
                except ValueError as err:
                    raise XmlValidationError(
                        f"Invalid PowerPoints value: {pp_text}"
                    ) from err

                powers: list[Power] = []
                powers_elem = arcana_elem.find("Powers")
                if powers_elem is not None:
                    for p_elem in powers_elem.findall("Power"):
                        pname = p_elem.attrib.get("name")
                        if not pname:
                            continue
                        ptrap = (
                            p_elem.attrib.get("trappings")
                            or p_elem.attrib.get("trapping")
                            or p_elem.findtext("Trappings")
                            or (p_elem.text or "")
                        )
                        pp_str = (
                            p_elem.attrib.get("power_points")
                            or p_elem.attrib.get("powerpoints")
                            or p_elem.findtext("PowerPoints")
                            or "1"
                        )
                        try:
                            pp_val = int(pp_str.strip())
                        except ValueError:
                            pp_val = 1
                        dmg = p_elem.attrib.get("damage") or p_elem.findtext("Damage") or ""
                        rng = p_elem.attrib.get("range") or p_elem.findtext("Range") or ""
                        dur = p_elem.attrib.get("duration") or p_elem.findtext("Duration") or ""
                        powers.append(
                            Power(
                                name=pname,
                                power_points=pp_val,
                                trappings=ptrap.strip(),
                                damage=dmg,
                                range=rng,
                                duration=dur,
                            )
                        )

                char.arcana = Arcana(
                    background=bg_name.strip(), power_points=pp, powers=powers
                )

    @classmethod
    def _parse_inventory(cls, root: ET.Element, char: Character) -> None:
        """Validate and parse the <Inventory> block."""
        inv_elem = root.find("Inventory")
        if inv_elem is not None:
            char.inventory.clear()
            for item_elem in inv_elem.findall("Item"):
                iname = item_elem.findtext("Name") or ""
                icat = item_elem.findtext("Category") or "Adventuring Gear"

                w_text = item_elem.findtext("Weight") or "0"
                c_text = item_elem.findtext("Cost") or "0"
                q_text = item_elem.findtext("Quantity") or "1"
                try:
                    weight = float(w_text.strip())
                    cost = float(c_text.strip())
                    qty = int(q_text.strip())
                except ValueError as err:
                    raise XmlValidationError(
                        f"Invalid numeric value in inventory item '{iname}': {err}"
                    ) from err

                eq_text = item_elem.findtext("Equipped") or "false"
                equipped = eq_text.strip().lower() in ("true", "1")

                damage = item_elem.findtext("Damage")
                range_val = item_elem.findtext("Range")
                min_str = item_elem.findtext("MinStr")
                notes = item_elem.findtext("Notes") or ""

                ab_text = item_elem.findtext("ArmorBonus") or "0"
                pb_text = item_elem.findtext("ParryBonus") or "0"
                try:
                    armor_bonus = int(ab_text.strip())
                    parry_bonus = int(pb_text.strip())
                except ValueError as err:
                    raise XmlValidationError(
                        f"Invalid armor/parry bonus value in item '{iname}': {err}"
                    ) from err

                item = InventoryItem(
                    name=iname,
                    custom_name=iname,
                    category=icat,
                    cost=cost,
                    weight=weight,
                    quantity=qty,
                    is_equipped=equipped,
                    damage=damage,
                    range=range_val,
                    min_str=min_str,
                    armor_bonus=armor_bonus,
                    parry_bonus=parry_bonus,
                    notes=notes,
                )
                char.inventory.append(item)


__all__ = [
    "XmlSerializationError",
    "XmlSyntaxError",
    "XmlValidationError",
    "CharacterXmlDeserializer",
]
