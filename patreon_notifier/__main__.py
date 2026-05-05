"""Allow ``python -m patreon_notifier``."""

from __future__ import annotations

import sys

from patreon_notifier.cli import main

if __name__ == "__main__":
    sys.exit(main())
