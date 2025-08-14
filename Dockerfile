FROM docker.io/library/python:3.13@sha256:1e4584c017d9cecf8a952cfd8f8e47ef5611b28dfc29da9e1d4b6bad98daf9b0
COPY --from=ghcr.io/astral-sh/uv:0.8.9@sha256:cda9608307dbbfc1769f3b6b1f9abf5f1360de0be720f544d29a7ae2863c47ef /uv /uvx /bin/

ADD . /app
WORKDIR /app
RUN uv sync --locked

CMD ["uv", "run", "run-bot"]
