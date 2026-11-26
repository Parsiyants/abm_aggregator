# Шпаргалка: git + деплой

Короткие команды на каждый день. Подробности — в `DEPLOY.md`.

---

## 1. Ежедневный цикл (95% случаев)

```bash
# 🖥️ локально
git status                 # что изменено
git add -A                 # добавить все изменения
git commit -m "fix: описание"
git push                   # → GitHub Actions соберёт и задеплоит сам
```

Всё. Через ~4–7 минут изменения на сервере.
Проверить: GitHub → вкладка **Actions** → последний `Deploy via SSH` зелёный.

## 2. Что происходит на сервере (для понимания)

```bash
cd /root/abm_aggregator
git fetch origin main && git reset --hard origin/main
docker compose -f docker-compose.server.yml up -d --build --remove-orphans
docker image prune -f
docker compose -f docker-compose.server.yml ps
```

## 3. Проверка после деплоя

```bash
# на сервере
cd /root/abm_aggregator
docker compose -f docker-compose.server.yml ps
curl -fsS http://127.0.0.1:8000/health
curl -sI http://127.0.0.1:3005/ | head -1

# API закрыт? должно быть 401 без токена
curl -o /dev/null -w 'orders: %{http_code}\n' http://127.0.0.1:8000/api/v1/orders
curl -o /dev/null -w 'docs:   %{http_code}\n' http://127.0.0.1:8000/api/v1/docs   # 200

# что реально задеплоено
git log --oneline -1
```

В браузере: **Ctrl+Shift+R** (жёсткое обновление, иначе останется старая сборка из кэша),
DevTools → Network → WS `/api/v1/ws` → статус `101`.

## 3.1 Пользователи и доступ

Весь API закрыт токеном. Открыты только `POST /api/v1/auth/login`,
`GET /health` и `WS /api/v1/ws` (токен в `?token=`).

> 🔴 `SECRET_KEY` — это ещё и соль хэша паролей. Поменяете — перестанут
> работать и сессии, и все пароли.

```bash
# создать админа (пароль спросит интерактивно)
docker compose -f docker-compose.server.yml exec backend \
  python seed_admin.py --email admin@abm-order.ru

# без интерактива / сменить пароль
docker compose -f docker-compose.server.yml exec \
  -e ADMIN_PASSWORD='пароль' backend python seed_admin.py --email admin@abm-order.ru
docker compose -f docker-compose.server.yml exec backend \
  python seed_admin.py --email admin@abm-order.ru --update

# проверить логин и получить токен
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@abm-order.ru","password":"пароль"}'

# запрос с токеном
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@abm-order.ru","password":"пароль"}' | sed 's/.*"access_token":"\([^"]*\)".*/\1/')
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/auth/me
```

Документация API доступна всегда, ничего включать не нужно:

```
https://abm-order.ru/api/v1/docs          # снаружи
http://127.0.0.1:8000/api/v1/docs        # с сервера
```

В Swagger нажмите **Authorize** и вставьте токен из `/auth/login`, иначе
_Try it out_ вернёт 401.

## 4. Логи

```bash
cd /root/abm_aggregator
docker compose -f docker-compose.server.yml logs -f backend          # хвост в реальном времени
docker compose -f docker-compose.server.yml logs --tail 100 frontend
docker compose -f docker-compose.server.yml logs --since 10m         # за последние 10 минут
```

## 5. Откат

```bash
# 🖥️ локально: отменить коммит и запушить — пересоберётся автоматически
git revert <sha> && git push

# 🖥️ или жёстко откатить ветку (если коммит последний)
git reset --hard HEAD~1 && git push --force-with-lease
```

```bash
# 🖥️ сервер, если Actions недоступен — собрать конкретный коммит руками
cd /root/abm_aggregator
git log --oneline -10
git checkout <sha>
docker compose -f docker-compose.server.yml up -d --build
git checkout main      # после проверки вернуться
```

## 6. Горячая правка на сервере (когда совсем некогда)

⚠️ Правки на сервере живут до следующего `git reset --hard` — их затрут.
Правильный путь: поправить локально → закоммитить → push.

Если нужно срочно:

```bash
cd /root/abm_aggregator
docker compose -f docker-compose.server.yml restart backend   # или frontend
```

## 7. Git: полезное

```bash
# что изменилось
git status -s                 # коротко
git diff                      # несохранённые правки
git diff --staged             # что уйдёт в коммит

# история
git log --oneline -10 --graph
git log -p -- backend/main.py           # история файла с диффами
git show <sha> --stat                   # что менял конкретный коммит

# спрятать правки на время
git stash
git stash pop

# отменить
git restore <file>            # выбросить правки в файле
git restore --staged <file>   # убрать из индекса
git reset --soft HEAD~1       # отменить коммит, оставить правки

# ветки
git switch -c feature/x       # новая ветка
git switch main
git fetch --prune             # подтянуть изменения и почистить мёртвые ветки
```

## 8. Если деплой упал

| Симптом                         | Что смотреть                                                                                              |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Actions падает на `SSH`         | секреты `VPS_HOST` / `VPS_USER` / `VPS_SSH_KEY`; `ssh -i ~/.ssh/abm_deploy root@168.222.140.36 "echo ok"` |
| `cd: no such file or directory` | на сервере нет `/root/abm_aggregator` — клонировать                                                       |
| `git fetch` просит пароль       | у сервера нет доступа к приватному репозиторию (deploy key / HTTPS-токен)                                 |
| `MONGO_USER is required`        | битый `.env` на сервере (`.env` живёт только там)                                                         |
| backend перезапускается         | `docker compose -f docker-compose.server.yml logs --tail 60 backend`                                      |
| `port is already allocated`     | порт `3005`/`8000` занят — поменять `FRONTEND_PORT`/`BACKEND_PORT` в `.env`                               |
| сайт открывается со старым UI   | кэш браузера (Ctrl+Shift+R) либо не прошёл деплой                                                         |
| WS отваливается каждую минуту   | в edge-nginx нет `proxy_read_timeout 3600s` или блок `/api/v1/ws`                                         |

## 9. Место на диске

```bash
df -h /
docker system df
docker image prune -f                 # висячие слои (безопасно)
docker image prune -a -f              # если реально не хватает места
```

## 10. Алиасы (сделать один раз)

`~/.ssh/config` на локальной машине — быстрый вход:

```
Host abm
    HostName 168.222.140.36
    User root
    IdentityFile ~/.ssh/abm_deploy
```

Дальше просто: `ssh abm`

В `~/.zshrc` / `~/.bashrc`:

```bash
alias abm-logs='ssh abm "cd /root/abm_aggregator && docker compose -f docker-compose.server.yml logs --tail 100 backend"'
alias abm-ps='ssh abm "cd /root/abm_aggregator && docker compose -f docker-compose.server.yml ps"'
alias abm-deploy='ssh abm "cd /root/abm_aggregator && git fetch origin main && git reset --hard origin/main && docker compose -f docker-compose.server.yml up -d --build --remove-orphans"'
```

## 11. Чек-лист перед пушем в main

- [ ] `npm run build` в `frontend/` проходит без ошибок
- [ ] `.env` и `backend/.env` **не** в коммите (`git status` их не показывает)
- [ ] секреты не попали в код (`git diff` глазами)
- [ ] сообщение коммита осмысленное — по нему потом искать причину поломки
