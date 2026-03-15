# Dockerfile cho auto_grader
# Image đơn giản với Maven và JDK để chạy test
# Dùng bởi DockerRunner trong run_in_docker.py

FROM maven:3.8.6-openjdk-11-slim

WORKDIR /app

COPY . /app/

# Lệnh mặc định: chạy Maven test
CMD ["mvn", "clean", "test"]
