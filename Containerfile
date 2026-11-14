FROM registry.access.redhat.com/ubi9/python-314:latest@sha256:015ebf0ddb86cd25d28ac1c2c82ef4ef3c8c9a650dd1b217502534436087ea79 AS builder

WORKDIR /opt/app-root/src

COPY pyproject.toml uv.lock .python-version ./
COPY src ./src

RUN python3 -m pip install --no-cache-dir uv==0.12.18 \
    && uv sync --locked --no-dev --no-editable --python python3.14

FROM registry.access.redhat.com/ubi9/python-314:latest@sha256:015ebf0ddb86cd25d28ac1c2c82ef4ef3c8c9a650dd1b217502534436087ea79

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

WORKDIR /opt/app-root/src

COPY --from=builder --chown=1001:0 /opt/app-root/src/.venv /opt/app-root/src/.venv

ENV PATH="/opt/app-root/src/.venv/bin:${PATH}"

ENTRYPOINT ["/opt/app-root/src/.venv/bin/stockchartsalerts"]
