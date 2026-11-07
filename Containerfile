FROM registry.access.redhat.com/ubi9/python-314:latest@sha256:0cf661efaf79d61f6f3c69c11ffcb5ad4ad5805344f5ac43a7076d7061a4b696 AS builder

WORKDIR /opt/app-root/src

COPY pyproject.toml uv.lock .python-version ./
COPY src ./src

RUN python3 -m pip install --no-cache-dir uv==0.12.18 \
    && uv sync --locked --no-dev --no-editable --python python3.14

FROM registry.access.redhat.com/ubi9/python-314:latest@sha256:0cf661efaf79d61f6f3c69c11ffcb5ad4ad5805344f5ac43a7076d7061a4b696

ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ENV GIT_COMMIT=${GIT_COMMIT}
ENV GIT_BRANCH=${GIT_BRANCH}

WORKDIR /opt/app-root/src

COPY --from=builder --chown=1001:0 /opt/app-root/src/.venv /opt/app-root/src/.venv

ENV PATH="/opt/app-root/src/.venv/bin:${PATH}"

ENTRYPOINT ["/opt/app-root/src/.venv/bin/stockchartsalerts"]
