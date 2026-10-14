FROM python:3.11.16-slim-bookworm@sha256:a36c24f9cbdf4fd0f52d67f0823eeac19c2028c637cecc392d97f980d4fec56b

# add apache bench (ab) tool
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    apache2-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /seed

COPY . .

# create POST data files with ab friendly formats
RUN python make-data.py

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /seed

USER appuser
CMD ["/seed/generate-votes.sh"]
