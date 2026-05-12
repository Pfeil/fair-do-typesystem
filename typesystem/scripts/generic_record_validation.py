# A tool to validate FDO records that are part of or using the FDO type system.
#
# CLI usage: python generic_record_validation.py [--verbose] <file_paths ...>
#
# Implementation rules and requirements:
# - Use typing. Especially for function signatures and return types.
# - No caching: We want this tool to analyze worst case scenarios (for now).
#   Also, we want to keep it simple and avoid unnecessary optimizations.
# - Modular design: Make functionalities extensible and reusable.
#   We might want to use it as a library in the future or exchange implementations.
#   We might want to exchange parts of the implementations for experiments.
# - Consistent logging: A custom logging class gives full control over
#   when, what, and how to log progress and (intermediate) results.
# - Logging is not for debugging, but for understanding validation failure and success.
# - The --verbose parameter enables information beyond the final
#   result per record (intermediate steps).
# - After validation of one record, there will be a summary of the results,
#   e.g. the number of resolutions for profile validation, and others.
# - Validation works with the pure records, and with pure PIDs.
#   Hide the fact that we use files to store the records from it.
#   Hide file paths from the validation at all costs.
#   This must be fully hidden using the PidRegistry etc.
# - DRY: Don't Repeat Yourself. Don't write the same code multiple times.
# - Do not hard code information that is available in records.
#   Always fetch it from the records themselves.
#   This will be useful for efficiency analysis.
# - Keep the different kinds of validation separate.
# - Keep the code easy to read and review.
#

import json

# import os
# import re
# import sys
from pathlib import Path
from typing import Dict, Optional


# Represents a resolved PID record.
class PidRecord:
    pass  # TODO implement


# Class hiding the fact that we use files to store the records.
class FileSystemAbstraction:
    def path_to_pid(self, path: Path) -> Optional[str]:
        pass  # TODO implement


# Allows resolving PIDs to their records.
class PidRegistry:
    def __init__(self, verbose: bool = True):
        self.base_path = Path(__file__).parent.parent
        self.verbose = verbose
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, str]:
        """Load the registry.json file."""
        registry_path = self.base_path / "registry.json"
        if not registry_path.exists():
            raise FileNotFoundError(f"registry.json not found at {registry_path}")

        with open(registry_path) as f:
            data = json.load(f)
            result = data.get("entries", {})
            # TODO actually log(f"Loaded registry with {len(result)} entries", 1)
            return result

    def _resolve_reference(self, ref: str) -> Optional[Path]:
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

    def resolve_pid(self, pid) -> PidRecord:
        return PidRecord()  # TODO implement


def main():
    # 1. Hide file paths by translating them to PIDs.

    # TODO Attribute validation:
    # - for each attribute (attribute definition + value)
    # - resolve attribute definition and all sub-parts recursively
    # - validate those sub-parts also
    # - collect all information required for validation of the value
    # - validate the value using the collected information

    # TODO Profile validation
    # - resolve profile definition and all sub-parts (extends, profiles) recursively
    # - use this information to validate the given record (e.g. presence of mandatory attributes)

    # TODO Specification check
    # - Check if the record conforms to the specification,
    #   e.g. if it relates to the core profiles properly and similar things
    #   that are not yet covered by the previous validations.
    pass


if __name__ == "__main__":
    main()
