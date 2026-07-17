#!/usr/bin/env python3
"""
Get the next RC version number for the current version in pyproject.toml.

This script:
1. Reads the current version through Poetry
2. Queries PyPI API to find existing RC versions for that version
3. Returns the next RC version (e.g., if 2.2.8rc1 and 2.2.8rc2 exist, returns 2.2.8rc3)
"""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def get_version_from_poetry():
    """Get the project version through Poetry's pyproject parser."""
    result = subprocess.run(
        ["poetry", "version", "--short"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    version = result.stdout.strip()
    if not version:
        raise ValueError("Poetry returned an empty project version")
    return version


def get_pypi_versions(package_name="abejacli"):
    """Get all versions from PyPI"""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            return list(data.get("releases", {}).keys())
    except Exception as e:
        raise RuntimeError(f"Could not fetch versions from PyPI: {e}") from e


def get_next_rc_version(base_version, existing_versions):
    """Find the next RC version number"""
    # Filter versions that match the base version with rc suffix
    rc_pattern = re.compile(rf"^{re.escape(base_version)}rc(\d+)$")
    rc_numbers = []

    for version in existing_versions:
        match = rc_pattern.match(version)
        if match:
            rc_numbers.append(int(match.group(1)))

    if rc_numbers:
        next_rc = max(rc_numbers) + 1
    else:
        next_rc = 1

    return f"{base_version}rc{next_rc}"


def main():
    try:
        base_version = get_version_from_poetry()
        existing_versions = get_pypi_versions()
        next_rc_version = get_next_rc_version(base_version, existing_versions)
        print(next_rc_version, end="")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
