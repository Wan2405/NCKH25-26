"""
DOCKER RUNNER - Chạy Maven test trong Docker Container
"""

import subprocess
import os
from pathlib import Path

class DockerRunner:
    """Class chạy test trong Docker"""
    
    def __init__(self, image_name="auto-grader-runner"):
        self.image_name = image_name
        self.docker_file = "auto_grader/docker/Dockerfile"
    
    def image_exists(self):
        """Kiểm tra Docker image đã tồn tại chưa"""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.image_name],
                capture_output=True,
                text=True
            )
            return len(result.stdout.strip()) > 0
        except Exception as e:
            print(f"[!] Lỗi kiểm tra image: {e}")
            return False
    
    def build_image(self):
        """Build Docker image"""
        try:
            print(f"[*] Building Docker image: {self.image_name}...")
            result = subprocess.run(
                ["docker", "build", "-t", self.image_name, "-f", self.docker_file, "."],
                cwd="auto_grader/docker",
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"[+] Build thành công: {self.image_name}")
                return True
            else:
                print(f"[!] Build lỗi: {result.stderr}")
                return False
        except Exception as e:
            print(f"[!] Lỗi build: {e}")
            return False
    
    def run_test(self, maven_root):
        """
        Chạy Maven test trong Docker container
        
        Args:
            maven_root: Đường dẫn tới Maven project root
        
        Returns:
            String: Output từ Maven test
        """
        try:
            # Đường dẫn tuyệt đối
            maven_abs_path = os.path.abspath(maven_root)
            
            # Lệnh chạy Docker
            # Mount Maven project vào /app trong container, rồi chạy Maven test
            cmd = [
                "docker", "run",
                "--rm",  # Xóa container sau khi chạy
                "-v", f"{maven_abs_path}:/app",  # Mount volume
                "-w", "/app",  # Working directory trong container
                self.image_name,  # Image name
                "mvn", "clean", "test"  # Command
            ]
            
            print(f"[*] Chạy Maven test trong Docker...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            # Kết hợp stdout + stderr
            full_log = result.stdout
            if result.stderr:
                full_log += "\n--- DOCKER STDERR ---\n" + result.stderr
            
            full_log += f"\n--- DOCKER EXIT CODE: {result.returncode} ---"
            
            return full_log
        
        except Exception as e:
            return f"ERROR: Lỗi khi chạy Docker: {str(e)}"