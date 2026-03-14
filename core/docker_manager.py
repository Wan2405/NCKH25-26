"""
DOCKER MANAGER
==============
Manages Docker containers for Java compilation and JUnit testing.

Uses the Python Docker SDK exclusively – never calls the Docker CLI via
subprocess on the host machine.
"""

from __future__ import annotations

import logging
import os

import docker
from docker.errors import APIError, DockerException, ImageNotFound

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "maven:3.9-eclipse-temurin-17"


class DockerManager:
    """
    Runs ``mvn clean test --batch-mode`` inside a sandboxed Docker container.

    Args:
        image:        Docker image to use (must include Maven and a JDK).
        memory_limit: Container memory cap (e.g. ``"512m"``).
        cpu_period:   CFS scheduler period in microseconds (default 100 000).
        cpu_quota:    CFS quota in microseconds; equals ``cpu_period`` for
                      exactly 1 CPU.
        pids_limit:   Maximum number of processes inside the container.
        timeout:      Seconds to wait for the container to finish before
                      raising an exception.
    """

    def __init__(
        self,
        image: str = DEFAULT_IMAGE,
        memory_limit: str = "512m",
        cpu_period: int = 100_000,
        cpu_quota: int = 100_000,
        pids_limit: int = 100,
        timeout: int = 180,
    ) -> None:
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_period = cpu_period
        self.cpu_quota = cpu_quota
        self.pids_limit = pids_limit
        self.timeout = timeout
        self._client: docker.DockerClient | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compile_and_test(self, workspace_path: str) -> str:
        """
        Mount *workspace_path* into a container and run::

            mvn clean test --batch-mode

        The Maven project must already exist at *workspace_path* (a valid
        ``pom.xml`` is expected at the root of that directory).

        Returns:
            Combined stdout + stderr from the container followed by a
            ``--- EXIT CODE: N ---`` trailer line.

        Raises:
            docker.errors.ImageNotFound  if the image is missing.
            docker.errors.APIError       on any other Docker API error.
        """
        abs_path = os.path.abspath(workspace_path)
        logger.info("compile_and_test: image=%s workspace=%s", self.image, abs_path)

        container = self.client.containers.create(
            self.image,
            command="mvn clean test --batch-mode",
            volumes={abs_path: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            network_disabled=True,
            mem_limit=self.memory_limit,
            cpu_period=self.cpu_period,
            cpu_quota=self.cpu_quota,
            pids_limit=self.pids_limit,
        )
        try:
            container.start()
            result = container.wait(timeout=self.timeout)
            logs = container.logs(stdout=True, stderr=True).decode(
                "utf-8", errors="replace"
            )
            exit_code = result.get("StatusCode", -1)
            return f"{logs}\n--- EXIT CODE: {exit_code} ---"
        except Exception:
            logger.exception("Error while running container")
            raise
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
