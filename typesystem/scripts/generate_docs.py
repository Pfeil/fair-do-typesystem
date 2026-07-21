#!/usr/bin/env python3
"""Generate self-contained HTML documentation for FDO PIDs."""

import json
import re
from html import escape
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import PidRecord
from registry import PidRegistry
from validation_logger import ValidationLogger


def normalize_pid(pid: str) -> str:
    """Normalize PID format: replace dashes with slashes where appropriate.

    Examples:
        "0-FDO-Profile" -> "0.FDO/Profile"
        "0.FDO/Profile" -> "0.FDO/Profile" (unchanged)
        "example-miniFDO" -> "example/miniFDO"
    """
    # Replace dashes with slashes for PID segments
    return re.sub(r"([A-Za-z0-9])-([A-Za-z0-9])", r"\1/\2", pid)


def is_included_pid(pid: str) -> bool:
    """Check if PID should be included in documentation.

    Includes:
    - All PIDs starting with "0.FDO/"
    - The example PID "example/miniFDO"
    """
    return pid.startswith("0.FDO/") or pid == "example/miniFDO"


def format_value(value: object) -> str:
    """Format a value for HTML display."""
    if isinstance(value, (dict, list)):
        return escape(json.dumps(value, indent=2))
    return escape(str(value))


def extract_description(record: PidRecord) -> str | None:
    """Extract description text from a record's 0.FDO/Description field."""
    desc = record.data.get("0.FDO/Description")
    if desc is None:
        return None

    # Handle list: take first element (descriptions can be repeated)
    if isinstance(desc, list):
        desc = desc[0] if desc else None
        if desc is None:
            return None

    # Handle structured description: {"0.FDO/StringSyntax": "..."} or {"0.FDO/StringValue": "..."}
    if isinstance(desc, dict):
        return desc.get("0.FDO/StringSyntax") or desc.get("0.FDO/StringValue")

    # Handle plain string description
    return str(desc)


def generate_docs() -> None:
    """Generate HTML documentation for all FDO PIDs."""

    # Setup
    logger = ValidationLogger(verbose=False)
    registry = PidRegistry(logger)

    # Discover all PIDs
    all_pids = registry.get_all_pids()

    # Resolve all records and collect descriptions
    # We need two passes: first resolve all records, then extract descriptions
    raw_records: dict[str, PidRecord] = {}
    for pid in all_pids:
        record = registry.resolve_pid(pid)
        if record:
            raw_records[pid] = record

    # Build description map: attr_pid -> description text
    # Use normalized PIDs as keys for lookup in template
    attribute_descriptions: dict[str, str] = {}
    for pid, record in raw_records.items():
        normalized = normalize_pid(pid)
        desc = extract_description(record)
        if desc:
            attribute_descriptions[normalized] = desc

    # Filter and normalize PIDs for output
    records: dict[str, PidRecord] = {}
    for pid, record in raw_records.items():
        normalized = normalize_pid(pid)
        if not is_included_pid(normalized):
            continue
        records[normalized] = record

    # Setup Jinja2
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["format_value"] = format_value

    # Render template
    template = env.get_template("docs.html.j2")
    html = template.render(
        records=records,
        attribute_descriptions=attribute_descriptions,
    )

    # Write output to ./docs/overview.html
    output_dir = Path(__file__).parent.parent.parent / "docs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "overview.html"
    output_path.write_text(html)
    print(f"Generated: {output_path.resolve()}")


def main() -> None:
    """Entry point for the fdo-generate-docs command."""
    generate_docs()


if __name__ == "__main__":
    main()
