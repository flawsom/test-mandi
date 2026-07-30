#!/usr/bin/env python3
"""
validate_northflank_config.py -- Pre-deploy validation for both Northflank Dockerfiles.

Cross-checks for each Dockerfile (cronjob + API server):
  1. Every COPY source exists on disk.
  2. Every ENV var is documented in NORTHFLANK_DEPLOY.md.
  3. Volume mount path (/data) is consistent between Dockerfile and deploy docs.

Usage:
    python scripts/validate_northflank_config.py

Exit codes:
    0  -- all checks pass
    1  -- one or more checks failed (details printed to stdout)
"""

import re
import sys
from pathlib import Path

# -- Paths (relative to project root) --
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILES = [
    ("Cron job (hourly ingestion)", "Dockerfile.cronjob"),
    ("API server (uvicorn)",         "Dockerfile.northflank"),
]
DEPLOY_DOC = PROJECT_ROOT / "NORTHFLANK_DEPLOY.md"

errors: list[str] = []

def err(msg: str) -> None:
    errors.append(msg)
    print(f"  X  {msg}")

def ok(msg: str) -> None:
    print(f"  V  {msg}")


# ---------------------------------------------------------------------------
# 1. Parse COPY instructions from Dockerfile
# ---------------------------------------------------------------------------
def parse_copy_sources(path: Path) -> list[str]:
    """Return every source path appearing in a COPY instruction."""
    sources: list[str] = []
    copy_re = re.compile(r"^\s*COPY\s+(\S+)\s", re.MULTILINE)
    for m in copy_re.finditer(path.read_text(encoding="utf-8")):
        src = m.group(1)
        if src.endswith("/"):
            src = src[:-1]
        sources.append(src)
    return sources


# ---------------------------------------------------------------------------
# 2. Parse ENV directives from Dockerfile
# ---------------------------------------------------------------------------
def parse_env_vars(path: Path) -> dict[str, str]:
    """Return {VAR_NAME: value} from ENV lines."""
    env: dict[str, str] = {}
    env_re = re.compile(r"^\s*ENV\s+(\w+)=(.*)", re.MULTILINE)
    for m in env_re.finditer(path.read_text(encoding="utf-8")):
        env[m.group(1)] = m.group(2).strip()
    return env


# ---------------------------------------------------------------------------
# 3. Parse env var names from NORTHFLANK_DEPLOY.md
# ---------------------------------------------------------------------------
def parse_documented_env_vars(path: Path) -> set[str]:
    """Return set of env var names mentioned in the deploy doc."""
    text = path.read_text(encoding="utf-8")
    vars_found: set[str] = set()

    # Match `- VAR_NAME=` or `- VAR_NAME (optional)` in bullet lists
    bullet_re = re.compile(r"^\s*[-*]\s+(\w+)(?:\s*=?\s*|$)", re.MULTILINE)
    for m in bullet_re.finditer(text):
        name = m.group(1)
        if name.upper() == name and not name.endswith(":"):
            vars_found.add(name)

    # Also match commented-out bullets `# - VAR_NAME`
    comment_bullet_re = re.compile(r"^\s*#\s*[-*]\s+(\w+)", re.MULTILINE)
    for m in comment_bullet_re.finditer(text):
        name = m.group(1)
        if name.upper() == name and not name.endswith(":"):
            vars_found.add(name)

    return vars_found


# ---------------------------------------------------------------------------
# 4. Parse volume mount info from deploy doc
# ---------------------------------------------------------------------------
def parse_volume_mount(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"Mount path:\s*(\S+)", text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# 5. Validate a single Dockerfile against the deploy doc
# ---------------------------------------------------------------------------
def validate_dockerfile(
    label: str,
    df_path: Path,
    doc_env: set[str],
    expected_mount: str | None,
) -> None:
    """Run all checks for one Dockerfile."""
    name = df_path.name

    if not df_path.is_file():
        err(f"[{name}] File not found: {df_path.relative_to(PROJECT_ROOT)}")
        return

    # -- Check A: COPY sources exist --
    copy_sources = parse_copy_sources(df_path)
    if not copy_sources:
        err(f"[{name}] No COPY instructions found")
    for src in copy_sources:
        disk_path = PROJECT_ROOT / src
        if disk_path.exists():
            ok(f"[{label}] COPY {src}")
        else:
            err(f"[{label}] COPY {src} -> NOT FOUND at {disk_path}")

    # -- Check B: ENV vars are documented --
    docker_env = parse_env_vars(df_path)
    for var_name in docker_env:
        if var_name in doc_env:
            ok(f"[{label}] ENV {var_name}={docker_env[var_name]}")
        else:
            err(
                f"[{label}] ENV {var_name}={docker_env[var_name]}"
                " -> NOT DOCUMENTED in NORTHFLANK_DEPLOY.md"
            )

    # -- Check C: Volume mount path --
    df_text = df_path.read_text(encoding="utf-8")
    if "/data" in df_text:
        ok(f"[{label}] References /data volume")
    else:
        err(f"[{label}] Does NOT reference /data anywhere")

    if expected_mount == "/data":
        ok(f"[{label}] NORTHFLANK_DEPLOY.md mount path matches: {expected_mount}")
    else:
        err(f"[{label}] Mount path mismatch: expected /data, got {expected_mount}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    # Force UTF-8 output on Windows consoles that default to cp1252
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

    print("\n  == Northflank config validation ==\n")
    print(f"  Project root: {PROJECT_ROOT}\n")

    # -- Check deploy doc exists --
    if not DEPLOY_DOC.is_file():
        err(f"Required file not found: {DEPLOY_DOC.relative_to(PROJECT_ROOT)}")
        print(f"\n  X  {len(errors)} error(s) -- aborting\n")
        return 1

    doc_env = parse_documented_env_vars(DEPLOY_DOC)
    expected_mount = parse_volume_mount(DEPLOY_DOC)

    # -- Validate each Dockerfile --
    for label, df_name in DOCKERFILES:
        df_path = PROJECT_ROOT / df_name
        header = f"  == {label} ({df_name}) =="
        print(f"\n{header}\n")
        validate_dockerfile(label, df_path, doc_env, expected_mount)

    # -- Final verdict --
    print("\n  == Summary ==\n")
    if errors:
        print(f"  X  {len(errors)} error(s) found:\n")
        for e in errors:
            print(f"     {e}")
        print()
        return 1
    else:
        print(
            "  V  All checks passed"
            " -- both Dockerfiles consistent with NORTHFLANK_DEPLOY.md.\n"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
