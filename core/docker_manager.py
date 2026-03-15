"""
docker_manager.py

Mục đích:
    Quản lý Docker container để compile và chạy test Java.
    Thay vì chạy trực tiếp trên máy, mình dùng Docker để đảm bảo
    môi trường giống nhau cho mọi người.

Cách hoạt động:
    1. Tạo container từ image nckh-build-env
    2. Mount thư mục workspace vào /workspace trong container
    3. Chạy lệnh mvn clean test
    4. Lấy log output và xóa container

Lưu ý:
    - Dùng Python Docker SDK, không gọi command line docker
    - Container có giới hạn RAM (512MB) và CPU để tránh treo máy
"""

from __future__ import annotations

import logging
import os

import docker
from docker.errors import APIError, DockerException, ImageNotFound

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "nckh-build-env"  # Image Docker đã build sẵn

class DockerManager:
    """
    Chạy mvn clean test trong Docker container.
    
    Các tham số:
        image: Tên Docker image (phải có Maven và JDK)
        memory_limit: Giới hạn RAM, ví dụ "512m"
        timeout: Thời gian chờ tối đa (giây) trước khi báo lỗi
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

    # === Các hàm nội bộ ===

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    # === Hàm công khai ===

    def compile_and_test(self, workspace_path: str) -> str:
        abs_path = os.path.abspath(workspace_path)
        logger.info("compile_and_test: image=%s workspace=%s", self.image, abs_path)

        container = self.client.containers.create(
            self.image,
            command="mvn clean test --batch-mode",
            volumes={abs_path: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            network_disabled=False,
            mem_limit=self.memory_limit,
            cpu_period=self.cpu_period,
            cpu_quota=self.cpu_quota,
            pids_limit=self.pids_limit,
        )
        try:
            container.start()
            result = container.wait(timeout=self.timeout)
            logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            exit_code = result.get("StatusCode", -1)
            
            # In log ra console để debug
            print("\n" + "="*70)
            print("DOCKER MAVEN OUTPUT:")
            print(logs)
            print("="*70 + "\n")
            
            return f"{logs}\n--- EXIT CODE: {exit_code} ---"
        except Exception:
            logger.exception("Error while running container")
            raise
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
