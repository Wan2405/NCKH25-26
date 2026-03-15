# Dockerfile - Môi trường thực thi cho pipeline sửa lỗi Java tự động
#
# Mục đích:
#     Tạo Docker image chứa JDK và Maven để compile và chạy test Java.
#     DockerManager sẽ dùng image này để chạy mvn test.
#
# Nội dung:
#     - JDK 17 (Eclipse Temurin)
#     - Maven 3.9
#     - JUnit 5 dependencies (pre-download để chạy nhanh hơn)
#
# Cách build thủ công:
#     docker build -t nckh-build-env .
#
# Cách test thủ công:
#     docker run --rm -v $(pwd)/workspace:/workspace nckh-build-env mvn clean test

FROM maven:3.9-eclipse-temurin-17

LABEL org.opencontainers.image.description="NCKH25-26 AI debug pipeline build environment"

# Pre-download các dependency JUnit 5 để lần chạy đầu tiên nhanh hơn
# (Maven sẽ cache trong /root/.m2 thay vì download mỗi lần)
RUN mvn dependency:get \
        -Dartifact=org.junit.jupiter:junit-jupiter-api:5.10.2 \
    && mvn dependency:get \
        -Dartifact=org.junit.jupiter:junit-jupiter-engine:5.10.2 \
    && mvn dependency:get \
        -Dartifact=org.apache.maven.plugins:maven-surefire-plugin:3.2.5 \
    && rm -rf /tmp/*

WORKDIR /workspace

# Lệnh mặc định (có thể bị override bởi DockerManager)
CMD ["mvn", "clean", "test", "--batch-mode"]
