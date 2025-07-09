
# From https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry
FROM docker.io/library/python:3.13@sha256:28f60ab75da2183870846130cead1f6af30162148d3238348f78f89cf6160b5d
WORKDIR /app

RUN pip install -U pip poetry
COPY ./pyproject.toml ./poetry.lock* /

RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

COPY ./stockchartsalerts /code/stockchartsalerts
COPY ./run_bot.py /code/run_bot.py
CMD ["./run_bot.py"]
