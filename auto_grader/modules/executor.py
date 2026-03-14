"""
JAVA EXECUTOR (utility)
=======================
Provides :func:`extract_class_name` for extracting the public class name
from Java source code.

.. note::
   Java compilation and execution **must** be performed inside a Docker
   container via :class:`core.docker_manager.DockerManager` – never via
   ``subprocess`` on the host machine.
"""

import logging
import re

logger = logging.getLogger(__name__)


def extract_class_name(code: str) -> str:
    """Extract the public class name from Java source code.

    Falls back to the first class name found, then to ``"Solution"`` if no
    class declaration is present.
    """
    match = re.search(r"public\s+class\s+(\w+)", code)
    if match:
        return match.group(1)
    match = re.search(r"class\s+(\w+)", code)
    if match:
        return match.group(1)
    return "Solution"
