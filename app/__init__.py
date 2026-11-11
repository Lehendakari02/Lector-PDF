"""Lector-PDF: free, offline PDF reader, study tool, form filler and signer."""

APP_NAME = "Lector-PDF"
__version__ = "0.0.1"

try:
    # Written by packaging/build.py when a Windows build is created.
    from app._build_info import BUILD_LABEL
except ImportError:
    BUILD_LABEL = ""
