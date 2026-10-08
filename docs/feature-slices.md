# Savage Worlds Character Generator — Vertical Feature Slices

This document defines the vertical feature slices for the implementation of the Savage Worlds Character Generator application. Work will proceed slice-by-slice under strict Test-Driven Development (TDD).

---

## Slice Overview & Dependency Order

```
[Slice 1: Core Models & Derived Combat Stats]
                      │
                      ▼
[Slice 2: Point-Buy Economy & Prerequisite Rules]
                      │
                      ▼
[Slice 3: SQLite Database, Item Catalog & Inventory]
                      │
                      ▼
[Slice 4: XML Serialization Engine (Import/Export)]
                      │
                      ▼
[Slice 5: Desktop GUI & End-to-End Character Builder]
```

---

## Slice 1: Core Domain Models, Dice Engine & Derived Combat Statistics

* **Description**: Foundational domain primitives, stepped polyhedral dice (`d4` through `d12`), 10 SWADE ancestries (Human, Android, Aquarian, Avion, Dwarf, Elf, Half-Elf, Half-Folk, Rakashan, Saurian), 5 core attributes, skills, hindrances, edges, and the mathematical engine for derived statistics.
* **Acceptance Criteria**:
  * Accurate representation of stepped dice and trait scaling.
  * Correct calculation of Pace (base 6, Dwarf/Half-Folk 5, Avion flight 12 / ground 5).
  * Correct calculation of Running die (base d6, reduced d4 for Dwarf/Half-Folk/Avion).
  * Parry accurately calculated as $2 + \lfloor \text{Fighting die} / 2 \rfloor$ (and 2 if untrained).
  * Toughness accurately calculated as $2 + \lfloor \text{Vigor die} / 2 \rfloor + \text{Armor} + \text{Size modifier}$.
  * Base Bennies set to 3 (or 4 for Half-Folk *Luck*).
  * Load Limit accurately calculated as $\text{Strength die} \times 5\text{ lbs}$ (or $\times 8\text{ lbs}$ for *Brawny*).
* **Components Touched**:
  * `swchar/core/dice.py`
  * `swchar/core/constants.py`
  * `swchar/models/ancestry.py`
  * `swchar/models/attributes.py`
  * `swchar/models/skills.py`
  * `swchar/models/character.py`
  * `swchar/rules/derived_stats.py`
  * `tests/test_models.py`
  * `tests/test_derived_stats.py`

---

## Slice 2: Point-Buy Economy & Prerequisite Validation Engine

* **Description**: Point budget validation and hindrance disadvantage economy, plus edge prerequisite checking.
* **Acceptance Criteria**:
  * Tracks 5 base attribute points, respecting standard creation limits (d12 maximum unless ancestral bonus raises starting to d6).
  * Tracks 5 core skills (Athletics, Common Knowledge, Notice, Persuasion, Stealth) starting at d4 for 0 points.
  * Tracks 12 skill points: 1 pt per die step up to linked attribute; 2 pts per die step above linked attribute.
  * Hindrance points capped at 4 points of mechanical reward (Major = 2, Minor = 1).
  * Point redemption accurately credits attribute points (2 pts), extra novice edges (2 pts), skill points (1 pt), or starting cash (+100% / +$500 per 1 pt).
  * Edge prerequisites correctly evaluated against character traits, rank, and other edges.
* **Components Touched**:
  * `swchar/models/hindrances.py`
  * `swchar/models/edges.py`
  * `swchar/rules/point_tracker.py`
  * `swchar/rules/prerequisites.py`
  * `tests/test_point_tracker.py`
  * `tests/test_prerequisites.py`

---

## Slice 3: SQLite Database, Item Catalog & Inventory Persistence

* **Description**: Local SQLite database storage maintaining standard SWADE equipment catalog (weapons, armor, adventuring gear, ammo) and personal character inventory with encumbrance calculations.
* **Acceptance Criteria**:
  * Initializes `swchar.db` with DDL tables (`catalog_items`, `characters`, `character_inventory`).
  * Seeds database with canonical SWADE weapons, armor, and gear items.
  * Provides repository methods to query, filter by category, and search catalog items.
  * Persists character inventory items with quantity and equipped state.
  * Computes total carried weight, compares to Load Limit, and calculates encumbrance penalties (0, -1, -2, -3, immobilized).
  * Flags Minimum Strength (Min Str) deficiencies for weapons and armor.
* **Components Touched**:
  * `swchar/db/connection.py`
  * `swchar/db/schema.py`
  * `swchar/db/catalog_seed.py`
  * `swchar/db/repository.py`
  * `swchar/rules/encumbrance.py`
  * `tests/test_database.py`
  * `tests/test_encumbrance.py`

---

## Slice 4: XML Serialization Engine (Import & Export)

* **Description**: Canonical XML serialization and deserialization for Savage Worlds characters.
* **Acceptance Criteria**:
  * Serializes complete Character instance into well-formatted, schema-compliant XML.
  * Captures identity, attributes, skills, hindrances, edges, arcana, derived stats, cash, and inventory items.
  * Deserializes valid XML back into a fully formed Character object with complete fidelity.
  * Emits informative errors for malformed or invalid XML structures.
* **Components Touched**:
  * `swchar/io/xml_serializer.py`
  * `swchar/io/xml_deserializer.py`
  * `tests/test_xml_io.py`

---

## Slice 5: Desktop GUI & End-to-End Character Builder

* **Description**: Native Tkinter/ttk desktop GUI unifying all layers into an interactive character builder.
* **Acceptance Criteria**:
  * Launches cleanly as a responsive desktop application.
  * Tab 1: Concept & Ancestry with instant ancestral trait feedback.
  * Tab 2: Attributes & Skills with live point budget counters and linked attribute visual indicators.
  * Tab 3: Hindrances & Edges with budget redemption and prerequisite checking.
  * Tab 4: Arcana & Powers for characters with Arcane Backgrounds.
  * Tab 5: Inventory manager connected to SQLite database (browser, add/remove, equip toggle, live encumbrance bar, cash tracker).
  * Tab 6: Character Sheet Summary displaying full combat profile, XML Import and Export buttons with file dialogs.
  * Complete end-to-end integration test confirming that a character can be created, saved to database, exported to XML, and reloaded.
* **Components Touched**:
  * `swchar/ui/main_window.py`
  * `swchar/ui/theme.py`
  * `swchar/ui/tabs/*.py`
  * `swchar/app.py`
  * `tests/test_app_integration.py`
