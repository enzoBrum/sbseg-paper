# syntax=docker/dockerfile:1
#
# ---------------------------------------------------------------------------
# Stage 1: build the DSS jar from source.
#
# target/demo-0.0.1-SNAPSHOT.jar is git-ignored (not committed) and no
# mvnw wrapper exists in src/tester_scripts/library/dss/, despite
# CLAUDE.md's one-time build instructions referencing both — so build it
# fresh here with a Maven image instead of relying on a host-built jar.
# ---------------------------------------------------------------------------
FROM maven:3.9-eclipse-temurin-21 AS dss-build
WORKDIR /build

# Copy the POM first so dependency resolution is cached independently of
# source changes.
COPY src/tester_scripts/library/dss/pom.xml ./pom.xml
RUN mvn -B -q dependency:go-offline || true

COPY src/tester_scripts/library/dss/src ./src
RUN mvn -B -q package -DskipTests

# ---------------------------------------------------------------------------
# Stage 2: runtime image — Python 3.13 (uv) + JRE 21.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# JRE only — the DSS jar is already built, no JDK/Maven needed at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY . .
RUN uv sync --frozen

# Drop in the jar built in stage 1, at the exact relative path
# DSSVerifier.command expects (`java -jar target/demo-0.0.1-SNAPSHOT.jar`
# with cwd=src/tester_scripts/library/dss) — no code changes needed.
COPY --from=dss-build /build/target/demo-0.0.1-SNAPSHOT.jar \
    src/tester_scripts/library/dss/target/demo-0.0.1-SNAPSHOT.jar

ENV SBSEG_DB_PATH=/data/signed_files.db
VOLUME ["/data"]
WORKDIR /data

# Everything after the image name is passed straight to the normal CLI.
ENTRYPOINT ["uv", "run", "--project", "/app", "python", "/app/src/main.py"]
