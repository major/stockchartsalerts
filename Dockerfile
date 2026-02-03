FROM docker.io/library/python:3.14@sha256:5ada2b3e9586c924a8c81d6a35e6016f4fc261429dbd7e5c6ae724431003dcee
COPY --from=ghcr.io/astral-sh/uv:0.9.28@sha256:59240a65d6b57e6c507429b45f01b8f2c7c0bbeee0fb697c41a39c6a8e3a4cfb /uv /uvx /bin/

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
