"""Deprecated — use scripts/dev/run_gui_owl.py instead.

Forwards to the new multi-tier wrapper with --default-tier=2b --pin so the
historical 2B-only behaviour is preserved. Will be removed once docs and the
test_machine_setup runbook reference run_gui_owl.py directly.
"""
# Notes: docs/scripts/dev/run_gui_owl.md
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    new_script = os.path.join(here, "run_gui_owl.py")
    print("[run_gui_owl_2b] DEPRECATED — forwarding to run_gui_owl.py with "
          "--default-tier=2b --pin. Update your runbook to call the new script directly.",
          file=sys.stderr, flush=True)
    forwarded = [sys.executable, new_script,
                 "--default-tier=2b", "--pin", *sys.argv[1:]]
    sys.exit(subprocess.call(forwarded))


if __name__ == "__main__":
    main()
