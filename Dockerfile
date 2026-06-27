FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY suites ./suites
COPY thresholds.yaml ./thresholds.yaml

EXPOSE 8000

# Bind to 0.0.0.0:$PORT so the service is reachable in containers/PaaS.
ENV PORT=8000
CMD ["sh", "-c", "evalforge serve --host 0.0.0.0 --port ${PORT}"]
