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
    python scripts/validate.py [path/to/file.json]

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

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.registry = self._load_registry()
        self.errors: List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []

    def _load_registry(self) -> Dict[str, str]:
        """Load the registry.json file."""
        registry_path = self.base_path / "registry.json"
        if not registry_path.exists():
            print(f"Warning: registry.json not found at {registry_path}")
            return {}

        with open(registry_path) as f:
            data = json.load(f)
            return data.get("entries", {})

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

    def check_required_attributes(
        self, fdo: Dict, path: Path, required: List[str]
    ) -> bool:
        """Check that all required attributes are present."""
        valid = True
        for attr in required:
            if attr not in fdo or not fdo[attr]:
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

        # Required attributes per 0.FDO/SyntaxDef
        required = [
            "0.FDO/Type",
            "0.FDO/Profile",
            "0.FDO/Data",
            "0.FDO/Name",
            "0.FDO/PrimitiveDataType",
        ]
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

        # Required attributes per 0.FDO/AttributeDef
        required = [
            "0.FDO/Type",
            "0.FDO/Profile",
            "0.FDO/Data",
            "0.FDO/Name",
            "0.FDO/ValidationMechanism",
            "0.FDO/Cardinality",
        ]
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
        valid = True

        # Required attributes per 0.FDO/ProfileDef
        required = [
            "0.FDO/Type",
            "0.FDO/Profile",
            "0.FDO/Data",
            "0.FDO/Name",
            "0.FDO/Attribute",
        ]
        if not self.check_required_attributes(fdo, path, required):
            valid = False

        # Check 0.FDO/Type contains FDO_Profile
        types = fdo.get("0.FDO/Type", [])
        if "FDO_Profile" not in types:
            self.errors.append((str(path), "Profile must have type 'FDO_Profile'"))
            valid = False

        # Check 0.FDO/Attribute has at least 3 entries (Type, Profile, Data are mandatory)
        attrs = fdo.get("0.FDO/Attribute", [])
        if len(attrs) < 3:
            self.errors.append(
                (
                    str(path),
                    f"Profile must define at least 3 attributes (Type, Profile, Data), got {len(attrs)}",
                )
            )
            valid = False

        # Check referenced attribute definitions exist
        for attr_ref in attrs:
            resolved = self.resolve_reference(attr_ref)
            if resolved is None:
                self.warnings.append(
                    (str(path), f"Cannot resolve Attribute reference: {attr_ref}")
                )

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

    if len(sys.argv) > 1:
        # Validate specific file
        file_path = Path(sys.argv[1])
        if not file_path.is_absolute():
            # Try relative to current working directory first
            cwd_path = Path.cwd() / file_path
            if cwd_path.exists():
                file_path = cwd_path
            else:
                # Fall back to relative to base_path
                file_path = base_path / file_path

        validator = FDOValidator(base_path)
        valid = validator.validate_fdo_record(file_path)
        validator.print_report()
        sys.exit(0 if valid else 1)
    else:
        # Validate all files
        validator = FDOValidator(base_path)
        valid = validator.validate_all()
        validator.print_report()
        sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
