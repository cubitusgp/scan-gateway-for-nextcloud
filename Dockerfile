FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    samba \
    python3 \
    python3-requests \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
COPY watch.py /watch.py
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
