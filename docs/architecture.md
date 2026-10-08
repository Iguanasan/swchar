# Savage Worlds Character Generator — Architecture Specification

## 1. Executive Overview

The **Savage Worlds Character Generator** (`swchar`) is a Python desktop application designed to build, validate, equip, and serialize player characters (Wild Cards) according to the rules of *Savage Worlds Adventure Edition* (SWADE). 

The system provides:
1. A **rule-enforcing domain engine** managing attribute/skill point economies, hindrance-reward conversions, edge prerequisites, and derived combat statistics.
2. A **local SQLite database** holding master equipment catalogs and persistent character inventories.
3. An **XML Import/Export engine** enabling portable, human-readable character serialization.
4. A **responsive desktop GUI** built with Python's native `tkinter` / `ttk` library.

---

## 2. Technology Stack & Rationale

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Runtime** | Python 3.11+ | Modern typing support, dataclasses, pattern matching, broad ecosystem support. |
| **Desktop GUI** | `tkinter` + `ttk` | Built into the Python standard library. Zero external binary compilation or DLL issues on Windows, instant startup, platform-native look and feel, and lightweight resource usage. |
| **Database** | `sqlite3` | Standard library, zero-configuration local relational database. Perfect for equipment catalogs, transaction safety, and querying inventory items. |
| **XML Serialization** | `xml.etree.ElementTree` | Standard library, fast, compliant XML generation and parsing with schema conformance. |
| **Testing** | `pytest` | Industry-standard test runner with rich assertion introspection and fixture management, supporting our TDD workflow. |

---

## 3. Directory & Module Structure

```
swchar/
│
├── docs/
│   ├── architecture.md           # This document
│   └── feature-slices.md         # Vertical slice implementation plan
│
├── swchar/
│   ├── __init__.py
│   ├── app.py                    # Application launcher and controller
│   │
│   ├── core/                     # Foundational primitives
│   │   ├── __init__.py
│   │   ├── dice.py               # DieType enum (D4, D6, D8, D10, D12, D12_PLUS)
│   │   └── constants.py          # SWADE constants (base points, cash, rank thresholds)
│   │
│   ├── models/                   # Pure domain models (data structures)
│   │   ├── __init__.py
│   │   ├── ancestry.py           # Ancestry definitions and racial modifiers
│   │   ├── attributes.py         # Attribute set (Agility, Smarts, Spirit, Strength, Vigor)
│   │   ├── skills.py             # Skill definition and character skill allocations
│   │   ├── hindrances.py         # Hindrance definitions (Minor/Major) and selections
│   │   ├── edges.py              # Edge definitions, requirements, and selections
│   │   ├── arcana.py             # Arcane backgrounds, powers, trappings, power points
│   │   ├── items.py              # Item catalog model and character inventory items
│   │   └── character.py          # Root Character Wild Card aggregate model
│   │
│   ├── rules/                    # Rules engine and validation logic
│   │   ├── __init__.py
│   │   ├── point_tracker.py      # Attribute, skill, and hindrance points accounting
│   │   ├── prerequisites.py      # Edge prerequisite validation against character traits
│   │   ├── derived_stats.py      # Calculations for Pace, Parry, Toughness, Bennies, Load Limit
│   │   └── encumbrance.py        # Carried weight vs. load limit, min str penalties
│   │
│   ├── db/                       # SQLite database layer
│   │   ├── __init__.py
│   │   ├── connection.py         # Connection manager and SQLite file path resolution
│   │   ├── schema.py             # DDL table creation and migration scripts
│   │   ├── catalog_seed.py       # Default SWADE items seed data (weapons, armor, gear)
│   │   └── repository.py         # Catalog item queries & character inventory persistence
│   │
│   ├── io/                       # Data serialization / interchange
│   │   ├── __init__.py
│   │   ├── xml_serializer.py     # Exports Character instance to formatted XML
│   │   └── xml_deserializer.py   # Parses XML into Character instance with validation
│   │
│   └── ui/                       # Desktop graphical interface
│       ├── __init__.py
│       ├── main_window.py        # Main application window, menu bar, status bar
│       ├── theme.py              # ttk styles, typography, and palette
│       └── tabs/
│           ├── __init__.py
│           ├── concept_tab.py    # Name, archetype, ancestry selection
│           ├── traits_tab.py     # Attributes and Skills point-buy controls with live budgets
│           ├── hindrances_edges_tab.py # Hindrance & Edge pickers with prerequisite hints
│           ├── arcana_tab.py     # Arcane background & power configuration
│           ├── inventory_tab.py  # SQLite item catalog browser, equip toggles, weight meter
│           └── summary_tab.py    # Complete character sheet overview & export triggers
│
├── tests/                        # Comprehensive test suite (TDD)
│   ├── __init__.py
│   ├── conftest.py               # Shared test fixtures (sample characters, in-memory DB)
│   ├── test_models.py
│   ├── test_rules.py
│   ├── test_database.py
│   ├── test_xml_io.py
│   └── test_ui_controllers.py
│
├── data/
│   └── swchar.db                 # Default local SQLite database file
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 4. Component Boundaries & Key Interfaces

The architecture follows a clean, decoupled **Layered Domain-Driven Design (DDD)** pattern:

```
      ┌─────────────────────────────────────────────────────────────┐
      │                        UI Layer                             │
      │   (MainWindow, ConceptTab, TraitsTab, InventoryTab, etc.)   │
      └──────────────┬───────────────────────────────┬──────────────┘
                     │                               │
                     ▼                               ▼
      ┌─────────────────────────────┐ ┌─────────────────────────────┐
      │         Rules Engine        │ │      XML I/O Subsystem      │
      │   (Budgets, Derived Stats,  │ │  (XmlSerializer,            │
      │    Prerequisites, Encumb)   │ │   XmlDeserializer)          │
      └──────────────┬──────────────┘ └──────────────┬──────────────┘
                     │                               │
                     ▼                               ▼
      ┌─────────────────────────────────────────────────────────────┐
      │                    Domain Model Layer                       │
      │   (Character, Attributes, Skills, Edges, InventoryItem)     │
      └──────────────────────────────┬──────────────────────────────┘
                                     │
                                     ▼
      ┌─────────────────────────────────────────────────────────────┐
      │                   Database / Persistence                    │
      │        (SQLite Repository, Item Catalog, Character Inv)     │
      └─────────────────────────────────────────────────────────────┘
```

### Key Interfaces

1. **`PointTracker`**:
   - `get_attribute_points_spent(character: Character) -> int` (target: 5 + bonus from hindrances)
   - `get_skill_points_spent(character: Character) -> int` (target: 12 + bonus from hindrances)
   - `get_hindrance_points_balance(character: Character) -> HindranceEconomy`
   - `validate_build(character: Character) -> list[str]` (returns validation warning/error messages)

2. **`DerivedStatsCalculator`**:
   - `calculate_pace(character: Character) -> tuple[int, DieType]` (Pace and Running Die)
   - `calculate_parry(character: Character) -> int` (2 + half Fighting die + shields/edges)
   - `calculate_toughness(character: Character) -> tuple[int, int]` (Base Toughness, Torso Armor)
   - `calculate_bennies(character: Character) -> int` (3 + racial/edge bonuses)
   - `calculate_load_limit(character: Character) -> float` (Strength die × 5 or 8)

3. **`InventoryRepository`**:
   - `list_catalog_items(category: str | None = None, query: str = "") -> list[CatalogItem]`
   - `get_catalog_item(item_id: int) -> CatalogItem | None`
   - `save_character_inventory(character_id: str, items: list[InventoryItem]) -> None`
   - `load_character_inventory(character_id: str) -> list[InventoryItem]`

4. **`CharacterXmlEngine`**:
   - `serialize(character: Character) -> str` (produces formatted XML document)
   - `deserialize(xml_content: str) -> Character` (constructs and validates character from XML)

---

## 5. Data Models & Storage Approach

### A. Domain Entities
* **`DieType`**: Enum representing `D4=4`, `D6=6`, `D8=8`, `D10=10`, `D12=12`, `D12_PLUS=14`.
* **`AttributeName`**: Enum (`AGILITY`, `SMARTS`, `SPIRIT`, `STRENGTH`, `VIGOR`).
* **`Skill`**: Name, linked attribute, core flag (True for the 5 core skills), die rating.
* **`Ancestry`**: Name, attribute bonuses, free edges, size, pace, running die, special abilities, liabilities.
* **`Hindrance`**: Name, severity (`MINOR` = 1 point, `MAJOR` = 2 points), description.
* **`Edge`**: Name, category (`BACKGROUND`, `COMBAT`, `LEADERSHIP`, `POWER`, `PROFESSIONAL`, `SOCIAL`, `WEIRD`), rank requirement (`NOVICE`), prerequisite lambda / specification, mechanical effects.
* **`InventoryItem`**: Catalog item reference, name, category, weight, cost, quantity, equipped (bool), weapon/armor stats (damage, armor value, min str).
* **`Character`**: Aggregate root containing ID, Name, Concept, Ancestry, Attributes, Skills, Hindrances, Edges, Arcane Background, Powers, Inventory, Cash, and calculated derived stats.

### B. SQLite Schema (`data/swchar.db`)
```sql
-- Catalog of items available in the game
CREATE TABLE IF NOT EXISTS catalog_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,          -- 'Melee Weapon', 'Ranged Weapon', 'Armor', 'Shield', 'Adventuring Gear', 'Ammo'
    cost REAL NOT NULL DEFAULT 0.0,
    weight REAL NOT NULL DEFAULT 0.0,
    min_str TEXT,                   -- e.g. 'd6'
    damage TEXT,                    -- e.g. 'Str+d6'
    range TEXT,                     -- e.g. '12/24/48'
    armor_bonus INTEGER DEFAULT 0,  -- e.g. 2 for leather armor
    parry_bonus INTEGER DEFAULT 0,  -- e.g. 1 for small shield
    notes TEXT
);

-- Persisted characters table
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    concept TEXT,
    ancestry TEXT NOT NULL,
    cash REAL NOT NULL DEFAULT 500.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inventory items linked to a character
CREATE TABLE IF NOT EXISTS character_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    catalog_item_id INTEGER,
    custom_name TEXT NOT NULL,
    category TEXT NOT NULL,
    cost REAL NOT NULL,
    weight REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    is_equipped BOOLEAN NOT NULL DEFAULT 0,
    min_str TEXT,
    damage TEXT,
    armor_bonus INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (catalog_item_id) REFERENCES catalog_items(id)
);
```

### C. XML Interchange Format Specification
Characters are exported to and imported from structured XML conforming to the following canonical format:

```xml
<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Id>uuid-here</Id>
    <Name>Valen Thorne</Name>
    <Concept>Bounty Hunter</Concept>
    <Ancestry>Human</Ancestry>
    <Rank>Novice</Rank>
    <Bennies>3</Bennies>
    <Cash currency="USD">350.00</Cash>
  </Identity>

  <Attributes>
    <Attribute name="Agility" die="d8"/>
    <Attribute name="Smarts" die="d6"/>
    <Attribute name="Spirit" die="d6"/>
    <Attribute name="Strength" die="d6"/>
    <Attribute name="Vigor" die="d6"/>
  </Attributes>

  <Skills>
    <Skill name="Athletics" attribute="Agility" die="d6" core="true"/>
    <Skill name="Common Knowledge" attribute="Smarts" die="d4" core="true"/>
    <Skill name="Notice" attribute="Smarts" die="d6" core="true"/>
    <Skill name="Persuasion" attribute="Spirit" die="d4" core="true"/>
    <Skill name="Stealth" attribute="Agility" die="d6" core="true"/>
    <Skill name="Fighting" attribute="Agility" die="d8" core="false"/>
    <Skill name="Shooting" attribute="Agility" die="d8" core="false"/>
  </Skills>

  <Hindrances>
    <Hindrance name="Cautious" type="Minor"/>
    <Hindrance name="Heroic" type="Major"/>
    <HindranceRewards>
      <AttributePointsBonus>1</AttributePointsBonus>
      <SkillPointsBonus>0</SkillPointsBonus>
      <ExtraEdgesBonus>0</ExtraEdgesBonus>
      <CashBonus>0</CashBonus>
    </HindranceRewards>
  </Hindrances>

  <Edges>
    <Edge name="Quick" category="Combat" origin="Creation"/>
    <Edge name="Alertness" category="Background" origin="Human_Adaptable"/>
  </Edges>

  <DerivedStats>
    <Pace>6</Pace>
    <RunningDie>d6</RunningDie>
    <Parry>6</Parry>
    <Toughness total="7" base="5" armor="2"/>
    <LoadLimit unit="lbs">30</LoadLimit>
    <CarriedWeight unit="lbs">22.5</CarriedWeight>
    <EncumbrancePenalty>0</EncumbrancePenalty>
  </DerivedStats>

  <Arcana>
    <Background name="None"/>
  </Arcana>

  <Inventory>
    <Item>
      <Name>Glock 9mm</Name>
      <Category>Ranged Weapon</Category>
      <Weight>3.0</Weight>
      <Cost>200.0</Cost>
      <Quantity>1</Quantity>
      <Equipped>true</Equipped>
      <Damage>2d6</Damage>
      <Range>12/24/48</Range>
      <MinStr>d4</MinStr>
      <Notes>AP 1, Semi-Auto</Notes>
    </Item>
    <Item>
      <Name>Leather Jacket</Name>
      <Category>Armor</Category>
      <Weight>5.0</Weight>
      <Cost>80.0</Cost>
      <Quantity>1</Quantity>
      <Equipped>true</Equipped>
      <ArmorBonus>1</ArmorBonus>
      <Notes>Covers Torso, Arms</Notes>
    </Item>
  </Inventory>
</SavageWorldsCharacter>
```

---

## 6. Testing Strategy & TDD Separation

Following the project guidelines:
* **Tester role**: Writes tests in `tests/` asserting domain rules, calculations, database persistence, XML serialization, and UI controller behavior before code implementation.
* **Coder role**: Implements production code in `swchar/` to make the failing tests pass without editing tests.
* **Continuous Test Suite Execution**: Validates that all features run cleanly via `pytest`.

---

## 7. Approval & Sign-Off Gate

This architecture document represents the definitive design blueprint for the project. In accordance with the project rules, implementation will begin only after explicit user approval.
