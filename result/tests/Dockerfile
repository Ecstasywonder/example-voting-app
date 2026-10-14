FROM python:3.11.16-slim-bookworm@sha256:a36c24f9cbdf4fd0f52d67f0823eeac19c2028c637cecc392d97f980d4fec56b

WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin testuser
COPY --chown=testuser:testuser tests.py ./tests.py
USER 10001
CMD ["python", "/app/tests.py"]
