# base defines a base stage that uses an exact, maintained Python runtime.
FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS base

# Add curl for healthcheck
RUN apk add --no-cache curl

# Set the application directory
WORKDIR /usr/local/app

RUN addgroup -S -g 10001 appuser && adduser -S -D -H -u 10001 -G appuser appuser

# Install our requirements.txt
COPY requirements.txt ./requirements.txt
FROM base AS dependencies
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# dev defines a stage for development, where it'll watch for filesystem changes
FROM dependencies AS dev
RUN /opt/venv/bin/pip install --no-cache-dir watchdog
ENV PATH="/opt/venv/bin:${PATH}" \
    FLASK_ENV=development \
    PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1
USER appuser
CMD ["python", "app.py"]

# final defines the stage that will bundle the application for production
FROM base AS final

# The application runs from its isolated virtual environment; remove build-time
# packaging tools from the final image.
COPY --from=dependencies /opt/venv /opt/venv
RUN /opt/venv/bin/python -m pip uninstall --yes setuptools wheel pip && \
    python -m pip uninstall --yes pip setuptools wheel && \
    rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.11

# Copy our code from the current folder to the working directory inside the container
COPY --chown=appuser:appuser . .

# An unprivileged process cannot bind ports below 1024.
EXPOSE 8080
ENV PATH="/opt/venv/bin:${PATH}"

# Define our command to be run when launching the container
USER appuser
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080", "--log-file", "-", "--access-logfile", "-", "--workers", "4", "--keep-alive", "0"]
