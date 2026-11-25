#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# migrate-mongo.sh — перенос данных MongoDB со старого стека (/root/abm_app)
# на новый (/root/abm_aggregator) БЕЗ потери данных.
#
# Что делает:
#   1. останавливает старые контейнеры (том с данными при этом сохраняется);
#   2. делает резервную копию старого тома в /root/backups;
#   3. копирует данные в новый docker-том;
#   4. сверяет размеры и количество файлов.
#
# Использование:
#   ./scripts/migrate-mongo.sh                    автопоиск старого тома
#   ./scripts/migrate-mongo.sh --old-volume abm_app_mongo_data
#   ./scripts/migrate-mongo.sh --reuse-old        не копировать, а просто
#                                                 подключить старый том
#   ./scripts/migrate-mongo.sh --force            перезаписать непустой новый том
#
# ПОСЛЕ миграции: docker compose -f docker-compose.server.yml up -d --build
# ---------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

OLD_DIR="${OLD_DIR:-/root/abm_app}"
OLD_CONTAINER="${OLD_CONTAINER:-abm_mongodb}"
BACKUP_DIR="${BACKUP_DIR:-/root/backups}"

OLD_VOLUME=""
NEW_VOLUME=""
REUSE_OLD=false
FORCE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --old-volume) OLD_VOLUME="${2:-}"; shift ;;
    --old-volume=*) OLD_VOLUME="${1#*=}" ;;
    --old-dir) OLD_DIR="${2:-}"; shift ;;
    --new-volume) NEW_VOLUME="${2:-}"; shift ;;
    --reuse-old) REUSE_OLD=true ;;
    --force) FORCE=true ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "❌ Неизвестный аргумент: $1"; exit 1 ;;
  esac
  shift
done

log()  { printf '%s\n' "$*"; }
step() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m⚠  %s\033[0m\n' "$*"; }
fail() { printf '\033[31m❌ %s\033[0m\n' "$*"; exit 1; }

command -v docker >/dev/null 2>&1 || fail "docker не установлен"

# --- Определяем имена томов ----------------------------------------------
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
NEW_VOLUME="${NEW_VOLUME:-${MONGO_VOLUME_NAME:-abm_aggregator_mongo_data}}"

if [[ -z "$OLD_VOLUME" ]]; then
  # Пытаемся понять имя тома старого стека по контейнеру
  OLD_VOLUME="$(
    docker inspect "$OLD_CONTAINER" \
      --format '{{range .Mounts}}{{if eq .Destination "/data/db"}}{{.Name}}{{end}}{{end}}' \
      2>/dev/null || true
  )"
fi
if [[ -z "$OLD_VOLUME" ]]; then
  # Фолбэк: стандартное имя для каталога /root/abm_app
  OLD_VOLUME="$(basename "$OLD_DIR")_mongo_data"
fi

log "📦 Миграция MongoDB"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "   старый том: ${OLD_VOLUME}"
log "   новый том:  ${NEW_VOLUME}"

docker volume inspect "$OLD_VOLUME" >/dev/null 2>&1 \
  || fail "Том ${OLD_VOLUME} не найден. Укажите вручную: --old-volume <имя> (docker volume ls)"

if docker volume inspect "$NEW_VOLUME" >/dev/null 2>&1; then
  NEW_FILES=$(docker run --rm -v "${NEW_VOLUME}:/to:ro" alpine sh -c 'ls -A /to 2>/dev/null | wc -l')
  if [[ "$NEW_FILES" -gt 0 && "$REUSE_OLD" == false && "$FORCE" == false ]]; then
    fail "Новый том ${NEW_VOLUME} уже содержит данные (${NEW_FILES} файлов).
   Ничего не меняю. Если уверены — запустите с --force."
  fi
fi

# --- Режим «просто подключить старый том» --------------------------------
if $REUSE_OLD; then
  step "🔗 Подключаю существующий том ${OLD_VOLUME} к новому стеку"
  [[ -f .env ]] || fail ".env не найден"
  if grep -q '^MONGO_VOLUME_NAME=' .env; then
    sed -i "s|^MONGO_VOLUME_NAME=.*|MONGO_VOLUME_NAME=${OLD_VOLUME}|" .env
  else
    printf '\nMONGO_VOLUME_NAME=%s\n' "$OLD_VOLUME" >> .env
  fi
  log "   .env: MONGO_VOLUME_NAME=${OLD_VOLUME}"
  log ""
  log "Готово. Дальше: docker compose -f docker-compose.server.yml up -d --build"
  exit 0
fi

# --- 1. Останавливаем старый стек ----------------------------------------
step "🛑 Останавливаю старые контейнеры"
if [[ -f "$OLD_DIR/docker-compose.yml" ]]; then
  ( cd "$OLD_DIR" && docker compose down --remove-orphans ) || warn "docker compose down вернул ошибку"
elif docker ps -a --format '{{.Names}}' | grep -qx "$OLD_CONTAINER"; then
  docker stop "$OLD_CONTAINER" >/dev/null 2>&1 || true
  docker rm "$OLD_CONTAINER" >/dev/null 2>&1 || true
fi
log "   ok (том ${OLD_VOLUME} сохранён)"

# --- 2. Резервная копия --------------------------------------------------
step "💾 Резервная копия старого тома"
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="${BACKUP_DIR}/mongo-${OLD_VOLUME}-$(date +%F-%H%M%S).tar.gz"
docker run --rm \
  -v "${OLD_VOLUME}:/from:ro" \
  -v "${BACKUP_DIR}:/backup" \
  alpine sh -c "tar czf /backup/$(basename "$BACKUP_FILE") -C /from ." \
  || fail "Не удалось создать бэкап"
log "   ${BACKUP_FILE} ($(du -h "$BACKUP_FILE" | awk '{print $1}'))"

# --- 3. Копирование в новый том ------------------------------------------
step "📁 Копирую данные в ${NEW_VOLUME}"
docker volume create "$NEW_VOLUME" >/dev/null
if $FORCE; then
  docker run --rm -v "${NEW_VOLUME}:/to" alpine sh -c 'rm -rf /to/* /to/.[!.]* 2>/dev/null || true'
fi
docker run --rm \
  -v "${OLD_VOLUME}:/from:ro" \
  -v "${NEW_VOLUME}:/to" \
  alpine sh -c 'cp -a /from/. /to/' \
  || fail "Копирование не удалось"
log "   ok"

# --- 4. Проверка ----------------------------------------------------------
step "🔍 Проверка"
OLD_SIZE=$(docker run --rm -v "${OLD_VOLUME}:/d:ro" alpine sh -c 'du -sk /d | cut -f1')
NEW_SIZE=$(docker run --rm -v "${NEW_VOLUME}:/d:ro" alpine sh -c 'du -sk /d | cut -f1')
OLD_FILES=$(docker run --rm -v "${OLD_VOLUME}:/d:ro" alpine sh -c 'find /d -type f | wc -l')
NEW_FILES=$(docker run --rm -v "${NEW_VOLUME}:/d:ro" alpine sh -c 'find /d -type f | wc -l')

log "   старый: ${OLD_SIZE} KB, файлов: ${OLD_FILES}"
log "   новый:  ${NEW_SIZE} KB, файлов: ${NEW_FILES}"

if [[ "$OLD_FILES" != "$NEW_FILES" ]]; then
  fail "Количество файлов не совпадает! Данные не тронуты — старый том ${OLD_VOLUME} цел."
fi
log "   ✅ данные скопированы полностью"

log ""
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "✅ Миграция завершена"
log ""
log "Дальше:"
log "   1. проверьте .env (MONGO_DB_NAME должен совпадать со старой базой)"
log "   2. docker compose -f docker-compose.server.yml up -d --build"
log "   3. после успешного старта старый том можно удалить:"
log "      docker volume rm ${OLD_VOLUME}"
log ""
