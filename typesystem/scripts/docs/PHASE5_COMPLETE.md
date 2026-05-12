# Phase 5: Attribute Validation - COMPLETE ✅

**Date**: 2025-01-12  
**Status**: All components implemented and tested

## Completed Components

### 1. `validators.py` - AttributeValidator (~250 lines added)
Comprehensive attribute value validation:
- ✅ `AttributeValidator` class (fully implemented)
- ✅ Uses `AttributeAssembly` for rule gathering
- ✅ Cardinality validation (1, 0..1, 1..*, 0..*, 2..3, etc.)
- ✅ Primitive type validation (string, number, integer, boolean)
- ✅ Regex pattern matching (ECMA-262 compatible)
- ✅ Numeric interval checking (min/max bounds)
- ✅ Whitelist enforcement
- ✅ Blacklist enforcement
- ✅ Metadata attribute filtering (Type, Profile, Data skipped)
- ✅ Detailed validation logging

### 2. Test Suite (`tests/test_attribute_validation.py`) (~300 lines for Phase 5 tests)
Tests for attribute validation organized in six classes:
- ✅ `TestAttributeValidator` - Core validation tests (3 tests)
- ✅ `TestCardinalityValidation` - Cardinality-specific tests (6 tests)
- ✅ `TestTypeValidation` - Type checking tests (5 tests)
- ✅ `TestRegexValidation` - Pattern matching tests (3 tests)
- ✅ `TestNumericIntervalValidation` - Interval checking tests (4 tests)
- ✅ `TestWhitelistBlacklistValidation` - List validation tests (3 tests)
- ✅ `TestIntegration` - Integration with real type system (3 tests)
- ✅ All 27 tests passing

## File Structure Update

```
typesystem/scripts/
├── validators.py                   ✅ Phase 3 + Phase 5 additions
├── assembly.py                     ✅ Phase 2 + Phase 4
├── models.py                       ✅ Phase 1
├── validation_logger.py            ✅ Phase 1
├── registry.py                     ✅ Phase 1
└── tests/
    ├── test_models.py              ✅ Phase 1 (19 tests)
    ├── test_validation_logger.py   ✅ Phase 1 (11 tests)
    ├── test_registry.py            ✅ Phase 1 (9 tests)
    ├── test_assembly.py            ✅ Phase 2 (18 tests)
    ├── test_validators.py          ✅ Phase 3 (26 tests)
    └── test_attribute_validation.py ✅ Phase 4+5 tests (33 tests total)
```

## Key Features Implemented

### 1. Complete Attribute Validation

The `AttributeValidator.validate()` method validates all attributes in a record:

```python
logger = ValidationLogger(verbose=True)
registry = PidRegistry(logger)
assembly = AttributeAssembly(registry, logger)
validator = AttributeValidator(registry, logger, assembly)

record = PidRecord(
    pid="test/Record",
    data={
        "0.FDO/Name": [{"value": "Test", "lang": "en"}],
        "0.FDO/Description": [{"value": "Desc", "lang": "en"}],
    },
    source_pid="test/Record",
)

result = validator.validate(record, "test/Record")
print(f"Attributes checked: {result.attributes_checked}")
print(f"Errors: {len(result.errors)}")
```

### 2. Cardinality Validation

Supports all cardinality formats from the specification:

```python
# "1" - exactly one (mandatory)
_check_cardinality(1, "1", "attr", result)  # ✓ Valid
_check_cardinality(0, "1", "attr", result)  # ✗ Error: expected at least 1

# "0..1" - zero or one (optional)
_check_cardinality(0, "0..1", "attr", result)  # ✓ Valid
_check_cardinality(1, "0..1", "attr", result)  # ✓ Valid
_check_cardinality(2, "0..1", "attr", result)  # ✗ Error: expected at most 1

# "1..*" - one or more (mandatory, repeatable)
_check_cardinality(1, "1..*", "attr", result)  # ✓ Valid
_check_cardinality(5, "1..*", "attr", result)  # ✓ Valid
_check_cardinality(0, "1..*", "attr", result)  # ✗ Error: expected at least 1

# "0..*" - zero or more (optional, repeatable)
_check_cardinality(0, "0..*", "attr", result)  # ✓ Valid
_check_cardinality(100, "0..*", "attr", result)  # ✓ Valid

# "2..3" - range (between 2 and 3 inclusive)
_check_cardinality(2, "2..3", "attr", result)  # ✓ Valid
_check_cardinality(3, "2..3", "attr", result)  # ✓ Valid
_check_cardinality(1, "2..3", "attr", result)  # ✗ Error: expected at least 2
_check_cardinality(4, "2..3", "attr", result)  # ✗ Error: expected at most 3
```

### 3. Primitive Type Validation

Validates values against primitive types with proper type discrimination:

```python
# String type
_check_type("hello", "string")     # ✓ True
_check_type(123, "string")         # ✗ False

# Number type (excludes boolean)
_check_type(123, "number")         # ✓ True
_check_type(12.5, "number")        # ✓ True
_check_type(True, "number")        # ✗ False (bool is not number)

# Integer type (excludes boolean)
_check_type(123, "integer")        # ✓ True
_check_type(12.5, "integer")       # ✗ False
_check_type(True, "integer")       # ✗ False

# Boolean type
_check_type(True, "boolean")       # ✓ True
_check_type(False, "boolean")      # ✓ True
_check_type(1, "boolean")          # ✗ False
_check_type("true", "boolean")     # ✗ False
```

### 4. Regex Pattern Matching

ECMA-262 regex patterns converted to Python for validation:

```python
# Simple pattern
_check_regex("123", r"\d+")        # ✓ True
_check_regex("abc", r"\d+")        # ✗ False

# Cardinality pattern from spec
pattern = r"^(\d+)(\.\.(\d+|\*))?$"
_check_regex("1", pattern)         # ✓ True
_check_regex("0..1", pattern)      # ✓ True
_check_regex("1..*", pattern)      # ✓ True
_check_regex("2..3", pattern)      # ✓ True
_check_regex("abc", pattern)       # ✗ False
```

### 5. Numeric Interval Checking

Validates numeric values within min/max bounds:

```python
interval = {"min": 10, "max": 20}
_check_numeric_interval(15, interval)  # ✓ True
_check_numeric_interval(10, interval)  # ✓ True (inclusive)
_check_numeric_interval(20, interval)  # ✓ True (inclusive)
_check_numeric_interval(9, interval)   # ✗ False
_check_numeric_interval(21, interval)  # ✗ False

# Min only
interval = {"min": 0}
_check_numeric_interval(5, interval)   # ✓ True
_check_numeric_interval(-1, interval)  # ✗ False

# Max only
interval = {"max": 100}
_check_numeric_interval(50, interval)  # ✓ True
_check_numeric_interval(101, interval) # ✗ False
```

### 6. Whitelist/Blacklist Enforcement

Enforces allowed and disallowed values:

```python
# Whitelist
rules = ValidationRules(whitelist=["red", "green", "blue"])
_validate_value("red", rules, "color")    # ✓ Valid
_validate_value("yellow", rules, "color") # ✗ Error: not in whitelist

# Blacklist
rules = ValidationRules(blacklist=["spam", "scam"])
_validate_value("legit", rules, "type")   # ✓ Valid
_validate_value("spam", rules, "type")    # ✗ Error: in blacklist
```

### 7. Comprehensive Value Validation

Validates individual values against all assembled rules:

```python
rules = ValidationRules(
    cardinality="1..*",
    primitive_type="string",
    regex=r"^[A-Z][a-z]+$",
    whitelist=["Red", "Green", "Blue"]
)

# Validate individual values
result = _validate_value("Red", rules, "color")
assert result.valid is True  # Passes all checks

result = _validate_value("yellow", rules, "color")
assert result.valid is False  # Fails whitelist check
assert len(result.errors) == 1
```

### 8. Metadata Attribute Filtering

Core FDO metadata attributes are skipped during attribute validation:

```python
metadata_attrs = {"0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"}

for attr_name, values in record.data.items():
    if attr_name in metadata_attrs or not values:
        continue
    # Validate non-metadata attributes only
```

**Rationale:** These attributes are validated at the profile level (Phase 3), avoiding circular validation logic.

## Design Decisions

### 1. Assembly vs. Validation Separation (Continued)

Following the Phase 3-4 pattern, attribute validation delegates rule assembly:

**Benefits:**
- Validator focuses on checking values, not gathering rules
- Assembly logic can be optimized independently
- Clear separation of concerns
- Easy to add caching to `AttributeAssembly` without touching validator

**Example:**
```python
# ASSEMBLY: Get validation rules
rules = self.assembly.assemble_rules(attr_name)

# VALIDATION: Check cardinality
if rules.cardinality:
    self._check_cardinality(len(values), rules.cardinality, ...)

# VALIDATION: Check each value
for value in values:
    self._validate_value(value, rules, attr_name)
```

### 2. Permissive Error Handling

Invalid expressions (regex, cardinality) don't crash validation:

```python
try:
    # Parse cardinality expression
    if ".." in cardinality_str:
        parts = cardinality_str.split("..")
        min_count = int(parts[0])
        max_count = None if parts[1] == "*" else int(parts[1])
    ...
except (ValueError, IndexError):
    self.logger.log_step(
        "Cardinality",
        f"⚠ {attr_name}: invalid cardinality expression '{cardinality_str}'",
        indent=2,
    )
    return True  # Be permissive
```

**Rationale:**
- Type system definitions might be incomplete
- Better to warn and continue than block validation
- Allows incremental improvement of definitions

### 3. ECMA-262 to Python Regex Conversion

Uses Python's `re` module with `fullmatch()` for regex validation:

```python
def _check_regex(self, value: str, pattern: str) -> bool:
    try:
        # Note: ECMA-262 regex is mostly compatible with Python
        # Some edge cases might differ, but this works for most patterns
        return bool(re.fullmatch(pattern, value))
    except re.error:
        return True  # Invalid regex, be permissive
```

**Note:** ECMA-262 (JavaScript) regex has minor differences from Python regex, but the conversion works for most practical patterns used in the type system.

### 4. Boolean Type Discrimination

Explicitly excludes booleans from number/integer checks:

```python
elif expected_type == "number":
    return isinstance(value, (int, float)) and not isinstance(value, bool)
elif expected_type == "integer":
    return isinstance(value, int) and not isinstance(value, bool)
```

**Rationale:** In Python, `bool` is a subclass of `int`, so `isinstance(True, int)` returns `True`. For type validation purposes, we want to treat booleans separately.

### 5. ValidationResult Aggregation

Aggregates errors from multiple validation checks:

```python
def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
    result = ValidationResult()
    
    for attr_name, values in record.data.items():
        # Skip metadata
        if attr_name in metadata_attrs:
            continue
        
        # Assemble rules
        rules = self.assembly.assemble_rules(attr_name)
        
        # Check cardinality
        if rules.cardinality:
            if not self._check_cardinality(...):
                result.add_error(...)
        
        # Check each value
        for value in values:
            value_result = self._validate_value(value, rules, attr_name)
            result.merge(value_result)
    
    return result
```

### 6. Detailed Logging

Every validation step is logged in verbose mode:

```
Attribute Validation: Starting validation for test/Record
  Attribute Validation: → Validating 0.FDO/Name (1 value(s))
    Attribute Assembly: Starting rule assembly for 0.FDO/Name
      Attribute Definition: ✓ Resolved 0.FDO/Name
      Cardinality: Found: 1..*
      Syntax Definition: ↓ Resolving syntax: 0.FDO/StringSyntax
        Primitive Type: Found: string
    Attribute Assembly: ✓ Complete: cardinality=1..*, type=string
    Cardinality: ✓ 0.FDO/Name: 1 value(s) satisfies 1..*
    Type Check: ✓ 0.FDO/Name: type OK (string)
```

## Specification Compliance

Based on review of `/sections/02-Terminology.html`:

### FDO Attribute Validation Semantics

From the specification:
> **FDO Attribute Definition**: Attribute definitions determine the value space that attribute values possibly can have and make the content of the attribute predictable and actionable for machines. Attribute definitions equip a property of an FDO with a label, a semantic meaning and syntactical validation rules for the instantiating attribute value.

Our implementation validates all syntactical rules:
- ✅ Cardinality constraints (how many values)
- ✅ Primitive type (string, number, integer, boolean)
- ✅ Regex patterns (format constraints)
- ✅ Numeric intervals (range constraints)
- ✅ Whitelists/blacklists (enumeration constraints)

### Attribute Categories

From the specification:
> We distinguish three categories of attributes: (1) mandatory attributes specified by the FDO Forum, (2) optional attributes specified by the FDO Forum but not mandatory and (3) community-defined attributes specified by communities.

Our implementation handles all categories:
- ✅ Mandatory attributes (via cardinality "1" or "1..*")
- ✅ Optional attributes (via cardinality "0..1" or "0..*")
- ✅ Community-defined attributes (same validation mechanism applies)

### Validation Mechanism

From attribute definitions in the type system:
```json
{
  "0.FDO/ValidationMechanism": ["Syntax"],
  "0.FDO/DataType": ["0.FDO/StringSyntax"],
  "0.FDO/Cardinality": ["1..*"]
}
```

Our implementation:
- ✅ Respects `0.FDO/ValidationMechanism` (currently supports "Syntax")
- ✅ Follows `0.FDO/DataType` references to syntax definitions
- ✅ Enforces `0.FDO/Cardinality` constraints
- ✅ Validates values against assembled rules

## Test Results

```
============================= 115 passed in 0.12s ==============================

Phase 1: 38 tests (models, logger, registry)
Phase 2: 18 tests (assembly)
Phase 3: 26 tests (validators)
Phase 4: 6 tests (attribute assembly)
Phase 5: 27 tests (attribute validation) ← NEW
```

### Example Test Output

```bash
# Run all tests
uv run pytest tests/ -v

# Run only Phase 5 tests
uv run pytest tests/test_attribute_validation.py -v \
  -k "not TestAttributeAssembly"

# Run with coverage
uv run pytest --cov=. --cov-report=term-missing
```

## Usage Examples

### Validating Real Type System Attributes

```python
from validators import AttributeValidator
from assembly import AttributeAssembly
from registry import PidRegistry
from validation_logger import ValidationLogger

# Setup
logger = ValidationLogger(verbose=True)
registry = PidRegistry(logger)
assembly = AttributeAssembly(registry, logger)
validator = AttributeValidator(registry, logger, assembly)

# Validate 0.FDO/Type attribute definition
type_def = registry.resolve_pid("0.FDO/Type")
result = validator.validate(type_def, "0.FDO/Type")

print(f"\n0.FDO/Type Validation:")
print(f"  Valid: {result.valid}")
print(f"  Attributes checked: {result.attributes_checked}")
print(f"  Errors: {len(result.errors)}")
```

### Manual Cardinality Validation

```python
from models import ValidationResult

result = ValidationResult()

# Test different cardinality expressions
validator._check_cardinality(1, "1", "attr", result)        # Exactly one
validator._check_cardinality(0, "0..1", "attr", result)     # Optional
validator._check_cardinality(5, "1..*", "attr", result)     # Repeatable
validator._check_cardinality(2, "2..3", "attr", result)     # Range
```

### Custom Rule Validation

```python
from models import ValidationRules

# Create custom validation rules
rules = ValidationRules(
    cardinality="1..*",
    primitive_type="string",
    regex=r"^[A-Z][a-z]+$",
    whitelist=["Red", "Green", "Blue"]
)

# Validate individual values
result = validator._validate_value("Red", rules, "color")
print(f"Valid: {result.valid}")  # True

result = validator._validate_value("yellow", rules, "color")
print(f"Valid: {result.valid}")  # False (not in whitelist)
print(f"Errors: {result.errors}")
```

### Integration with Profile Validation

```python
from validators import ProfileValidator, AttributeValidator
from assembly import ProfileAssembly, AttributeAssembly

# Setup both validators
profile_assembly = ProfileAssembly(registry, logger)
attribute_assembly = AttributeAssembly(registry, logger)

profile_validator = ProfileValidator(registry, logger, profile_assembly)
attribute_validator = AttributeValidator(registry, logger, attribute_assembly)

# Validate record against profile
profile_result = profile_validator.validate(record, "test/Record")

# Validate attribute values
attribute_result = attribute_validator.validate(record, "test/Record")

# Combine results
if profile_result.valid and attribute_result.valid:
    print("✅ Record is fully valid!")
else:
    print("❌ Record has validation errors")
    print(f"Profile errors: {profile_result.errors}")
    print(f"Attribute errors: {attribute_result.errors}")
```

## Integration with Previous Phases

Phase 5 builds on and integrates with all previous phases:

### Phase 1 Foundation
- Uses `PidRecord` for record representation
- Uses `ValidationResult` for error aggregation
- Uses `ValidationRules` for rule representation
- Uses `ValidationLogger` for structured logging

### Phase 2 Profile Assembly
- No direct dependency
- Both assembly classes work in parallel

### Phase 3 Profile Validation
- Complements profile validation
- ProfileValidator checks structure (required attributes present)
- AttributeValidator checks values (attributes conform to definitions)

### Phase 4 Attribute Assembly
- Direct dependency on `AttributeAssembly`
- Delegates rule gathering to assembly
- Focuses purely on validation logic

## Next Steps: Phase 6 - Specification Validation

Phase 6 will implement:
- `SpecificationValidator` class
- Root profile conformance checks (R8-1)
- Profile extension validity (R8-2)
- Attribute definition syntax (R8-3)
- Syntax definition completeness (R8-4)
- Circular reference detection (R8-5)

## Notes

- Total lines for Phase 5: ~550 (250 implementation + 300 tests)
- Cumulative total: ~2,300 lines across 7 modules
- All 115 tests passing
- Full integration with Phase 4 AttributeAssembly
- Ready for Phase 6 specification validation

## Known Limitations

1. **Tuple Structure Not Implemented**: The specification mentions attributes as tuples `(definition_PID, value)`, but our JSON representation uses simple key-value pairs. This simplification works for local development but would need updating for actual FDO records.

2. **Validation Mechanism Types**: Currently only supports "Syntax" validation mechanism. Other mechanisms (e.g., "Semantic", "Custom") would require additional validators.

3. **Regex Flavor Differences**: ECMA-262 to Python regex conversion works for most patterns but may have edge case differences.

4. **No Caching**: Following design principle, no caching is implemented. Each validation performs fresh resolutions. Can be added later via inheritance.

5. **Metadata Attribute Simplification**: Skips Type, Profile, Data attributes entirely. In a full implementation, these would still be validated but through a different mechanism.
