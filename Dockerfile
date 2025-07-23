
# From https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry
FROM docker.io/library/python:3.13@sha256:dd82a2be8703eec3824c8c5f693aa9836fb984f72a14b8a32502236d94c0f8cb
WORKDIR /app

RUN pip install -U pip poetry
COPY ./pyproject.toml ./poetry.lock* /

RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

COPY ./stockchartsalerts /code/stockchartsalerts
COPY ./run_bot.py /code/run_bot.py
CMD ["./run_bot.py"]
