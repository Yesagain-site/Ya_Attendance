# Bake the schema into the image so it runs on first init without relying on
# a host bind mount (Docker Desktop on Windows mishandles single-file mounts).
FROM postgres:16-alpine
COPY init.sql /docker-entrypoint-initdb.d/init.sql
