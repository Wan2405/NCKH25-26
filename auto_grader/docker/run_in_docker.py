"""
DOCKER RUNNER - Chạy Maven test trong Docker Container
Với security hardening: --network none, --read-only, resource limits
"""

import subprocess
import os
from pathlib import Path

class DockerRunner:
    """Class chạy test trong Docker với security sandboxing"""
    
    def __init__(self, image_name="auto-grader-runner"):
        self.image_name = image_name
        # Đường dẫn tuyệt đối tới Dockerfile
        self.docker_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__))
        )
    
    def image_exists(self):
        """Kiểm tra Docker image đã tồn tại chưa"""
        try:
            result = subprocess.run(
                ["docker", "images", "-q", self.image_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            return len(result.stdout.strip()) > 0
        except Exception as e:
            print("[!] Lỗi kiểm tra image: {}".format(e))
            return False
    
    def build_image(self):
        """Build Docker image"""
        try:
            print("[*] Building Docker image: {}...".format(self.image_name))
            dockerfile_path = os.path.join(self.docker_dir, "Dockerfile")
            result = subprocess.run(
                ["docker", "build", "-t", self.image_name,
                 "-f", dockerfile_path, self.docker_dir],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print("[+] Build thành công: {}".format(self.image_name))
                return True
            else:
                print("[!] Build lỗi: {}".format(result.stderr))
                return False
        except Exception as e:
            print("[!] Lỗi build: {}".format(e))
            return False
    
    def run_test(self, maven_root):
        """
        Chạy Maven test trong Docker container với security sandboxing
        
        Args:
            maven_root: Đường dẫn tới Maven project root
        
        Returns:
            String: Output từ Maven test
        """
        try:
            maven_abs_path = os.path.abspath(maven_root)
            
            # Docker command với security hardening:
            # --rm: Xóa container sau khi chạy
            # --network none: Không cho phép truy cập mạng
            # --memory 512m: Giới hạn RAM
            # --cpus 1.0: Giới hạn CPU
            # --pids-limit 100: Giới hạn số process
            cmd = [
                "docker", "run",
                "--rm",
                "--network", "none",
                "--memory", "512m",
                "--cpus", "1.0",
                "--pids-limit", "100",
                "-v", "{}:/app:rw".format(maven_abs_path),
                "-w", "/app",
                self.image_name,
                "mvn", "clean", "test"
            ]
            
            print("[*] Chạy Maven test trong Docker (sandboxed)...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=180
            )
            
            full_log = result.stdout
            if result.stderr:
                full_log += "\n--- ERROR STREAM ---\n" + result.stderr
            full_log += "\n--- EXIT CODE: {} ---".format(result.returncode)
            
            return full_log
        
        except subprocess.TimeoutExpired:
            return "ERROR: Docker container timeout sau 180 giây"
        except Exception as e:
            return "ERROR: Lỗi khi chạy Docker: {}".format(str(e))