#!/usr/bin/env sh
# 备份数据库与房源图片，保留最近 14 天。建议加入 crontab：
#   30 3 * * * cd /opt/houses && sh deploy/backup.sh >> logs/backup.log 2>&1
set -eu

ENV_FILE="${HOUSES_ENV_FILE:-deploy/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"

# 读取数据库账号（只取需要的两行，不 source 整个文件）
DB_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
DB_NAME="$(grep -E '^POSTGRES_DATABASE=' "$ENV_FILE" | cut -d= -f2-)"

mkdir -p "$BACKUP_DIR"
compose="docker compose --env-file $ENV_FILE"

$compose exec -T postgres pg_dump -U "$DB_USER" -d "$DB_NAME" --format=custom > "$BACKUP_DIR/db-$STAMP.dump"
$compose run --rm --no-deps -T --entrypoint tar api -C /data -czf - uploads > "$BACKUP_DIR/uploads-$STAMP.tar.gz"

find "$BACKUP_DIR" -type f \( -name 'db-*.dump' -o -name 'uploads-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
echo "$(date '+%F %T') 备份完成：$BACKUP_DIR/db-$STAMP.dump, uploads-$STAMP.tar.gz"
# 恢复数据库：$compose exec -T postgres pg_restore -U "$DB_USER" -d "$DB_NAME" --clean < db-xxxx.dump
