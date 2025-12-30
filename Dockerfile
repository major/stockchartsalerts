FROM docker.io/library/python:3.14@sha256:f05033a4c0ff84db95fd7e6cb361b940a260703d1cd63c63b3472c8ee48e9cff
COPY --from=ghcr.io/astral-sh/uv:0.9.20@sha256:81f1a183fbdd9cec1498b066a32f0da043d4a9dda12b8372c7bfd183665e485d /uv /uvx /bin/

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
