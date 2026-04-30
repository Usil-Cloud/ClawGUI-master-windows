"""Deprecated — use scripts/dev/setup_perception_env.py instead.

Forwards to the new multi-tier installer with --tiers=2b so behaviour matches
the historical 2B-only install. Will be removed once all internal docs and the
test_machine_setup runbook are pinned to the new name.
"""
# Notes: docs/scripts/dev/setup_perception_env.md
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    new_script = os.path.join(here, "setup_perception_env.py")
    print("[setup_gui_owl_env] DEPRECATED — forwarding to setup_perception_env.py "
          "with --tiers=2b. Update your runbook to call the new script directly.",
          file=sys.stderr, flush=True)
    forwarded = [sys.executable, new_script, "--tiers", "2b", *sys.argv[1:]]
    sys.exit(subprocess.call(forwarded))


if __name__ == "__main__":
    main()
