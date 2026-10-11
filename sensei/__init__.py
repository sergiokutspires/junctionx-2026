"""Fresh Eyes shelf monitor (team QuantumLotus, JunctionX Lisbon 2026, Sensei challenge).

Reads ceiling-camera images of a produce section and, for every planogram area, answers the stock
level (empty / half / full) and whether the planned product is there. ``python -m sensei --help`` lists
the commands. Submodules are imported lazily by their users (``sensei.data``, ``sensei.products``,
``sensei.features`` ...) so that the light parts work without torch installed.
"""
import logging

from .config import Config

__all__ = ["Config", "__version__"]
__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
