"""Nox sessions for MandiIQ.

Usage:
    nox -s validate-northflank   # Validate Dockerfile.cronjob vs NORTHFLANK_DEPLOY.md
    nox -s install-hooks         # Install git pre-push hook (one-time setup)
    nox -l                       # List all available sessions

First-time setup:
    pip install nox
    nox -s install-hooks      # installs pre-push hook

After that, `git push` will auto-run validate-northflank.
"""

import nox
from pathlib import Path


@nox.session(python=False)
def validate_northflank(session: nox.Session) -> None:
    """Validate Dockerfile.cronjob vs NORTHFLANK_DEPLOY.md for consistency."""
    session.run("python", "scripts/validate_northflank_config.py")


@nox.session(python=False)
def install_hooks(session: nox.Session) -> None:
    """Install git pre-push hook that runs validate-northflank before every push."""
    dot_git = Path(".git")
    if not dot_git.is_dir():
        session.error(".git directory not found — are you in the project root?")

    hooks_dir = dot_git / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "pre-push"
    if hook_path.exists():
        session.log("⚠️  Existing hook found at %s — overwriting", hook_path)

    hook_script = """#!/bin/sh
# MandiIQ pre-push hook — installed by nox -s install-hooks
# Runs the Northflank config validator before every push.
# To skip: git push --no-verify

echo "=== validate-northflank ==="
python -m nox -s validate-northflank 2>&1 || {
    echo "❌ Northflank config validation failed."
    echo "   If nox is not installed: pip install nox"
    echo "   To skip: git push --no-verify"
    exit 1
}
"""

    hook_path.write_text(hook_script.lstrip())
    hook_path.chmod(0o755)
    session.log("✅ Pre-push hook installed at %s", hook_path)
    session.log("   It will run 'python -m nox -s validate-northflank' before every push.")
    session.log("   To skip temporarily: git push --no-verify")
