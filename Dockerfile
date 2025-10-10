FROM docker.io/library/python:3.14@sha256:d29cf0828933ed271be9234ca2c2d578c16f2911451418aacc4525ac04ac7114
COPY --from=ghcr.io/astral-sh/uv:0.9.2@sha256:6dbd7c42a9088083fa79e41431a579196a189bcee3ae68ba904ac2bf77765867 /uv /uvx /bin/

ADD . /app
WORKDIR /app
RUN uv sync --locked

CMD ["uv", "run", "run-bot"]
