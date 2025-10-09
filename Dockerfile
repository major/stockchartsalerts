FROM docker.io/library/python:3.14@sha256:d29cf0828933ed271be9234ca2c2d578c16f2911451418aacc4525ac04ac7114
COPY --from=ghcr.io/astral-sh/uv:0.9.1@sha256:3b368e735c0227077902233a73c5ba17a3c2097ecdd83049cbaf2aa83adc8a20 /uv /uvx /bin/

ADD . /app
WORKDIR /app
RUN uv sync --locked

CMD ["uv", "run", "run-bot"]
