# base defines a base stage that uses an exact, maintained Python runtime.
FROM python:3.11.16-slim-bookworm@sha256:a36c24f9cbdf4fd0f52d67f0823eeac19c2028c637cecc392d97f980d4fec56b AS base

# Add curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Set the application directory
WORKDIR /usr/local/app

# Install our requirements.txt
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser

# dev defines a stage for development, where it'll watch for filesystem changes
FROM base AS dev
RUN pip install watchdog
ENV FLASK_ENV=development \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1
USER appuser
CMD ["python", "app.py"]

# final defines the stage that will bundle the application for production
FROM base AS final

# Copy our code from the current folder to the working directory inside the container
COPY --chown=appuser:appuser . .

# An unprivileged process cannot bind ports below 1024.
EXPOSE 8080

# Define our command to be run when launching the container
USER appuser
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080", "--log-file", "-", "--access-logfile", "-", "--workers", "4", "--keep-alive", "0"]
