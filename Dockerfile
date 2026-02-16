FROM docker.io/library/python:3.14@sha256:151ab3571dad616bb031052e86411e2165295c7f67ef27206852203e854bcd12
COPY --from=ghcr.io/astral-sh/uv:0.10.3@sha256:7a88d4c4e6f44200575000638453a5a381db0ae31ad5c3a51b14f8687c9d93a3 /uv /uvx /bin/

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
