"""
RUNNER (execution layer)
========================
Thin wrapper that invokes DockerManager to compile and run JUnit tests.

All Java compilation and test execution happens inside a Docker container
via DockerManager – never directly on the host machine.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.docker_manager import DockerManager

logger = logging.getLogger(__name__)


def run_tests(docker_manager: "DockerManager", workspace_path: str) -> str:
    """
    Compile and run JUnit tests for the Maven project at *workspace_path*
    inside a Docker container.

    Args:
        docker_manager: A configured :class:`~core.docker_manager.DockerManager`.
        workspace_path: Local path to the Maven project root.

    Returns:
        Raw log string (stdout + stderr + exit-code trailer).
    """
    logger.info("run_tests: workspace=%s", workspace_path)
    return docker_manager.compile_and_test(workspace_path)
