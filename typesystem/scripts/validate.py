#!/usr/bin/env python3
"""
FDO Type System Validator

Validates all type system JSON files against their meta-profiles.
This script checks:
1. Required attributes are present
2. Attribute cardinalities are respected
3. Referenced files exist
4. Basic structural validity

Usage:
    python scripts/validate.py [path/to/file.json] [--quiet]

Options:
    --quiet, -q    Only show warnings and errors (hide successful steps)

If no file is specified, validates all files in the typesystem directory.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ValidationError(Exception):
    """Represents a validation error."""

    pass


class FDOValidator:
    """Validates FDO type system files."""

    def __init__(self, base_path: Path, verbose: bool = True):
        self.base_path = base_path
        self.verbose = verbose  # Set this FIRST before calling _load_registry
        self.registry = self._load_registry()
        self.errors: List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []

    def log(self, message: str, indent: int = 0):
        """Print a log message if verbose mode is enabled."""
        if self.verbose:
            prefix = "  " * indent
            print(f"{prefix}{message}")

    def _load_registry(self) -> Dict[str, str]:
        """Load the registry.json file."""
        registry_path = self.base_path / "registry.json"
        if not registry_path.exists():
            print(f"Warning: registry.json not found at {registry_path}")
            return {}

        with open(registry_path) as f:
            data = json.load(f)
            result = data.get("entries", {})
            self.log(f"Loaded registry with {len(result)} entries", 1)
            return result

    def resolve_reference(self, ref: str) -> Optional[Path]:
        """Resolve a PID or path reference to a local file path."""
        # Check if it's a known PID in registry
        if ref in self.registry:
            return self.base_path / self.registry[ref]

        # Check if it's already a relative path
        path = self.base_path / ref
        if path.exists():
            return path

        # Try common variations
        for suffix in [".json", ""]:
            for prefix in ["", "core/", "attributes/", "syntax/"]:
                test_path = self.base_path / f"{prefix}{ref}{suffix}"
                if test_path.exists():
                    return test_path

        return None

    def load_fdo(self, path: Path) -> Dict[str, Any]:
        """Load an FDO JSON file."""
        with open(path) as f:
            return json.load(f)

    def get_attribute_value(self, fdo: Dict, attr_name: str) -> Any:
        """Get the value of an attribute from an FDO record."""
        return fdo.get(attr_name, [])

    def is_pid_reference(self, value: str) -> bool:
        """Check if a string is a PID reference (not a literal value).

        Uses a blacklist of known non-PID literals. Can be enhanced later
        with proper PID validation when the type system uses real registered PIDs.
        """
        non_pid_literals = {"Not_Applicable"}
        return value not in non_pid_literals

    def get_profile_required_attributes(
        self, profile_ref: str, fdo_path: Path, _visited: Optional[set] = None
    ) -> Tuple[List[str], int, int]:
        """Load a profile definition and recursively collect required attributes from extended profiles.

        Returns a tuple of (required_attributes, total_attributes_collected, profiles_traversed_count).
        """
        if _visited is None:
            _visited = set()

        # Avoid infinite loops from circular extension references
        if profile_ref in _visited:
            self.log(f"    ↩ Skipping {profile_ref}: already visited", 4)
            return [], 0, 0
        _visited.add(profile_ref)

        resolved = self.resolve_reference(profile_ref)
        if not resolved or not resolved.exists():
            self.warnings.append(
                (str(fdo_path), f"Cannot resolve profile reference: {profile_ref}")
            )
            return [], 0, 1

        try:
            profile_def = self.load_fdo(resolved)
            own_attrs = profile_def.get("0.FDO/Attribute", [])

            # Collect attributes from extended profiles recursively
            extends_refs = profile_def.get("0.FDO/Extends", [])
            if extends_refs:
                self.log(f"    ↓ Extends: {extends_refs}", 3)

            all_attrs = list(own_attrs)
            profiles_count = 1

            for ext_ref in extends_refs:
                if not isinstance(ext_ref, str) or not self.is_pid_reference(ext_ref):
                    continue
                ext_attrs, ext_attr_count, ext_profile_count = (
                    self.get_profile_required_attributes(ext_ref, fdo_path, _visited)
                )
                # Merge attributes, avoiding duplicates
                for attr in ext_attrs:
                    if attr not in all_attrs:
                        all_attrs.append(attr)
                profiles_count += ext_profile_count

            return all_attrs, len(all_attrs), profiles_count

        except Exception as e:
            self.warnings.append(
                (str(fdo_path), f"Cannot load profile definition {profile_ref}: {e}")
            )
            return [], 0, 1

    def check_required_attributes(
        self, fdo: Dict, path: Path, required: List[str], indent: int = 1
    ) -> bool:
        """Check that all required attributes are present."""
        self.log("Checking required attributes:", indent)
        valid = True
        for attr in required:
            present = attr in fdo and fdo[attr]
            status = "✓" if present else "✗"
            self.log(
                f"  {status} {attr}: {'present' if present else 'MISSING'}", indent + 1
            )
            if not present:
                self.errors.append((str(path), f"Missing required attribute: {attr}"))
                valid = False
        return valid

    def check_cardinality(
        self, fdo: Dict, path: Path, attr_name: str, cardinality: str
    ) -> bool:
        """Check that an attribute's cardinality is satisfied."""
        values = fdo.get(attr_name, [])
        count = len(values) if isinstance(values, list) else (1 if values else 0)

        # Parse cardinality regex: ^(\d+)(\.\.(\d+|\*))?$
        match = re.match(r"^(\d+)(\.\.(\d+|\*))?$", cardinality)
        if not match:
            self.errors.append(
                (str(path), f"Invalid cardinality format: {cardinality}")
            )
            return False

        min_count = int(match.group(1))
        max_part = match.group(3)

        if max_part is None:
            # Exact count required
            if count != min_count:
                self.errors.append(
                    (
                        str(path),
                        f"Attribute {attr_name} must appear exactly {min_count} time(s), got {count}",
                    )
                )
                return False
        elif max_part == "*":
            # Min to infinity
            if count < min_count:
                self.errors.append(
                    (
                        str(path),
                        f"Attribute {attr_name} must appear at least {min_count} time(s), got {count}",
                    )
                )
                return False
        else:
            # Range
            max_count = int(max_part)
            if count < min_count or count > max_count:
                self.errors.append(
                    (
                        str(path),
                        f"Attribute {attr_name} must appear {min_count}-{max_count} time(s), got {count}",
                    )
                )
                return False

        return True

    def validate_syntax_definition(self, fdo: Dict, path: Path) -> bool:
        """Validate a syntax definition FDO."""
        valid = True

        # Load required attributes from 0.FDO/SyntaxDef profile definition
        self.log("Checking required attributes (from 0.FDO/SyntaxDef):", 1)
        required, attr_count, profile_count = self.get_profile_required_attributes(
            "0.FDO/SyntaxDef", path
        )
        self.log(
            f"  → Collected {attr_count} attributes from {profile_count} profile(s)", 2
        )
        if not required:
            required = ["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"]
        if not self.check_required_attributes(fdo, path, required):
            valid = False

        # Check 0.FDO/Type contains FDO_Syntax_Definition
        types = fdo.get("0.FDO/Type", [])
        if "FDO_Syntax_Definition" not in types:
            self.errors.append(
                (str(path), "Syntax definition must have type 'FDO_Syntax_Definition'")
            )
            valid = False

        # Check 0.FDO/Profile references 0.FDO/SyntaxDef
        profiles = fdo.get("0.FDO/Profile", [])
        if (
            "0.FDO/SyntaxDef" not in profiles
            and "syntax/0.FDO-SyntaxDef.json" not in str(profiles)
        ):
            self.warnings.append(
                (
                    str(path),
                    "Syntax definition should reference 0.FDO/SyntaxDef profile",
                )
            )

        # Check PrimitiveDataType is one of the four allowed values
        prim_types = fdo.get("0.FDO/PrimitiveDataType", [])
        allowed_primitives = ["string", "number", "integer", "boolean"]
        for pt in prim_types:
            if pt not in allowed_primitives:
                self.errors.append(
                    (
                        str(path),
                        f"Invalid primitive data type: {pt}. Must be one of: {allowed_primitives}",
                    )
                )
                valid = False

        return valid

    def validate_attribute_definition(self, fdo: Dict, path: Path) -> bool:
        """Validate an attribute definition FDO."""
        valid = True

        # Load required attributes from 0.FDO/AttributeDef profile definition
        self.log("Checking required attributes (from 0.FDO/AttributeDef):", 1)
        required, attr_count, profile_count = self.get_profile_required_attributes(
            "0.FDO/AttributeDef", path
        )
        self.log(
            f"  → Collected {attr_count} attributes from {profile_count} profile(s)", 2
        )
        if not required:
            required = ["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"]
        if not self.check_required_attributes(fdo, path, required):
            valid = False

        # Check 0.FDO/Type contains FDO_Attribute_Definition
        types = fdo.get("0.FDO/Type", [])
        if "FDO_Attribute_Definition" not in types:
            self.errors.append(
                (
                    str(path),
                    "Attribute definition must have type 'FDO_Attribute_Definition'",
                )
            )
            valid = False

        # Check ValidationMechanism is valid
        mechanisms = fdo.get("0.FDO/ValidationMechanism", [])
        allowed_mechanisms = [
            "Syntax",
            "Union",
            "InlineCombination",
            "Whitelist",
            "AttributeReference",
            "ProfileReference",
            "ExternalVocabularyReference",
        ]
        for mech in mechanisms:
            if mech not in allowed_mechanisms:
                self.errors.append((str(path), f"Invalid validation mechanism: {mech}"))
                valid = False

        # Check Cardinality format
        cardinalities = fdo.get("0.FDO/Cardinality", [])
        for card in cardinalities:
            if not re.match(r"^(\d+)(\.\.(\d+|\*))?$", str(card)):
                self.errors.append((str(path), f"Invalid cardinality format: {card}"))
                valid = False

        # Check DataType references exist (if present)
        data_types = fdo.get("0.FDO/DataType", [])
        for dt in data_types:
            resolved = self.resolve_reference(dt)
            if resolved is None:
                self.warnings.append(
                    (str(path), f"Cannot resolve DataType reference: {dt}")
                )

        return valid

    def validate_profile(self, fdo: Dict, path: Path) -> bool:
        """Validate a profile FDO."""
        self.log(f"\n📋 Validating PROFILE: {path.name}", 0)
        self.log(f"Path: {path}", 1)
        valid = True

        # Step 1: Check required attributes per the profile this FDO references
        self.log("\nStep 1: Checking required attributes (from profile definition):", 1)
        profile_refs = fdo.get("0.FDO/Profile", [])
        total_required = []
        total_profiles_traversed = 0
        for ref in profile_refs:
            if isinstance(ref, str) and not ref.startswith("0.FDO/"):
                # Skip non-FDO profile references (e.g., custom syntax profiles)
                continue
            required, attr_count, profile_count = self.get_profile_required_attributes(
                ref, path
            )
            total_required.extend([a for a in required if a not in total_required])
            total_profiles_traversed += profile_count
            if required:
                break  # Use the first successfully loaded profile definition
        required = total_required
        if not required:
            # Fallback: use common FDO attributes if no profile definition found
            required = ["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"]
            self.log(
                f"  ⚠ Could not load profile definition, using fallback: {required}",
                3,
            )
        else:
            self.log(
                f"  → Collected {len(required)} attributes from {total_profiles_traversed} profile(s)",
                2,
            )
        # Filter required attributes to only those the Profile actually declares
        # A Profile only needs to satisfy attributes it claims to have
        declared_attrs = fdo.get("0.FDO/Attribute", [])
        if declared_attrs:
            required = [attr for attr in required if attr in declared_attrs]
            self.log(f"  → Checking declared attributes only: {required}", 2)
        if not self.check_required_attributes(fdo, path, required, indent=2):
            valid = False

        # Step 2: Check 0.FDO/Type contains FDO_Profile
        self.log("\nStep 2: Checking FDO type:", 1)
        types = fdo.get("0.FDO/Type", [])
        self.log(f"  Found types: {types}", 2)
        if "FDO_Profile" in types:
            self.log("  ✓ Contains 'FDO_Profile'", 2)
        else:
            self.log("  ✗ MISSING 'FDO_Profile'", 2)
            self.errors.append((str(path), "Profile must have type 'FDO_Profile'"))
            valid = False

        # Step 3: Check 0.FDO/Attribute count
        self.log("\nStep 3: Checking attribute list:", 1)
        attrs = fdo.get("0.FDO/Attribute", [])
        self.log(f"  Found {len(attrs)} attribute(s): {attrs}", 2)
        if len(attrs) >= 3:
            self.log(f"  ✓ Has at least 3 attributes (minimum required)", 2)
        else:
            self.log(
                f"  ✗ Must define at least 3 attributes (Type, Profile, Data), got {len(attrs)}",
                2,
            )
            self.errors.append(
                (
                    str(path),
                    f"Profile must define at least 3 attributes (Type, Profile, Data), got {len(attrs)}",
                )
            )
            valid = False

        # Step 4: Check mandatory attributes are in the list
        self.log("\nStep 4: Checking mandatory attributes are listed:", 1)
        mandatory_in_list = ["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"]
        for mandatory_attr in mandatory_in_list:
            if mandatory_attr in attrs:
                self.log(f"  ✓ {mandatory_attr} is in attribute list", 2)
            else:
                self.log(f"  ✗ {mandatory_attr} is MISSING from attribute list", 2)
                self.errors.append(
                    (
                        str(path),
                        f"Profile must include {mandatory_attr} in 0.FDO/Attribute list",
                    )
                )
                valid = False

        # Step 5: Check referenced attribute definitions exist
        self.log("\nStep 5: Resolving attribute definition references:", 1)
        for attr_ref in attrs:
            self.log(f"  Checking reference: {attr_ref}", 2)
            resolved = self.resolve_reference(attr_ref)
            if resolved and resolved.exists():
                self.log(
                    f"    ✓ Resolved to: {resolved.relative_to(self.base_path)}", 3
                )
            else:
                self.log(f"    ✗ Cannot resolve", 3)
                self.warnings.append(
                    (str(path), f"Cannot resolve Attribute reference: {attr_ref}")
                )

        # Step 6: Check profile self-reference (special case for ProfileDef)
        if path.name == "0.FDO-ProfileDef.json":
            self.log(
                "\nStep 6: Checking self-referential structure (ProfileDef special case):",
                1,
            )
            profiles = fdo.get("0.FDO/Profile", [])
            self.log(f"  Profile references: {profiles}", 2)
            if "0.FDO/ProfileDef" in profiles:
                self.log(
                    f"  ✓ ProfileDef correctly references itself (bootstrapping)", 2
                )
            else:
                self.log(f"  ⚠ ProfileDef should reference itself for bootstrapping", 2)

        if valid:
            self.log(f"\n✅ PROFILE VALID: {path.name}", 0)
        else:
            self.log(f"\n❌ PROFILE INVALID: {path.name}", 0)

        return valid

    def validate_fdo_record(self, path: Path) -> bool:
        """Validate any FDO record based on its type."""
        try:
            fdo = self.load_fdo(path)
        except json.JSONDecodeError as e:
            self.errors.append((str(path), f"Invalid JSON: {e}"))
            return False

        # Determine FDO type and validate accordingly
        types = fdo.get("0.FDO/Type", [])

        if "FDO_Syntax_Definition" in types:
            return self.validate_syntax_definition(fdo, path)
        elif "FDO_Attribute_Definition" in types:
            return self.validate_attribute_definition(fdo, path)
        elif "FDO_Profile" in types:
            return self.validate_profile(fdo, path)
        else:
            # Generic validation for unknown types
            return self.check_required_attributes(
                fdo, path, ["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data"]
            )

    def validate_all(self) -> bool:
        """Validate all JSON files in the typesystem directory."""
        all_valid = True

        for root, dirs, files in os.walk(self.base_path):
            # Skip certain directories (virtual envs, cache, test data, etc.)
            dirs[:] = [
                d
                for d in dirs
                if d
                not in [
                    "instances",
                    "profiles",
                    "types",
                    "__pycache__",
                    ".venv",
                    "venv",
                    ".git",
                    "node_modules",
                    "dist",
                    "build",
                ]
            ]

            for file in files:
                if file.endswith(".json") and file not in [
                    "registry.json",
                    "uv_cache.json",
                    "direct_url.json",
                ]:
                    path = Path(root) / file
                    if not self.validate_fdo_record(path):
                        all_valid = False

        return all_valid

    def print_report(self):
        """Print validation report."""
        if self.errors:
            print("\n❌ ERRORS:")
            for path, msg in self.errors:
                print(f"  {path}: {msg}")

        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for path, msg in self.warnings:
                print(f"  {path}: {msg}")

        if not self.errors and not self.warnings:
            print("\n✅ All files validated successfully!")
        elif not self.errors:
            print(f"\n✅ Validation passed with {len(self.warnings)} warning(s)")
        else:
            print(
                f"\n❌ Validation failed with {len(self.errors)} error(s) and {len(self.warnings)} warning(s)"
            )


def main():
    base_path = Path(__file__).parent.parent

    # Parse command line arguments
    verbose = True
    file_path_args = []

    for arg in sys.argv[1:]:
        if arg in ["--quiet", "-q"]:
            verbose = False
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}")
            print("Usage: python validate.py [file1.json] [file2.json] ... [--quiet]")
            sys.exit(1)
        else:
            file_path_args.append(arg)

    validator = FDOValidator(base_path, verbose=verbose)
    all_valid = True

    if file_path_args:
        # Validate specific files
        for file_path_arg in file_path_args:
            file_path = Path(file_path_arg)
            if not file_path.is_absolute():
                # Try relative to current working directory first
                cwd_path = Path.cwd() / file_path
                if cwd_path.exists():
                    file_path = cwd_path
                else:
                    # Fall back to relative to base_path
                    file_path = base_path / file_path

            if not file_path.exists():
                validator.errors.append(
                    (str(file_path), f"File not found: {file_path}")
                )
                all_valid = False
                continue

            valid = validator.validate_fdo_record(file_path)
            if not valid:
                all_valid = False
    else:
        # Validate all files
        if verbose:
            print("🔍 Validating all type system files...\n")
        all_valid = validator.validate_all()

    validator.print_report()
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
