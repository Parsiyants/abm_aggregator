# Деплой ABM Aggregator

Схема: **GitHub Actions → SSH на сервер → сборка и запуск прямо на сервере**.
Никаких реестров образов: `docker compose -f docker-compose.server.yml up -d --build`.

> 🔖 Быстрые команды на каждый день (git, деплой, откат, логи, алиасы) —
> в [CHEATSHEET.md](CHEATSHEET.md).

```
push в main
   │
   └─ GitHub Actions: appleboy/ssh-action ──► root@168.222.140.36
                                               │
                                               ├─ cd /root/abm_aggregator
                                               ├─ git fetch origin main
                                               ├─ git reset --hard origin/main   (.env не трогается)
                                               ├─ docker compose -f docker-compose.server.yml up -d --build
                                               ├─ docker image prune -f
                                               └─ docker compose ... ps
```

## Два compose-файла

| Файл                        | Для чего             | Контейнеры                     | Том                                                |
| --------------------------- | -------------------- | ------------------------------ | -------------------------------------------------- |
| `docker-compose.yml`        | локальная разработка | `abm_local_*`                  | `abm_local_mongo_data`                             |
| `docker-compose.server.yml` | сервер               | `abm_mongodb/backend/frontend` | `abm_aggregator_mongo_data` (или старый, см. п. 5) |

Проекты разные (`name:` в файле), поэтому на одной машине они не конфликтуют.

## TL;DR для сервера

```bash
git clone git@github.com:<owner>/<repo>.git /root/abm_aggregator
cd /root/abm_aggregator
cp .env.example .env && chmod 600 .env && nano .env
# перенести MONGO_*, SECRET_KEY из /root/abm_app/.env (см. п. 4)

cd /root/abm_app && docker compose down && cd /root/abm_aggregator
# подключить старый том данных (см. п. 5)
docker compose -f docker-compose.server.yml up -d --build
```

Дальше — только `git push origin main`.

---

## 1. SSH-ключ для деплоя

GitHub Actions должен заходить на сервер без пароля. Ключ — **отдельная пара**:
приватный в GitHub Secrets, публичный на сервере.

> Секреты GitHub привязаны к **репозиторию**. То, что `VPS_*` уже заведены в
> репозитории `workout-tracker`, в репозитории агрегатора не появится — их нужно
> добавить заново. Сам ключ можно переиспользовать.

### Вариант A — переиспользовать `workout_deploy` (ничего не делать на сервере)

Публичный ключ уже в `/root/.ssh/authorized_keys`. Достаточно создать 4 секрета
в новом репозитории с теми же значениями (см. п. 2).

### Вариант B — отдельный ключ для агрегатора (рекомендуется)

```bash
# 🖥️ локально
ssh-keygen -t ed25519 -C "github-actions-abm" -f ~/.ssh/abm_deploy -N ""

# публичный ключ на сервер
ssh-copy-id -i ~/.ssh/abm_deploy.pub root@168.222.140.36
# либо вручную: cat ~/.ssh/abm_deploy.pub → добавить строку в /root/.ssh/authorized_keys

# проверка: должно пустить без пароля
ssh -i ~/.ssh/abm_deploy root@168.222.140.36 "echo ok"
```

Приватный ключ целиком (вместе с `-----BEGIN/END-----`):

```bash
cat ~/.ssh/abm_deploy
```

Отдельный ключ удобнее: отзыв доступа к одному проекту не ломает другой
(удалить строку из `authorized_keys`).

## 2. Секреты GitHub

🌐 Репозиторий → **Settings → Secrets and variables → Actions → New repository secret**

| Имя           | Значение                                          |
| ------------- | ------------------------------------------------- |
| `VPS_HOST`    | `168.222.140.36`                                  |
| `VPS_USER`    | `root`                                            |
| `VPS_PORT`    | `22`                                              |
| `VPS_SSH_KEY` | содержимое приватного ключа (весь файл, дословно) |

Переменные `VITE_API_URL` / `VITE_WS_URL` задавать **не нужно**: значения по
умолчанию (`/api/v1` и автоопределение WS) прописаны в `docker-compose.server.yml`.

> Приватный ключ нельзя показывать, пересылать в чат или коммитить.

## 3. Подготовка сервера

```bash
ssh root@168.222.140.36

# 3.1 проверить, что порты не заняты workout-tracker'ом
docker ps --format '{{.Names}}\t{{.Ports}}'
ss -ltnp | grep -E ':(3005|8000)\b' || echo "3005/8000 свободны"

# 3.2 бэкапы и код
mkdir -p /root/backups
git clone git@github.com:<owner>/<repo>.git /root/abm_aggregator
cd /root/abm_aggregator

# 3.3 конфиг
cp .env.example .env
chmod 600 .env
nano .env
```

Если порт `3005` или `8000` занят — в `.env` поставьте `FRONTEND_PORT=3006`
(и такой же порт в `proxy_pass` системного nginx).

### Структура на сервере

| Что            | Где                                             |
| -------------- | ----------------------------------------------- |
| Код            | `/root/abm_aggregator` (git clone)              |
| Секреты        | `/root/abm_aggregator/.env` (в git не попадает) |
| Данные MongoDB | docker-том (см. п. 5)                           |
| Бэкапы         | `/root/backups`                                 |
| Старый стек    | `/root/abm_app` (остаётся как страховка)        |

## 4. Заполнение `.env`

**Критично:** `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_DB_NAME` должны **точно
совпадать** со старым `/root/abm_app/.env`. Root-пользователь хранится внутри
самих данных MongoDB — если значение поменять «на бумаге», база перестанет
пускать.

> 🔴 **`SECRET_KEY` менять нельзя после того, как заведены пользователи.**
> Он используется и как ключ подписи JWT, **и как соль для хэша пароля**
> (`sha256(password + SECRET_KEY)`). Новое значение = все сессии невалидны
> **и** ни один пароль не подойдёт. Если ключ всё же меняется — каждому
> пользователю нужно заново задать пароль (`seed_admin.py --update` для админа,
> `POST /api/v1/auth/register` для остальных).

```bash
cd /root/abm_aggregator
grep -E '^(MONGO_USER|MONGO_PASSWORD|MONGO_DB_NAME|SECRET_KEY|POLLING_INTERVAL_SECONDS|OZON_API_KEY|OZON_CLIENT_ID|TELEGRAM_BOT_TOKEN)=' \
  /root/abm_app/.env >> .env

nano .env      # проверить: дублей ключей быть не должно
```

Остальные значения — по смыслу: `FRONTEND_PORT`, `BACKEND_PORT`,
`MONGO_VOLUME_NAME`, `VITE_API_URL=/api/v1`, `VITE_WS_URL=`.

## 5. Перенос данных MongoDB

### Вариант A — подключить существующий том (проще, без копирования)

```bash
# посмотреть тома
docker volume ls

# остановить старый стек (том с данными сохраняется)
cd /root/abm_app && docker compose down
cd /root/abm_aggregator

# прописать имя старого тома в .env
sed -i 's|^MONGO_VOLUME_NAME=.*|MONGO_VOLUME_NAME=abm_app_mongo_data|' .env
```

Новый стек сразу увидит существующие данные. Старый том удалять нельзя.

### Вариант B — скопировать с бэкапом (старое остаётся нетронутым)

```bash
cd /root/abm_aggregator
./scripts/migrate-mongo.sh
```

Скрипт: останавливает старые контейнеры → кладёт tar-архив тома в
`/root/backups` → копирует данные в `abm_aggregator_mongo_data` → сверяет
размер и число файлов (при расхождении падает и ничего не удаляет).

После успешной проверки приложения старый том можно удалить:
`docker volume rm abm_app_mongo_data`.

## 6. Первый запуск

```bash
cd /root/abm_aggregator
docker compose -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.server.yml ps

curl -fsS http://127.0.0.1:8000/health        # {"status":"ok"}
curl -sI  http://127.0.0.1:3005/ | head -1    # HTTP/1.1 200 OK
```

Первая сборка занимает 3–6 минут (`npm ci` + `pip install`), дальше — быстрее
за счёт кэша слоёв Docker. Требуется ~1.5 ГБ свободной RAM на сборку фронтенда
и ~2 ГБ диска.

### 6.1 Первый пользователь (обязательно)

**Весь API закрыт авторизацией.** Открыты только:

| Эндпоинт                  | Почему открыт                                        |
| ------------------------- | ---------------------------------------------------- |
| `POST /api/v1/auth/login` | вход и выдача JWT                                    |
| `GET /health`             | docker healthcheck                                   |
| `WS /api/v1/ws`           | токен передаётся в `?token=`, проверяется в хендлере |

`POST /api/v1/auth/register` тоже требует токен — самостоятельная регистрация
закрыта. `/docs` и `/openapi.json` на сервере выключены (`ENABLE_DOCS=false`).

Поэтому первого пользователя создаём сидом:

```bash
cd /root/abm_aggregator
docker compose -f docker-compose.server.yml exec backend \
  python seed_admin.py --email admin@abm-order.ru
# пароль запросит интерактивно (ввод не отображается)
```

Без интерактива:

```bash
docker compose -f docker-compose.server.yml exec \
  -e ADMIN_PASSWORD='сильный_пароль' backend \
  python seed_admin.py --email admin@abm-order.ru

# сменить пароль существующему
docker compose -f docker-compose.server.yml exec backend \
  python seed_admin.py --email admin@abm-order.ru --update
```

Пароль короче 8 символов скрипт не примет. Проверка:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@abm-order.ru","password":"..."}' | head -c 120
# → {"access_token":"eyJ...", ...}
```

Дополнительных пользователей авторизованный админ создаёт через
`POST /api/v1/auth/register` (в UI — страница `/register`, доступна только
после входа).

## 7. Системный nginx (edge)

Контейнеры публикуются только на localhost, снаружи их закрывает edge-nginx
(конфиг лежит отдельно: `deploy/edge/conf.d/abm.conf`).

| location     | upstream         | что это                       |
| ------------ | ---------------- | ----------------------------- |
| `/api/v1/ws` | `127.0.0.1:8000` | WebSocket (нужен `Upgrade`)   |
| `/api/v1/`   | `127.0.0.1:8000` | REST API                      |
| `/`          | `127.0.0.1:3005` | фронтенд (nginx в контейнере) |

```nginx
server {
    listen 443 ssl;
    server_name abm-order.ru;
    # ... ssl_certificate ...

    client_max_body_size 50m;

    # WebSocket: префикс длиннее, чем /api/v1/, поэтому nginx берёт этот блок
    location /api/v1/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location /api/v1/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location / {
        proxy_pass http://127.0.0.1:3005;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> ⚠️ Путь WebSocket — **`/api/v1/ws`**, а не `/ws`. Если блока `/api/v1/ws` нет,
> handshake уходит в `/api/v1/` без заголовков `Upgrade` и падает (400/426 вместо
> `101 Switching Protocols`).

Альтернатива: не описывать `/api` на edge вообще — тогда запросы проксируются
в контейнер фронтенда (`:3005`), где уже есть `location ^~ /api/` → `backend:8000`.
Так тоже работает, но появляется лишний хоп.

```bash
nginx -t && systemctl reload nginx
certbot --nginx -d abm-order.ru -d www.abm-order.ru
```

## 8. Автодеплой

```bash
git push origin main
```

🌐 Вкладка **Actions** → job `Deploy via SSH` (~4–7 минут: сборка на сервере).

Проверка после первого прогона:

```bash
cd /root/abm_aggregator && git log --oneline -1
docker compose -f docker-compose.server.yml ps
```

## 9. Откат

```bash
# на сервере
cd /root/abm_aggregator
git log --oneline -10
git checkout <sha>                                # или git reset --hard <sha>
docker compose -f docker-compose.server.yml up -d --build
```

Либо локально: `git revert <sha>` → `git push` (пересоберётся автоматически).

Образы пересобираются из кода, поэтому «откатить только образ» нельзя — откат
это всегда откат коммита.

## 10. Обслуживание

```bash
cd /root/abm_aggregator

docker compose -f docker-compose.server.yml ps              # статус
docker compose -f docker-compose.server.yml logs -f backend # логи
docker compose -f docker-compose.server.yml restart backend # рестарт сервиса
docker compose -f docker-compose.server.yml down            # остановить (данные сохраняются)
```

Место на диске:

```bash
df -h /
docker system df
docker image prune -a -f     # только если реально не хватает места
```

## Чек-лист после переезда

- [ ] `docker compose -f docker-compose.server.yml ps` — все три сервиса `Up`
- [ ] `curl http://127.0.0.1:8000/health` → `{"status":"ok"}`
- [ ] `curl -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/orders` → `401` (API закрыт)
- [ ] `curl -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/docs` → `404` (доки выключены)
- [ ] админ создан сидом, `POST /api/v1/auth/login` возвращает `access_token`
- [ ] вход в приложение работает, старые пользователи на месте
- [ ] заказы/отгрузки отдаются (значит база перенесена)
- [ ] DevTools → Network → WS: `101 Switching Protocols` на `/api/v1/ws`
- [ ] домен открывается по HTTPS
- [ ] только после этого: `docker volume rm abm_app_mongo_data` и удаление `/root/abm_app`
