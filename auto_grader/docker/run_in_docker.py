"""
run_in_docker.py

Mục đích:
    Chạy Maven test trong Docker container sử dụng Python Docker SDK.
    KHÔNG gọi command line docker mà dùng thư viện docker-py.

Cách hoạt động:
    1. Kiểm tra Docker image có sẵn chưa
    2. Nếu chưa có → Build từ Dockerfile
    3. Tạo container với giới hạn RAM/CPU
    4. Mount thư mục Maven project vào container
    5. Chạy mvn clean test và lấy log

Lưu ý:
    - Container bị giới hạn tài nguyên để tránh treo máy
    - Container tự động xóa sau khi chạy xong
"""

from __future__ import annotations

import logging
import os

import docker
from docker.errors import DockerException, ImageNotFound

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "auto-grader-runner"   # Image mặc định (build từ Dockerfile)
FALLBACK_IMAGE = "maven:3.9-eclipse-temurin-17"  # Image backup nếu build thất bại


class DockerRunner:
    """
    Chạy mvn clean test trong Docker container.
    
    Tham số:
        image_name: Tên Docker image
        memory_limit: Giới hạn RAM (vd: "512m")
        cpu_limit: Số CPU (vd: "1.0")
        pids_limit: Số process tối đa trong container
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
        
        # Chuyển cpu_limit (số cores) sang CFS quota/period
        # Ví dụ: cpu_limit=1.0 nghĩa là dùng 1 CPU
        self.cpu_period = 100_000
        self.cpu_quota = int(float(cpu_limit) * self.cpu_period)
        self.pids_limit = int(pids_limit)
        self._client: docker.DockerClient | None = None

    @property
    def client(self) -> docker.DockerClient:
        """Lazy init Docker client (chỉ tạo khi cần)."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def image_exists(self) -> bool:
        """Kiểm tra Docker image có sẵn trên máy chưa."""
        try:
            self.client.images.get(self.image_name)
            return True
        except ImageNotFound:
            return False
        except DockerException as exc:
            logger.warning("Could not check image '%s': %s", self.image_name, exc)
            return False

    def build_image(self) -> bool:
        """Build Docker image từ Dockerfile trong thư mục này."""
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
        Chạy mvn clean test trong Docker container.

        Tham số:
            maven_root: Đường dẫn đến thư mục Maven project.

        Trả về:
            Chuỗi log (stdout + stderr) kèm exit code.
        """
        # Nếu image chưa có → Build hoặc dùng fallback
        if not self.image_exists():
            logger.info("Image '%s' not found, attempting to build …", self.image_name)
            if not self.build_image():
                logger.warning(
                    "Build failed; falling back to image '%s'", FALLBACK_IMAGE
                )
                self.image_name = FALLBACK_IMAGE

        abs_path = os.path.abspath(maven_root)
        logger.info("run_test: image=%s path=%s", self.image_name, abs_path)

        # Tạo container với các giới hạn tài nguyên
        container = self.client.containers.create(
            self.image_name,
            command="mvn clean test",
            volumes={abs_path: {"bind": "/app", "mode": "rw"}},  # Mount project
            working_dir="/app",
            network_disabled=True,  # Không cho truy cập mạng
            mem_limit=self.memory_limit,  # Giới hạn RAM
            cpu_period=self.cpu_period,
            cpu_quota=self.cpu_quota,  # Giới hạn CPU
            pids_limit=self.pids_limit,  # Giới hạn số process
        )
        try:
            # Chạy container và đợi kết quả (timeout 180s)
            container.start()
            result = container.wait(timeout=180)
            # Lấy log và exit code
            logs = container.logs(stdout=True, stderr=True).decode(
                "utf-8", errors="ignore"
            )
            exit_code = result.get("StatusCode", -1)
            return f"{logs}\n--- EXIT CODE: {exit_code} ---"
        except Exception as exc:
            logger.error("Container error: %s", exc)
            return f"ERROR: {exc}\n--- EXIT CODE: -1 ---"
        finally:
            # Luôn dọn dẹp container sau khi chạy xong
            try:
                container.remove(force=True)
            except Exception:
                pass


def get_docker_runner(**kwargs) -> DockerRunner:
    """Factory function để tạo DockerRunner với config tùy chỉnh."""
    return DockerRunner(**kwargs)
