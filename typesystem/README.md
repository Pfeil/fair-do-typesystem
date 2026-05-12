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

# Validate all type system files (verbose mode - shows all steps)
uv run fdo-validate
uv run python validate.py

# Validate in quiet mode (only warnings and errors)
uv run fdo-validate --quiet
uv run python validate.py --quiet

# Validate a specific file (verbose)
uv run python validate.py core/0.FDO-Root.json

# Validate a specific file (quiet)
uv run python validate.py core/0.FDO-Root.json --quiet

# Validate multiple specific files
uv run python validate.py core/0.FDO-Root.json core/0.FDO-ProfileDef.json
uv run python validate.py core/*.json  # Shell glob expansion

# Run from parent directory
cd ..
uv run --directory scripts fdo-validate

## Testing

The validator includes a comprehensive test suite organized by module:

### Running Tests

```bash
cd typesystem/scripts

# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests for specific module
uv run pytest tests/test_models.py
uv run pytest tests/test_validation_logger.py
uv run pytest tests/test_registry.py

# Run tests with coverage report
uv run pytest --cov=. --cov-report=term-missing

# Run tests matching a pattern
uv run pytest -k "test_pid"  # Tests with "pid" in name
uv run pytest -k "TestPidRecord"  # All tests in TestPidRecord class
```

### Test Structure

Tests are organized to match the code structure:

```
typesystem/scripts/
├── models.py                    → tests/test_models.py
├── validation_logger.py         → tests/test_validation_logger.py
├── registry.py                  → tests/test_registry.py
├── assembly.py                  → tests/test_assembly.py (Phase 2)
├── validators.py                → tests/test_validators.py (Phase 3)
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_validation_logger.py
    ├── test_registry.py
    └── conftest.py              # Shared fixtures
```

### Writing Tests

Each test file corresponds to one module and uses pytest:

```python
"""Tests for my_module.py."""

import pytest
from my_module import MyClass


class TestMyClass:
    """Test MyClass functionality."""

    def test_something(self):
        """Test description."""
        obj = MyClass()
        assert obj.method() == expected
```

### Continuous Integration

Tests can be run automatically on commit or push using CI/CD pipelines.
The test structure supports parallel execution and selective testing.

### Command Line Options

| Argument | Short | Description |
|----------|-------|-------------|
| `[file.json ...]` | | One or more files to validate (default: all files) |
| `--quiet` | `-q` | Only show warnings and errors, hide successful validation steps |
| *(none)* | | Show detailed step-by-step validation process (default) |

**Examples:**
```bash
# Single file
python validate.py core/0.FDO-Root.json

# Multiple files
python validate.py core/0.FDO-Root.json core/0.FDO-ProfileDef.json

# Using shell glob
python validate.py core/*.json

# With quiet flag
python validate.py core/*.json --quiet
```

### Understanding the Validation Output

When running in verbose mode (default), the validator shows:

1. **Registry Loading**: Number of PID-to-path mappings loaded
2. **For each FDO file**:
   - File name and path
   - **Step 1**: Required attributes check (per the meta-profile)
   - **Step 2**: FDO type verification
   - **Step 3**: Attribute list validation
   - **Step 4**: Mandatory attributes presence check
   - **Step 5**: Attribute definition reference resolution
   - **Step 6**: Special checks (e.g., ProfileDef self-reference)
   - Final validity status
3. **Summary**: Overall validation result with error/warning counts

Example output for validating `0.FDO-ProfileDef.json`:
```
📋 Validating PROFILE: 0.FDO-ProfileDef.json
  Path: /path/to/core/0.FDO-ProfileDef.json

Step 1: Checking required attributes (per 0.FDO/ProfileDef):
    Checking required attributes:
        ✓ 0.FDO/Type: present
        ✓ 0.FDO/Profile: present
        ...

Step 6: Checking self-referential structure (ProfileDef special case):
      Profile references: ['0.FDO/ProfileDef']
      ✓ ProfileDef correctly references itself (bootstrapping)

✅ PROFILE VALID: 0.FDO-ProfileDef.json
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
