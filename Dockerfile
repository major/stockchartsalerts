FROM docker.io/library/python:3.14@sha256:934873f1360893d07afe0d25b99af46640e916a5900f1677fb86e41f73920253
COPY --from=ghcr.io/astral-sh/uv:0.9.6@sha256:4b96ee9429583983fd172c33a02ecac5242d63fb46bc27804748e38c1cc9ad0d /uv /uvx /bin/

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
