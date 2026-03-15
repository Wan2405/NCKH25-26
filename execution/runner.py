"""
runner.py

Mục đích:
    Wrapper đơn giản để gọi DockerManager chạy test.
    File này giúp code gọn hơn khi cần chạy test từ nhiều nơi.

Lưu ý:
    Tất cả việc compile và chạy test đều thực hiện trong Docker,
    không bao giờ chạy trực tiếp trên máy host.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.docker_manager import DockerManager

logger = logging.getLogger(__name__)


def run_tests(docker_manager: "DockerManager", workspace_path: str) -> str:
    """
    Compile và chạy JUnit test trong Docker container.
    
    Tham số:
        docker_manager: Instance của DockerManager đã cấu hình
        workspace_path: Đường dẫn đến thư mục project Maven
    
    Trả về:
        Chuỗi log (stdout + stderr + exit code)
    """
    logger.info("run_tests: workspace=%s", workspace_path)
    return docker_manager.compile_and_test(workspace_path)
