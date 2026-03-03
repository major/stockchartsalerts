FROM docker.io/library/python:3.14@sha256:61346539f7b26521a230e72c11da5ebd872924745074b19736e7d65ba748c366
COPY --from=ghcr.io/astral-sh/uv:0.10.8@sha256:88234bc9e09c2b2f6d176a3daf411419eb0370d450a08129257410de9cfafd2a /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better layer caching
# This layer only rebuilds when dependencies change
COPY pyproject.toml uv.lock README.md ./

# Install dependencies without the project itself - this layer is cached unless dependency files change
RUN uv sync --locked --no-dev --no-install-project

# Copy source code - this layer rebuilds on any code change
COPY src ./src

# Install the project now that source code is available
RUN uv sync --locked --no-dev

# Capture git commit and branch at build time
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

CMD [".venv/bin/python", "-m", "stockchartsalerts.run_bot"]
