# FDO Type System - Local Development Representation

This directory contains a machine-readable, local representation of the FAIR Digital Objects (FDO) type system for development, testing, and validation algorithm prototyping.

## Purpose

- **Test validation algorithms** against realistic FDO type structures
- **Develop and refine** the type system before official registration
- **Experiment** with extensions and custom profiles
- **Document uncertainties** in the specification via sidecar markdown files

## Structure

```
typesystem/
├── registry.json              # Maps logical PIDs to local file paths
├── README.md                  # This file
│
├── core/                      # Foundational profiles (self-referential)
│   ├── 0.FDO-Root.json
│   ├── 0.FDO-ProfileDef.json
│   ├── 0.FDO-AttributeDef.json
│   └── 0.FDO-SyntaxDef.json
│
├── attributes/                # Attribute definitions (each is an FDO)
│   ├── mandatory/             # Required in every FDO
│   ├── profile-def/           # Used by ProfileDef profile
│   ├── attribute-def/         # Used by AttributeDef profile
│   └── syntax-def/            # Used by SyntaxDef profile
│
├── syntax/                    # Syntax definitions (each is an FDO)
│   ├── StringSyntax.json
│   ├── NumberSyntax.json
│   ├── IntegerSyntax.json
│   ├── BooleanSyntax.json
│   └── custom/                # Custom syntaxes (whitelists, regex patterns)
│
├── profiles/                  # Domain-specific profiles (extend as needed)
├── types/                     # FDO Type definitions (extend as needed)
├── instances/                 # Example FDO records for testing
└── scripts/                   # Validation and utility scripts
```

## File Format

Each JSON file represents **exactly what an FDO record would contain** when registered. No restructuring or convenience fields are added.

### Example: Profile Record

```json
{
  "0.FDO/Type": ["FDO_Profile"],
  "0.FDO/Profile": ["0.FDO/ProfileDef"],
  "0.FDO/Data": ["Not_Applicable"],
  "0.FDO/Name": [{"value": "Example Profile", "lang": "en"}],
  "0.FDO/Description": [{"value": "...", "lang": "en"}],
  "0.FDO/Attribute": [
    "0.FDO/Type",
    "0.FDO/Profile",
    "0.FDO/Data",
    "0.FDO/Name",
    "0.FDO/Creator"
  ]
}
```

**Key points:**
- `0.FDO/Attribute` contains **only PIDs** of attribute definitions
- Cardinality lives in the **attribute definition**, not the profile
- All files validate against their respective meta-profiles

## Reference Resolution

Use `registry.json` to resolve logical PIDs to local file paths:

```python
import json

with open('registry.json') as f:
    registry = json.load(f)

# Resolve a PID to a local path
pid = "0.FDO/Type"
local_path = registry['entries'][pid]  # → "attributes/mandatory/0.FDO-Type.json"
```

## Validation

A basic validator script is provided in `scripts/validate.py`. Run it to check that all type system files are structurally valid:

```bash
cd typesystem
python scripts/validate.py
```

## Known Uncertainties

Some aspects of the specification are not fully defined. These are documented in sidecar `.md` files next to the affected JSON files:

| File | Uncertainty |
|------|-------------|
| `attributes/profile-def/0.FDO-Name.md` | Localized value structure |
| `attributes/profile-def/0.FDO-Description.md` | Localized value structure |
| `attributes/syntax-def/0.FDO-NumericInterval.md` | Interval format |

## Extending the Type System

### Adding a New Profile

1. Create a new JSON file in `profiles/` or a subdirectory
2. Include all required attributes per `0.FDO/ProfileDef`
3. Reference attribute definitions by their logical PID or local path
4. Optionally extend an existing profile via `0.FDO/Extends`

### Adding a New Attribute Definition

1. Create a new JSON file in `attributes/` or a subdirectory
2. Include all required attributes per `0.FDO/AttributeDef`
3. Reference a syntax definition in `0.FDO/DataType`
4. Specify cardinality as a string matching the cardinality regex

### Adding a New Syntax Definition

1. Create a new JSON file in `syntax/` or a subdirectory
2. Include all required attributes per `0.FDO/SyntaxDef`
3. Specify `0.FDO/PrimitiveDataType` (required)
4. Optionally add constraints via Regex, NumericInterval, Whitelist, or Blacklist

## Registration Workflow

When ready to register types with an official registry:

1. Keep the `pid` field as your logical identifier (e.g., `"0.FDO/Type"`)
2. Add/update a `registeredPid` field with the assigned PID (e.g., `"hdl:21.11111/0.FDO.Type"`)
3. Update `registry.json` to map both logical and registered PIDs
4. Your validation code should work with both

## Installation & Usage

### Quick Reference

```bash
# First-time setup
cd typesystem/scripts
uv sync

# Validate all type system files
uv run fdo-validate
uv run python validate.py

# Validate a specific file
uv run python validate.py core/0.FDO-Root.json

# Run from parent directory
cd ..
uv run --directory scripts fdo-validate

# Run tests (when available)
uv run pytest
```

### Using uv (Recommended)

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, reliable Python dependency management.

**1. Install uv** (if you haven't already):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Navigate to the scripts directory and install:**
```bash
cd typesystem/scripts
uv sync
```

**3. Run the validator:**
```bash
# Using the installed command
fdo-validate

# Or directly with uv
uv run fdo-validate

# Or run the script directly
uv run python validate.py
```

**4. Validate a specific file:**
```bash
uv run python validate.py ../core/0.FDO-Root.json
```

**5. Run tests (future):**
```bash
uv run pytest
```

### Using Python Directly

If you prefer not to use uv:

```bash
cd typesystem
python scripts/validate.py
```

## Scripts

| Script | Purpose | Command |
|--------|---------|----------||
| `validate.py` | Validates all type system files against their meta-profiles | `fdo-validate` or `uv run python validate.py` |
| `generate-examples.py` | Generates example FDO records for testing | _TODO_ |

## References

- Official FDO Specification: `/sections/` directory
- R10-1 to R10-15: FDO Types specification
- R3-1 to R3-5: FDO Record requirements
- R4-1 to R4-12: FDO Profile requirements
- R5-1 to R5-15: FDO Attribute requirements
- R6-1 to R6-6: FDO Syntax Definition requirements
