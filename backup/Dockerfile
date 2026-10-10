FROM postgres:18-alpine@sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873
RUN apk add --no-cache bash age curl jq python3 ca-certificates \
    && mkdir -p /app && chown postgres:postgres /app
WORKDIR /app
COPY --chown=postgres:postgres scripts/crm-client* ./scripts/
COPY --chown=postgres:postgres backup/ ./backup/
USER postgres
ENV CLIENT_BACKUP_ENABLED=false CLIENT_BACKUP_REQUIRE_ENCRYPTION=true \
    CLIENT_BACKUP_RETENTION_DAYS=30 CLIENT_BACKUP_YANDEX_PATH=app:/clients-backups
# The official image's database-init entrypoint is intentionally not used.
ENTRYPOINT ["bash", "/app/scripts/crm-clients-backup-job.sh"]
