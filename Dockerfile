FROM docker.io/library/python:3.13@sha256:74503e0bff6cf811f029590a05e0218cc9ba3e099a4b7df0ab84a67df081e1bc
COPY --from=ghcr.io/astral-sh/uv:0.8.15@sha256:a5727064a0de127bdb7c9d3c1383f3a9ac307d9f2d8a391edc7896c54289ced0 /uv /uvx /bin/

ADD . /app
WORKDIR /app
RUN uv sync --locked

CMD ["uv", "run", "run-bot"]
