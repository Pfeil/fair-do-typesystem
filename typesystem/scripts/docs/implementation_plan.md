# Generic Record Validation - Implementation Plan

## Overview

This document outlines the implementation plan for a generic FDO record validator that validates records based on their content and structure rather than hard-coded type checks. The validator treats all FDOs uniformly, deriving validation rules from the profiles and attribute definitions they reference.

## Core Philosophy

**Content-Driven Validation**: Instead of checking "what type is this?" and applying hard-coded rules, we ask "what does this record claim to be?" and validate against those claims by resolving and interpreting the referenced profiles and attribute definitions.

**Transparency**: Logging serves to explain validation outcomes, not for debugging. Every decision should be traceable through logs.

**Abstraction**: File system details are hidden behind PID abstractions. Validators work with pure PIDs and records.

---

## File Structure

**Principle**: One file per concern/component group. Not one file per class (overkill), but not everything in one file (unmaintainable).

```
typesystem/scripts/
├── generic_record_validation.py    # CLI entry point, main()
├── models.py                       # Data classes (PidRecord, AssembledProfile, etc.)
├── registry.py                     # PidRegistry (PID resolution)
├── logging.py                      # ValidationLogger (structured logging)
├── assembly.py                     # ProfileAssembly, AttributeAssembly
├── validators.py                   # ProfileValidator, AttributeValidator, SpecificationValidator
└── orchestrator.py                 # ValidationOrchestrator (coordinates everything)
```

### File Responsibilities

**`generic_record_validation.py`** (~40 lines)
- CLI argument parsing
- File loading
- Orchestrator instantiation
- Main execution loop
- Exit codes

**`models.py`** (~80 lines)
- `PidRecord` dataclass
- `AssembledProfile` dataclass
- `ValidationRules` dataclass
- `ValidationResult` dataclass
- Pure data structures, no business logic

**`registry.py`** (~60 lines)
- `PidRegistry` class
- `_load_registry()` helper
- `resolve_pid()` method
- File system abstraction
- No validation logic

**`logging.py`** (~100 lines)
- `ValidationLogger` class
- Phase-based logging
- Indentation management
- Resolution counting
- Summary reporting

**`assembly.py`** (~150 lines)
- `ProfileAssembly` class
- `AttributeAssembly` class
- Recursive resolution logic
- Cycle detection
- Rule collection
- All "gathering" logic

**`validators.py`** (~200 lines)
- `ProfileValidator` class
- `AttributeValidator` class
- `SpecificationValidator` class
- Validation logic only (no data gathering)
- Use injected assembly components

**`orchestrator.py`** (~80 lines)
- `ValidationOrchestrator` class
- Wires all components together
- Coordinates validation phases
- Aggregates results

**Total**: ~710 lines across 7 files
**Average**: ~100 lines per file
**Benefit**: Each file is focused, navigable, and testable independently

### Import Structure

```
generic_record_validation.py
    └── imports orchestrator
        └── imports models, registry, logging, assembly, validators
            └── validators imports assembly, models, logging
            └── assembly imports models, registry, logging
```

No circular dependencies. Clean separation.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Interface                          │
│  (parse args, load files, coordinate validation, report)    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Validation Orchestrator                  │
│  (coordinate profile + attribute + spec validation)         │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   Profile    │ │  Attribute   │ │   Spec       │
    │  Validator   │ │  Validator   │ │  Validator   │
    └──────────────┘ └──────────────┘ └──────────────┘
            │               │               │
            └───────────────┼───────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      PID Registry                           │
│  (resolve PIDs → PidRecord, hide file system)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Validation Logger                         │
│  (structured logging for understanding, not debugging)      │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Design

### Design Principle: Assembly vs. Validation

**Assembly**: Gathering and combining information from multiple sources (profiles, extensions, attribute definitions, syntax rules).

**Validation**: Checking if data conforms to assembled rules.

**Why Separate?**
- Assembly logic is complex (recursive resolution, cycle detection, merging)
- Validation logic should focus on rules, not data gathering
- Easier to test assembly independently
- Can swap assembly strategies (e.g., add caching later) without touching validators
- Clearer responsibility boundaries

---

## Detailed Component Design

### 1. PidRecord

**Purpose**: Represents a resolved PID record, hiding file system details.

```python
class PidRecord:
    pid: str
    data: Dict[str, Any]  # The actual JSON content
    source_pid: str  # The PID used to resolve this record
    
    def get_values(self, attr_name: str) -> List[Any]:
        """Get all values for an attribute name."""
        return self.data.get(attr_name, [])
    
    def has_attribute(self, attr_name: str) -> bool:
        """Check if attribute exists and has values."""
        return bool(self.get_values(attr_name))
    
    def get_single_value(self, attr_name: str) -> Optional[Any]:
        """Get first value if exactly one exists."""
        values = self.get_values(attr_name)
        return values[0] if len(values) == 1 else None
```

**Key Design Decisions**:
- No file paths exposed
- Simple API for attribute access
- Immutable once created (no caching concerns)

---

### 2. PidRegistry

**Purpose**: Resolve PIDs to PidRecords, abstracting file system.

**Note**: Keep this simple - just resolution, no business logic.

```python
class PidRegistry:
    def __init__(self, logger: ValidationLogger):
        self.logger = logger
        self.base_path = Path(__file__).parent.parent
        self.registry = self._load_registry()
    
    def resolve_pid(self, pid: str) -> Optional[PidRecord]:
        """
        Resolve a PID to its record.
        Returns None if resolution fails (caller handles error).
        Logs resolution attempt and outcome.
        """
        # 1. Check registry.json
        # 2. Try as relative path
        # 3. Try common variations
        # Log each step
```

**Key Design Decisions**:
- No caching (worst-case analysis per requirements)
- All resolution attempts logged
- Returns `Optional` - caller decides how to handle failures

---

### 3. ValidationLogger

**Purpose**: Structured logging for understanding validation outcomes.

**Design Philosophy**: Traditional logging uses levels (DEBUG, INFO, WARN, ERROR). Our logger uses **validation phases** and **resolution depth**.

```python
class ValidationLogger:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.indent_level = 0
        self.resolution_count = 0
        self.validation_steps = []
    
    def log_phase(self, phase: str, message: str):
        """Log a major validation phase."""
        print(f"\n{phase}: {message}")
    
    def log_step(self, step: str, message: str, indent: int = 0):
        """Log a validation step within a phase."""
        if self.verbose:
            prefix = "  " * (self.indent_level + indent)
            print(f"{prefix}{step}: {message}")
    
    def log_resolution(self, pid: str, success: bool, target: Optional[str] = None):
        """Log a PID resolution event."""
        self.resolution_count += 1
        if self.verbose:
            status = "✓" if success else "✗"
            target_info = f" → {target}" if target else ""
            print(f"  {status} Resolved {pid}{target_info}")
    
    def enter_context(self):
        """Increase indent for nested validation."""
        self.indent_level += 1
    
    def exit_context(self):
        """Decrease indent after nested validation."""
        self.indent_level -= 1
    
    def print_summary(self, record_pid: str, valid: bool, errors: List[str], warnings: List[str]):
        """Print summary after validating one record."""
        print(f"\n{'✅' if valid else '❌'} {record_pid}")
        print(f"  Resolutions performed: {self.resolution_count}")
        print(f"  Errors: {len(errors)}, Warnings: {len(warnings)}")
```

**Why Unusual?**:
- Indentation tracks validation depth (nested profiles, extended attributes)
- Resolution counting shows complexity
- Phase-based rather than severity-based
- Summary per record, not just final report

### 4. ProfileAssembly

**NEW CLASS** - Encapsulates assembling complete profile information from potentially extended profiles.

**Purpose**: Given a profile PID, resolve the entire extension chain and assemble a complete view of required attributes.

**Why Separate from Validator?**
- Complex logic (recursion, cycles, merging) isolated
- Can be tested independently
- Validator focuses on "does record match?" not "how to gather profile info?"
- Easy to add optimizations later (caching, parallel resolution)

```python
@dataclass
class AssembledProfile:
    """Complete profile information assembled from profile and all extensions."""
    pid: str
    all_attributes: List[str]  # All attributes from profile chain
    declared_attributes: List[str]  # Only what this profile declares
    extends_chain: List[str]  # List of all profiles in extension chain
    profiles_resolved: int  # Number of profiles resolved
    has_cycle: bool  # True if cycle was detected

class ProfileAssembly:
    def __init__(self, registry: PidRegistry, logger: ValidationLogger):
        self.registry = registry
        self.logger = logger
    
    def assemble(self, profile_pid: str) -> AssembledProfile:
        """
        Assemble complete profile information by resolving extension chain.
        
        Handles cycles gracefully (marks has_cycle=True, continues with partial info).
        Logs resolution steps at appropriate detail level.
        """
        visited = set()
        all_attrs = []
        extends_chain = []
        has_cycle = False
        
        self._resolve_profile_chain(
            profile_pid, visited, all_attrs, extends_chain, has_cycle
        )
        
        return AssembledProfile(
            pid=profile_pid,
            all_attributes=all_attrs,
            declared_attributes=self._get_declared_attributes(profile_pid),
            extends_chain=extends_chain,
            profiles_resolved=len(visited),
            has_cycle=has_cycle
        )
    
    def _resolve_profile_chain(
        self,
        pid: str,
        visited: Set[str],
        all_attrs: List[str],
        extends_chain: List[str],
        has_cycle: bool
    ):
        """Recursive helper to resolve profile chain."""
        if pid in visited:
            self.logger.log_step("Cycle", f"↩ {pid} already visited")
            has_cycle = True
            return
        
        visited.add(pid)
        extends_chain.append(pid)
        
        profile = self.registry.resolve_pid(pid)
        if not profile:
            self.logger.log_step("Resolution", f"✗ Failed to resolve {pid}")
            return
        
        # Add this profile's attributes
        attrs = profile.get_values("0.FDO/Attribute")
        for attr in attrs:
            if attr not in all_attrs:
                all_attrs.append(attr)
        
        self.logger.log_step(
            "Profile",
            f"✓ {pid}: {len(attrs)} attributes"
        )
        
        # Recursively resolve extensions
        extends = profile.get_values("0.FDO/Extends")
        for ext_pid in extends:
            if self.is_pid_reference(ext_pid):
                self._resolve_profile_chain(
                    ext_pid, visited, all_attrs, extends_chain, has_cycle
                )
```

**Usage Example**:
```python
assembly = ProfileAssembly(registry, logger)
assembled = assembly.assemble("0.FDO/ProfileDef")

print(f"Resolved {assembled.profiles_resolved} profiles")
print(f"Total attributes: {len(assembled.all_attributes)}")
print(f"Chain: {' → '.join(assembled.extends_chain)}")
```

---

### 5. AttributeAssembly

**NEW CLASS** - Encapsulates assembling validation rules from attribute definitions.

**Purpose**: Given an attribute name, resolve its definition and collect all validation rules (syntax, cardinality, whitelists, etc.).

**Why Separate from Validator?**
- Attribute definitions can reference syntax definitions (another layer)
- Rule collection is complex (multiple attributes contribute rules)
- Validator focuses on "does value match rules?" not "where do rules come from?"
- Easy to extend with new rule types

```python
@dataclass
class ValidationRules:
    """Assembled validation rules for an attribute."""
    cardinality: Optional[str]  # e.g., "1..*", "0..1"
    primitive_type: Optional[str]  # "string", "number", "integer", "boolean"
    regex: Optional[str]  # ECMA-262 regex pattern
    numeric_interval: Optional[dict]  # {"min": 0, "max": 100}
    whitelist: Optional[List[Any]]  # Allowed values
    blacklist: Optional[List[Any]]  # Disallowed values
    syntax_definition_pid: Optional[str]  # Source of syntax rules

class AttributeAssembly:
    def __init__(self, registry: PidRegistry, logger: ValidationLogger):
        self.registry = registry
        self.logger = logger
    
    def assemble_rules(self, attr_name: str) -> ValidationRules:
        """
        Assemble all validation rules for an attribute.
        
        Steps:
        1. Resolve attribute definition
        2. Extract cardinality
        3. Resolve syntax definition (if present)
        4. Extract syntax rules (primitive type, regex, etc.)
        5. Return combined rules
        """
        attr_def = self.registry.resolve_pid(attr_name)
        if not attr_def:
            return ValidationRules()  # Empty rules, validator will handle
        
        # Extract cardinality
        cardinality_vals = attr_def.get_values("0.FDO/Cardinality")
        cardinality = cardinality_vals[0] if cardinality_vals else None
        
        # Resolve syntax definition
        syntax_refs = attr_def.get_values("0.FDO/SyntaxDefinition")
        syntax_pid = syntax_refs[0] if syntax_refs else None
        
        rules = ValidationRules(
            cardinality=cardinality,
            syntax_definition_pid=syntax_pid
        )
        
        # If syntax definition exists, extract its rules
        if syntax_pid:
            syntax_def = self.registry.resolve_pid(syntax_pid)
            if syntax_def:
                rules.primitive_type = self._extract_single_value(
                    syntax_def.get_values("0.FDO/PrimitiveDataType")
                )
                rules.regex = self._extract_single_value(
                    syntax_def.get_values("0.FDO/Regex")
                )
                # ... extract other syntax rules
        
        return rules
    
    def _extract_single_value(self, values: List[Any]) -> Optional[Any]:
        """Get first value if exactly one exists."""
        return values[0] if len(values) == 1 else None
```

---

### 6. Profile Validator

**Purpose**: Validate that a record conforms to its claimed profile(s).

**Now Simplified** - Delegates assembly to `ProfileAssembly`, focuses on validation logic.

**Validation Flow**:
```
1. Extract profile references from record's 0.FDO/Profile attribute
2. For each profile reference:
   a. Use ProfileAssembly to assemble complete profile
   b. Filter to attributes the profile actually declares
   c. Check record has all required attributes
3. Report results
```

```python
class ProfileValidator:
    def __init__(
        self, 
        registry: PidRegistry, 
        logger: ValidationLogger,
        assembly: ProfileAssembly  # Injected dependency
    ):
        self.registry = registry
        self.logger = logger
        self.assembly = assembly
    
    def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Validate record against its profile(s).
        
        Now delegates assembly complexity to ProfileAssembly.
        Focuses purely on validation logic.
        """
        profile_refs = record.get_values("0.FDO/Profile")
        
        for profile_ref in profile_refs:
            if not self.is_pid_reference(profile_ref):
                continue
            
            # ASSEMBLY: Get complete profile info
            assembled = self.assembly.assemble(profile_ref)
            
            self.logger.log_step(
                "Profile Assembly",
                f"Resolved {assembled.profiles_resolved} profile(s), "
                f"{len(assembled.all_attributes)} total attributes"
            )
            
            # VALIDATION: Check record matches profile
            required = self._filter_to_declared(
                assembled.all_attributes,
                assembled.declared_attributes
            )
            
            for attr in required:
                if not record.has_attribute(attr):
                    # Report error
                    pass
```

**Benefits of Separation**:
- Validator code is simpler, focused on validation
- Assembly logic tested independently
- Can see assembly stats (profiles resolved, attributes collected)
- Easy to add caching to `ProfileAssembly` without touching validator

---

### 7. Attribute Validator

**Purpose**: Validate each attribute value against its attribute definition.

**Now Simplified** - Delegates rule assembly to `AttributeAssembly`, focuses on value checking.

**Validation Flow**:
```
For each attribute in record:
1. Extract attribute definition PID (first element of tuple)
2. Resolve attribute definition
3. Extract validation rules from attribute definition:
   - Syntax definition (0.FDO/PrimitiveDataType, 0.FDO/Regex, etc.)
   - Cardinality (0.FDO/Cardinality)
   - Whitelist/Blacklist if present
4. Validate value against collected rules
5. Report violations
```

```python
class AttributeValidator:
    def __init__(
        self, 
        registry: PidRegistry, 
        logger: ValidationLogger,
        assembly: AttributeAssembly  # Injected dependency
    ):
        self.registry = registry
        self.logger = logger
        self.assembly = assembly
    
    def validate_all(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """Validate all attributes in the record."""
        for attr_name, values in record.data.items():
            self.validate_attribute(attr_name, values, record_pid)
    
    def validate_attribute(
        self, 
        attr_name: str, 
        values: List[Any], 
        record_pid: str
    ) -> bool:
        """
        Validate a single attribute.
        
        Now delegates rule assembly to AttributeAssembly.
        Focuses purely on value validation.
        
        Steps:
        1. ASSEMBLY: Get validation rules for attribute
        2. VALIDATION: Check cardinality
        3. VALIDATION: Check each value against syntax rules
        """
        # ASSEMBLY: Collect all rules
        rules = self.assembly.assemble_rules(attr_name)
        
        # VALIDATION: Check cardinality
        if rules.cardinality:
            if not self.check_cardinality(len(values), rules.cardinality, attr_name):
                return False
        
        # VALIDATION: Check each value against syntax rules
        for value in values:
            if not self.validate_value_against_rules(value, rules, attr_name):
                return False
        
        return True
```

**Value Validation Against Rules**:
```python
def validate_value_against_rules(
    self, 
    value: Any, 
    rules: ValidationRules, 
    attr_name: str
) -> bool:
    """
    Validate a single value against assembled rules.
    
    Checks:
    1. Primitive type (if specified)
    2. Regex pattern (if specified)
    3. Numeric interval (if specified)
    4. Whitelist (if specified)
    5. Blacklist (if specified)
    """
    valid = True
    
    # Type check
    if rules.primitive_type:
        if not self.check_type(value, rules.primitive_type):
            self.logger.log_step(
                "Type",
                f"✗ {attr_name}: {value} is not {rules.primitive_type}"
            )
            valid = False
    
    # Regex check
    if rules.regex:
        if not re.match(rules.regex, str(value)):
            self.logger.log_step(
                "Regex",
                f"✗ {attr_name}: {value} doesn't match {rules.regex}"
            )
            valid = False
    
    # Whitelist check
    if rules.whitelist:
        if value not in rules.whitelist:
            self.logger.log_step(
                "Whitelist",
                f"✗ {attr_name}: {value} not in allowed values"
            )
            valid = False
    
    # Blacklist check
    if rules.blacklist:
        if value in rules.blacklist:
            self.logger.log_step(
                "Blacklist",
                f"✗ {attr_name}: {value} is disallowed"
            )
            valid = False
    
    return valid
```

**Cardinality Validation**:
```python
def check_cardinality(
    self, 
    actual_count: int, 
    cardinality_str: str, 
    attr_name: str
) -> bool:
    """
    Validate count against cardinality regex: ^(\d+)(\.\.(\d+|\*))?$
    
    Examples:
    - "1" → exactly 1
    - "0..1" → 0 or 1
    - "1..*" → at least 1
    - "2..3" → between 2 and 3 inclusive
    """
```

---

### 8. Specification Validator

**Purpose**: Check conformance to FDO specification beyond profile/attribute validation.

**Checks**:
- [R8-1]: Has 0.FDO/Profile attribute
- [R8-4]: Validates against 0.FDO/Root profile
- [R8-5]: No violations of spec rules
- Profile self-reference for ProfileDef ([R4-7])
- Minimum 3 attributes in profiles ([R4-3])
- Type consistency (FDO_Profile, FDO_Attribute_Definition, etc.)

```python
class SpecificationValidator:
    def __init__(self, registry: PidRegistry, logger: ValidationLogger):
        self.registry = registry
        self.logger = logger
    
    def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Perform specification-level checks.
        
        These are rules that can't be expressed purely through
        profile/attribute validation.
        """
```

---

### 9. Validation Orchestrator

**Purpose**: Coordinate all validators and aggregate results.

```python
class ValidationOrchestrator:
    def __init__(self, verbose: bool = False):
        self.logger = ValidationLogger(verbose)
        self.registry = PidRegistry(self.logger)
        
        # Assembly components (handle data gathering)
        self.profile_assembly = ProfileAssembly(self.registry, self.logger)
        self.attribute_assembly = AttributeAssembly(self.registry, self.logger)
        
        # Validator components (handle rule checking)
        self.profile_validator = ProfileValidator(
            self.registry, self.logger, self.profile_assembly
        )
        self.attribute_validator = AttributeValidator(
            self.registry, self.logger, self.attribute_assembly
        )
        self.spec_validator = SpecificationValidator(self.registry, self.logger)
    
    def validate_record(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Run all validations on a single record.
        
        Order matters:
        1. Specification (basic structure)
        2. Profile (required attributes)
        3. Attribute (value validation)
        """
        results = []
        
        self.logger.log_phase("Specification", record_pid)
        results.append(self.spec_validator.validate(record, record_pid))
        
        self.logger.log_phase("Profile", record_pid)
        results.append(self.profile_validator.validate(record, record_pid))
        
        self.logger.log_phase("Attribute", record_pid)
        results.append(self.attribute_validator.validate_all(record, record_pid))
        
        return self.aggregate_results(results)
```

---

### 10. CLI Interface

```python
def main():
    parser = argparse.ArgumentParser(description="Validate FDO records")
    parser.add_argument("files", nargs="+", help="JSON files to validate")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Show intermediate validation steps")
    args = parser.parse_args()
    
    orchestrator = ValidationOrchestrator(verbose=args.verbose)
    
    all_valid = True
    for file_path in args.files:
        # Convert file path to PID (hide file system)
        record_pid = path_to_pid(file_path)
        record = load_record(file_path)
        
        result = orchestrator.validate_record(record, record_pid)
        
        orchestrator.logger.print_summary(
            record_pid, 
            result.valid, 
            result.errors, 
            result.warnings
        )
        
        if not result.valid:
            all_valid = False
    
    sys.exit(0 if all_valid else 1)
```

---

## Data Flow Example

### With Enhanced Encapsulation

Let's trace validation of a profile record:

**Input**: `0.FDO-Root.json`
```json
{
  "0.FDO/Type": ["FDO_Profile"],
  "0.FDO/Profile": ["0.FDO/ProfileDef"],
  "0.FDO/Data": ["Not_Applicable"],
  "0.FDO/Name": [...],
  "0.FDO/Description": [...],
  "0.FDO/Attribute": ["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"]
}
```

**Validation Steps**:

1. **Load & Abstract**: File → `PidRecord(pid="0.FDO/Root", data=...)`

2. **Specification Check**:
   - ✓ Has 0.FDO/Profile
   - ✓ Type is FDO_Profile
   - ⚠ Only 3 attributes (minimum met)

3. **Profile Validation** (with ProfileAssembly):
   ```
   Step 1: Extract profile references
     → ["0.FDO/ProfileDef"]
   
   Step 2: ProfileAssembly.assemble("0.FDO/ProfileDef")
     └─→ Resolve 0.FDO/ProfileDef
         → Log: "✓ Profile: 0.FDO/ProfileDef: 8 attributes"
     └─→ Check extensions
         → 0.FDO/Extends: ["Not_Applicable"]
         → Filter: Not a PID reference
         → No recursive resolution
     └─→ Return AssembledProfile:
         - all_attributes: [Type, Profile, Data, Name, Description, ...]
         - declared_attributes: [Type, Profile, Data, ...]
         - profiles_resolved: 1
   
   Step 3: ProfileValidator checks record
     → Filter to declared attributes: [Type, Profile, Data]
     → Check presence:
       ✓ Type present
       ✓ Profile present  
       ✓ Data present
   ```

4. **Attribute Validation** (with AttributeAssembly):
   ```
   For each attribute (e.g., "0.FDO/Type"):
   
   Step 1: AttributeAssembly.assemble_rules("0.FDO/Type")
     └─→ Resolve attribute definition
     └─→ Extract cardinality: "1..*"
     └─→ Resolve syntax definition (if present)
     └─→ Return ValidationRules:
         - cardinality: "1..*"
         - primitive_type: None
         - whitelist: ["FDO_Profile", "FDO_Attribute_Definition", ...]
   
   Step 2: AttributeValidator checks value
     → Check cardinality: record has 1 value, needs 1..* ✓
     → Check whitelist: "FDO_Profile" is allowed ✓
   ```

5. **Summary**:
   ```
   ✅ 0.FDO/Root
     Resolutions performed: 7
     Errors: 0, Warnings: 0
   ```

---

## Key Design Decisions & Trade-offs

### 1. Assembly vs. Validation Separation
**Decision**: Extract `ProfileAssembly` and `AttributeAssembly` as separate classes.

**Rationale**: 
- Clear separation: Assembly = gathering, Validation = checking
- Assembly logic is complex (recursion, cycles, merging) - deserves isolation
- Validators become simpler, focused on rules
- Easy to optimize assembly later (caching, parallel) without touching validators
- Better testability (test assembly output independently)

**Trade-off**: More classes, but each is simpler and more focused.

### 2. No Caching
**Decision**: Explicitly no caching of resolved PIDs.

**Rationale**: 
- Worst-case analysis reveals true resolution complexity
- Simpler code (no cache invalidation concerns)
- Easier to reason about for now

**Trade-off**: Slower validation, especially for deeply nested profiles. Acceptable for current use case.

**Note**: With `ProfileAssembly` separated, adding caching later is trivial:
```python
class CachedProfileAssembly(ProfileAssembly):
    def __init__(self, registry, logger):
        super().__init__(registry, logger)
        self._cache = {}
    
    def assemble(self, profile_pid: str) -> AssembledProfile:
        if profile_pid not in self._cache:
            self._cache[profile_pid] = super().assemble(profile_pid)
        return self._cache[profile_pid]
```

### 3. PID-Centric Abstraction
**Decision**: Hide file paths completely behind `PidRegistry`.

**Rationale**:
- Matches real-world usage (PIDs, not paths)
- Makes code future-proof for actual PID resolution
- Cleaner separation of concerns

**Trade-off**: Need `path_to_pid` mapping for local development.

### 4. Phase-Based Logging
**Decision**: Use validation phases instead of severity levels.

**Rationale**:
- Helps users understand validation flow
- Shows where in the process failure occurred
- More informative than "ERROR" alone

**Trade-off**: Non-standard logging approach.

### 5. Recursive Profile Resolution
**Decision**: Fully resolve profile extension chains.

**Rationale**:
- Correct behavior per spec [R4-11]
- Handles complex inheritance scenarios
- Cycle detection prevents infinite loops

**Trade-off**: More complex than flat profile checking.

### 6. Separate Validators
**Decision**: Three distinct validators (Spec, Profile, Attribute).

**Rationale**:
- Clear separation of concerns
- Easy to disable/swap validators for experiments
- Modular design for future library use

**Trade-off**: Some code duplication between validators.

---

## Additional Encapsulation Benefits

### Testing Strategy

With assembly separated, testing becomes clearer:

```python
def test_profile_assembly_with_extension():
    """Test that profile extension chain is resolved correctly."""
    assembly = ProfileAssembly(mock_registry, mock_logger)
    result = assembly.assemble("ChildProfile")
    
    assert result.profiles_resolved == 2  # Child + Parent
    assert "ParentAttr" in result.all_attributes
    assert result.has_cycle == False

def test_profile_validator_uses_assembly():
    """Test that validator correctly uses assembled profile."""
    mock_assembly = Mock()
    mock_assembly.assemble.return_value = AssembledProfile(
        pid="TestProfile",
        all_attributes=["Attr1", "Attr2"],
        declared_attributes=["Attr1"],
        profiles_resolved=1,
        has_cycle=False
    )
    
    validator = ProfileValidator(registry, logger, mock_assembly)
    result = validator.validate(test_record, "test.pid")
    
    # Verify assembly was called
    mock_assembly.assemble.assert_called_once()
    # Verify validation used assembled data
    assert result.valid == True
```

### Future Extensions Made Easy

**Example: Add caching to assembly**
```python
class CachedProfileAssembly(ProfileAssembly):
    """Drop-in replacement with caching."""
    def __init__(self, registry, logger):
        super().__init__(registry, logger)
        self._cache = {}
    
    def assemble(self, profile_pid: str) -> AssembledProfile:
        if profile_pid in self._cache:
            self.logger.log_step("Cache", f"Hit: {profile_pid}")
            return self._cache[profile_pid]
        
        result = super().assemble(profile_pid)
        self._cache[profile_pid] = result
        return result
```

**Example: Parallel assembly**
```python
class ParallelProfileAssembly(ProfileAssembly):
    """Resolve multiple profiles in parallel."""
    def assemble_multiple(self, profile_pids: List[str]) -> List[AssembledProfile]:
        with ThreadPoolExecutor() as executor:
            return list(executor.map(self.assemble, profile_pids))
```

---

## Potential Issues & Mitigations

### Issue 1: Circular Profile Extensions
**Risk**: Profile A extends B, B extends A → infinite loop.

**Mitigation**: `_visited` set in `collect_profile_attributes()` detects cycles.

### Issue 2: Missing Profile Definitions
**Risk**: Profile references non-existent definition.

**Mitigation**: `resolve_pid()` returns `None`, validator logs warning and continues with fallback.

### Issue 3: Attribute Definition Chains
**Risk**: Attribute definitions reference syntax definitions that reference other definitions.

**Mitigation**: Same recursive pattern with cycle detection applies throughout.

### Issue 4: Verbose Output Overwhelm
**Risk**: Too much logging makes output unreadable.

**Mitigation**: 
- Default: minimal output (errors/warnings only)
- `--verbose`: detailed intermediate steps
- Structured indentation shows nesting clearly

### Issue 5: Hard-Coded Knowledge Creep
**Risk**: Slowly re-introducing hard-coded lists like old validator.

**Mitigation**: 
- Code review checklist includes "Is this hard-coded?"
- Always prefer `record.get_values()` over literals
- Document any necessary exceptions

---

## Implementation Phases

### Phase 1: Foundation (Core Classes)
- [ ] `PidRecord` class
- [ ] `PidRegistry` with resolution
- [ ] `ValidationLogger` with structured output
- [ ] `ValidationResult` dataclass
- [ ] `AssembledProfile` dataclass
- [ ] `ValidationRules` dataclass

### Phase 2: Profile Assembly
- [ ] `ProfileAssembly` class
- [ ] Recursive profile extension resolution
- [ ] Cycle detection
- [ ] Attribute merging logic
- [ ] Tests for assembly (independent of validation)

### Phase 3: Profile Validation
- [ ] `ProfileValidator` using `ProfileAssembly`
- [ ] Required attribute checking
- [ ] Integration with assembly
- [ ] Simplified validator logic

### Phase 4: Attribute Assembly
- [ ] `AttributeAssembly` class
- [ ] Syntax rule extraction
- [ ] Cardinality extraction
- [ ] Tests for assembly (independent of validation)

### Phase 5: Attribute Validation
- [ ] `AttributeValidator` using `AttributeAssembly`
- [ ] Cardinality validation
- [ ] Primitive type validation
- [ ] Regex validation
- [ ] Whitelist/blacklist validation
- [ ] Integration with assembly

### Phase 4: Specification Validation
- [ ] `SpecificationValidator`
- [ ] Root profile conformance
- [ ] Structural checks
- [ ] Type consistency checks

### Phase 5: Orchestration & CLI
- [ ] `ValidationOrchestrator`
- [ ] CLI argument parsing
- [ ] File loading and PID conversion
- [ ] Summary reporting

### Phase 6: Testing & Refinement
- [ ] Test with existing type system files
- [ ] Verify logging clarity
- [ ] Performance profiling (even without caching)
- [ ] Documentation

---

## Evaluation of This Plan

### Strengths
1. **True Generic Approach**: No hard-coded type checks, everything derived from content
2. **Transparent**: Every validation decision traceable through logs
3. **Modular**: Easy to swap components for experiments
4. **Spec-Aligned**: Directly implements requirements from sections
5. **Future-Proof**: PID abstraction ready for real registries
6. **Better Encapsulation**: Assembly logic isolated from validation logic
7. **Testable**: Assembly and validation can be tested independently
8. **Extensible**: Easy to add caching, parallelism, or new rule types

### Weaknesses
1. **More Classes**: Additional `ProfileAssembly` and `AttributeAssembly` classes
2. **Performance**: No caching means repeated resolutions (but easier to add later)
3. **Learning Curve**: Phase-based logging unfamiliar to some

### Mitigation for "More Classes"
The additional classes actually **reduce** complexity per class:
- `ProfileAssembly`: ~80 lines (just assembly logic)
- `ProfileValidator`: ~60 lines (just validation logic)
- vs. combined `ProfileValidator`: ~140 lines doing both

Smaller, focused classes are easier to understand and maintain.

### Risks
1. **Scope Creep**: Could become too ambitious
2. **Over-Engineering**: Might be more than needed initially
3. **Debugging Difficulty**: Without traditional debug logs

### Mitigation Strategy
- Start minimal, add features incrementally
- Keep verbose mode truly optional
- Document assumptions clearly
- Regular code reviews against DRY principle

---

## Conclusion

This plan creates a validator that truly understands FDOs through their content rather than hard-coded type checks. The unusual logging approach serves the goal of transparency, making validation outcomes understandable rather than just reporting pass/fail.

The modular design supports future experimentation while the PID abstraction ensures relevance beyond local file-based development.

**Next Step**: Review this plan, then proceed with Phase 1 implementation.
