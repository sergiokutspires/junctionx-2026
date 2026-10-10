"""Sensei shelf monitor: planogram compliance and stock levels from ceiling-camera images.

Submodules are imported lazily by their users (``sensei.data``, ``sensei.products``,
``sensei.features`` ...) so that the light parts work without torch installed.
"""
import logging

from .config import Config

__all__ = ["Config", "__version__"]
__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
