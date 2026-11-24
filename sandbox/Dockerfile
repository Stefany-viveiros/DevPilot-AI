FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pytest==8.3.5

WORKDIR /workspace
COPY validate.py /opt/devpilot/validate.py
USER 65534:65534
