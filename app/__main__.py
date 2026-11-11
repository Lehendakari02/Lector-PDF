"""Allow starting the program with ``python -m app``."""

import sys

if __name__ == "__main__":
    # Imported here, not at the top: the helper process that draws the pages
    # loads this file too and must not load the whole interface.
    from app.main import main

    sys.exit(main())
