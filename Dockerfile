
# From https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry
FROM docker.io/library/python:3.13@sha256:6f244021b4eebc18b8b577ada606b5765b907bd547dacadfa132fe2acfa5f58f
WORKDIR /app

RUN pip install -U pip poetry
COPY ./pyproject.toml ./poetry.lock* /

RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

COPY ./stockchartsalerts /code/stockchartsalerts
COPY ./run_bot.py /code/run_bot.py
CMD ["./run_bot.py"]
