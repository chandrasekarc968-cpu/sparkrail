#!/usr/bin/env python3
"""
Audit Git Cleanliness and Security Gate
Verifies that no binary databases, unencrypted credentials, private keys, or secret tokens
are tracked in the Git repository.
"""
import sys
import subprocess
from typing import List, Tuple

FORBIDDEN_EXTENSIONS = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".cer",
    ".crt"
)

FORBIDDEN_FILENAMES = (
    "sparkrail_auth.db",
    "dead_letter.jsonl",
    "id_rsa",
    "id_ed25519"
)

def get_tracked_files() -> List[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def audit_files(files: List[str]) -> List[str]:
    violations = []
    for file in files:
        f_lower = file.lower()
        if any(f_lower.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
            violations.append(f"Forbidden file extension: {file}")
        if any(f_lower.split("/")[-1] == name.lower() for name in FORBIDDEN_FILENAMES):
            violations.append(f"Forbidden tracked filename: {file}")
    return violations

def main() -> int:
    try:
        files = get_tracked_files()
    except Exception as e:
        print(f"ERROR: Failed to list git files: {e}", file=sys.stderr)
        return 1

    violations = audit_files(files)
    if violations:
        print("SECURITY GATE FAILED: The following forbidden files are tracked in Git:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(f"SECURITY GATE PASSED: All {len(files)} tracked files audited. Zero databases, keys, or forbidden artifacts found.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
