FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY dist/*.whl /tmp/
RUN pip install /tmp/*.whl && rm -rf /tmp/*.whl

WORKDIR /data
ENTRYPOINT ["datasets-lint"]
CMD ["--help"]
