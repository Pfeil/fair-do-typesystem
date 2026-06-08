"""PID registry for FDO record validation.

Resolves PIDs to PidRecords, abstracting file system details.
Validators work with pure PIDs and records, never with file paths.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

try:
    # When imported as a package
    from .models import PidRecord
    from .validation_logger import ValidationLogger
except ImportError:
    # When run directly
    from models import PidRecord
    from validation_logger import ValidationLogger


class PidRegistry:
    """Resolves PIDs to PidRecords using a local registry.json mapping.

    Hides file system details from validators. In production, this would
    resolve actual PIDs via the Handle System or other PID infrastructure.

    For local development, uses registry.json to map PIDs to file paths.
    No caching - each resolution is performed fresh (worst-case analysis).

    Usage:
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        record = registry.resolve_pid("0.FDO/ProfileDef")
        if record:
            print(f"Resolved: {record.pid}")
    """

    def __init__(self, logger: ValidationLogger) -> None:
        self.logger: ValidationLogger = logger
        self.base_path: Path = Path(__file__).parent.parent
        self.registry: Dict[str, str] = self._load_registry()

    def _load_registry(self) -> Dict[str, str]:
        """Load the registry.json file that maps PIDs to file paths."""
        registry_path: Path = self.base_path / "registry.json"
        if not registry_path.exists():
            raise FileNotFoundError(f"registry.json not found at {registry_path}")

        with open(registry_path) as f:
            data: Dict[str, object] = json.load(f)
            return data.get("entries", {})

    def resolve_pid(self, pid: str) -> Optional[PidRecord]:
        """
        Resolve a PID to its PidRecord.

        Returns None if resolution fails (caller handles error).
        Logs resolution attempt and outcome.

        Resolution strategy:
        1. Check registry.json for known PID
        2. Try as relative path from base_path
        3. Try common variations (prefixes, suffixes)

        Args:
            pid: The PID to resolve (e.g., "0.FDO/ProfileDef")

        Returns:
            PidRecord if successful, None otherwise
        """
        # Strategy 1: Check registry.json
        if pid in self.registry:
            file_path: Path = self.base_path / self.registry[pid]
            if file_path.exists():
                return self._load_record_from_file(pid, file_path)

        # Strategy 2: Try as relative path
        direct_path: Path = self.base_path / pid
        if direct_path.exists():
            return self._load_record_from_file(pid, direct_path)

        # Strategy 3: Try common variations
        for suffix in [".json", ""]:
            for prefix in ["", "core/", "attributes/", "syntax/", "examples/"]:
                test_path: Path = self.base_path / f"{prefix}{pid}{suffix}"
                if test_path.exists():
                    return self._load_record_from_file(pid, test_path)

        # Resolution failed
        self.logger.log_resolution(pid, success=False)
        return None

    def _load_record_from_file(self, pid: str, file_path: Path) -> Optional[PidRecord]:
        """Load a JSON file and wrap it as a PidRecord."""
        try:
            with open(file_path) as f:
                data: Dict[str, Any] = json.load(f)

            # Use the file path relative to base_path for logging
            target: str
            try:
                target = str(file_path.relative_to(self.base_path))
            except ValueError:
                target = str(file_path)

            self.logger.log_resolution(pid, success=True, target=target)

            return PidRecord(pid=pid, data=data, source_pid=pid)
        except (json.JSONDecodeError, IOError) as e:
            self.logger.log_resolution(pid, success=False)
            self.logger.log_step("Error", f"Failed to load {file_path}: {e}")
            return None
