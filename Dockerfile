FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    samba \
    python3 \
    python3-requests \
    python3-flask \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
COPY watch.py /watch.py
COPY admin.py /admin.py
RUN chmod +x /entrypoint.sh

VOLUME ["/config"]

ENTRYPOINT ["/entrypoint.sh"]
