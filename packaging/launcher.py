"""Start-up script used for the packaged Windows program."""

import multiprocessing
import sys

if __name__ == "__main__":
    # Must be the first thing: when this same .exe is started as the helper
    # process that draws pages, this call runs the helper and never returns.
    multiprocessing.freeze_support()

    from app.main import main

    sys.exit(main())
