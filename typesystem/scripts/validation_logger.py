"""Structured logging for FDO record validation.

Logging is not for debugging, but for understanding validation outcomes.
Uses phases instead of severity levels to show validation flow.
"""

from typing import List, Optional


class ValidationLogger:
    """Structured logger for validation progress and results.

    Features:
    - Phase-based logging (Specification, Profile, Attribute)
    - Indentation tracks validation depth
    - Resolution counting shows complexity
    - Summary per record for clear reporting

    Usage:
        logger = ValidationLogger(verbose=True)
        logger.log_phase("Profile", "0.FDO/Root")
        logger.log_step("Resolution", "Resolved 0.FDO/ProfileDef")
        logger.print_summary("0.FDO/Root", valid=True, errors=[], warnings=[])
    """

    def __init__(self, verbose: bool = False) -> None:
        self.verbose: bool = verbose
        self.indent_level: int = 0
        self.resolution_count: int = 0
        self._record_pid: Optional[str] = None

    def reset_for_record(self, record_pid: str) -> None:
        """Reset logger state for a new record being validated."""
        self._record_pid = record_pid
        self.indent_level = 0
        self.resolution_count = 0

    def log_phase(self, phase: str, message: str) -> None:
        """Log a major validation phase (always shown)."""
        print(f"\n{phase}: {message}")

    def log_step(self, step: str, message: str, indent: int = 0) -> None:
        """Log a validation step within a phase (only in verbose mode)."""
        if self.verbose:
            prefix: str = "  " * (self.indent_level + indent)
            print(f"{prefix}{step}: {message}")

    def log_resolution(
        self, pid: str, success: bool, target: Optional[str] = None
    ) -> None:
        """Log a PID resolution event and increment counter."""
        self.resolution_count += 1
        if self.verbose:
            status: str = "✓" if success else "✗"
            target_info: str = f" → {target}" if target else ""
            print(f"  {status} Resolved {pid}{target_info}")

    def enter_context(self) -> None:
        """Increase indent for nested validation (e.g., entering profile chain)."""
        self.indent_level += 1

    def exit_context(self) -> None:
        """Decrease indent after nested validation completes."""
        if self.indent_level > 0:
            self.indent_level -= 1

    def print_summary(
        self, record_pid: str, valid: bool, errors: List[str], warnings: List[str]
    ) -> None:
        """Print summary after validating one record."""
        status_icon: str = "✅" if valid else "❌"
        print(f"\n{status_icon} {record_pid}")
        print(f"  Resolutions performed: {self.resolution_count}")

        if errors or warnings:
            print(f"  Errors: {len(errors)}, Warnings: {len(warnings)}")
        else:
            print(f"  ✅ All checks passed")

    def get_resolution_count(self) -> int:
        """Get the number of resolutions performed for current record."""
        return self.resolution_count
