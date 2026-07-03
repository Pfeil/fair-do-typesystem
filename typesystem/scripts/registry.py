"""PID registry for FDO record validation.

Resolves PIDs to PidRecords, abstracting file system details.
Validators work with pure PIDs and records, never with file paths.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

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

    def resolve_pid(self, pid: str) -> Optional[PidRecord]:
        """
        Resolve a PID to its PidRecord.

        Returns None if resolution fails (caller handles error).
        Logs resolution attempt and outcome.

        Resolution strategy:
        Appends .json, then tries common filename variations,
        like replacing slashes with underscores/dashes.
        For these filename_candidates, find all files
        recursively and return the first match.
        """
        import re

        pid_json = f"{pid}.json"

        def slash_replacements(pid: str):
            return [
                pid,
                pid.replace("/", "_"),
                pid.replace("/", "-"),
                pid.replace("/", ""),
                pid.replace("/", " "),
            ]

        possible_filenames = set(slash_replacements(pid_json))

        # find any of these in base_path
        candidates = set()
        for filename in possible_filenames:
            for file_path in self.base_path.rglob(filename):
                candidates.add(file_path)

        if len(candidates) > 1:
            self.logger.log_resolution(pid, success=False)
            self.logger.log_step(
                "Multiple candidates found", f"{len(candidates)} candidates"
            )
            return None

        if len(candidates) == 0:
            self.logger.log_resolution(pid, success=False)
            self.logger.log_step(
                "No candidates found",
                f"None of the {len(possible_filenames)} possible filenames exist: {possible_filenames}",
            )
            return None

        return self._load_record_from_file(pid, file_path)
        # Resolution failed
        self.logger.log_resolution(pid, success=False)
        return None

    def get_all_pids(self) -> set[str]:
        """Return all PIDs known to the registry."""
        pids = set()
        for file_path in self.base_path.rglob("*.json"):
            try:
                with open(file_path) as f:
                    data: Dict[str, Any] = json.load(f)
                    if any(key.startswith("0.FDO") for key in data.keys()):
                        pids.add(str(file_path.name.replace(".json", "")))
            except (json.JSONDecodeError, IOError):
                continue
        return pids

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
