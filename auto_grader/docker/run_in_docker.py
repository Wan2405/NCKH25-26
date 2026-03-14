"""
DOCKER RUNNER
=============
Runs Maven tests inside a Docker container using the Python Docker SDK.

No subprocess calls to the Docker CLI are made; all container management
goes through the ``docker`` Python library.
"""

from __future__ import annotations

import logging
import os

import docker
from docker.errors import DockerException, ImageNotFound

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "auto-grader-runner"
FALLBACK_IMAGE = "maven:3.9-eclipse-temurin-17"


class DockerRunner:
    """
    Runs ``mvn clean test`` in a Docker container via the Python Docker SDK.

    Keeps the same public interface as the legacy subprocess-based version
    so that existing callers (``auto_fixer.py``, ``full_pipeline.py``) need
    no changes.
    """

    def __init__(
        self,
        image_name: str = DEFAULT_IMAGE,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0",
        pids_limit: str = "100",
    ) -> None:
        self.image_name = image_name
        self.memory_limit = memory_limit
        # Convert cpu_limit (cores as float) to CFS quota/period values
        self.cpu_period = 100_000
        self.cpu_quota = int(float(cpu_limit) * self.cpu_period)
        self.pids_limit = int(pids_limit)
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def image_exists(self) -> bool:
        """Return True if the Docker image is available locally."""
        try:
            self.client.images.get(self.image_name)
            return True
        except ImageNotFound:
            return False
        except DockerException as exc:
            logger.warning("Could not check image '%s': %s", self.image_name, exc)
            return False

    def build_image(self) -> bool:
        """Build the Docker image from the Dockerfile in this directory."""
        dockerfile_dir = os.path.dirname(os.path.abspath(__file__))
        try:
            logger.info("Building Docker image: %s", self.image_name)
            _, logs = self.client.images.build(
                path=dockerfile_dir,
                tag=self.image_name,
                rm=True,
            )
            for chunk in logs:
                if "stream" in chunk:
                    logger.debug("BUILD: %s", chunk["stream"].rstrip())
            logger.info("Image built successfully: %s", self.image_name)
            return True
        except DockerException as exc:
            logger.error("Image build failed: %s", exc)
            return False

    def run_test(self, maven_root: str) -> str:
        """
        Run ``mvn clean test`` inside a Docker container.

        Args:
            maven_root: Local path to the Maven project to test.

        Returns:
            Combined stdout + stderr string with an exit-code trailer line.
        """
        # Auto-build if the image is not present
        if not self.image_exists():
            logger.info("Image '%s' not found, attempting to build …", self.image_name)
            if not self.build_image():
                logger.warning(
                    "Build failed; falling back to image '%s'", FALLBACK_IMAGE
                )
                self.image_name = FALLBACK_IMAGE

        abs_path = os.path.abspath(maven_root)
        logger.info("run_test: image=%s path=%s", self.image_name, abs_path)

        container = self.client.containers.create(
            self.image_name,
            command="mvn clean test",
            volumes={abs_path: {"bind": "/app", "mode": "rw"}},
            working_dir="/app",
            network_disabled=True,
            mem_limit=self.memory_limit,
            cpu_period=self.cpu_period,
            cpu_quota=self.cpu_quota,
            pids_limit=self.pids_limit,
        )
        try:
            container.start()
            result = container.wait(timeout=180)
            logs = container.logs(stdout=True, stderr=True).decode(
                "utf-8", errors="ignore"
            )
            exit_code = result.get("StatusCode", -1)
            return f"{logs}\n--- EXIT CODE: {exit_code} ---"
        except Exception as exc:
            logger.error("Container error: %s", exc)
            return f"ERROR: {exc}\n--- EXIT CODE: -1 ---"
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass


def get_docker_runner(**kwargs) -> DockerRunner:
    """Factory function for convenience."""
    return DockerRunner(**kwargs)
