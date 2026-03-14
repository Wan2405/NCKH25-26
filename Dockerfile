# Execution container for AI-in-the-loop automated Java debugging pipeline.
# Used by DockerManager.startBuildContainer() as the build environment.
#
# Contains: JDK 17, Maven 3.9, and a pre-warmed local Maven repository to
# speed up dependency resolution in the feedback loop.
#
# Usage (manual test):
#   docker build -t nckh-build-env .
#   docker run --rm -v $(pwd)/workspace:/workspace nckh-build-env mvn clean test

FROM maven:3.9-eclipse-temurin-17

LABEL org.opencontainers.image.description="NCKH25-26 AI debug pipeline build environment"

# Pre-warm Maven dependency cache with JUnit 5 so the first run is faster
RUN mvn dependency:get \
        -Dartifact=org.junit.jupiter:junit-jupiter-api:5.10.2 \
    && mvn dependency:get \
        -Dartifact=org.junit.jupiter:junit-jupiter-engine:5.10.2 \
    && mvn dependency:get \
        -Dartifact=org.apache.maven.plugins:maven-surefire-plugin:3.2.5 \
    && rm -rf /tmp/*

WORKDIR /workspace

# Default command (overridden by DockerManager via exec)
CMD ["mvn", "clean", "test", "--batch-mode"]
