#!/usr/bin/env python3
"""
Создание (или обновление пароля) администратора.

Регистрация через API закрыта: первого пользователя заводим этим скриптом.

Запуск на сервере:
    docker compose -f docker-compose.server.yml exec backend \
        python seed_admin.py --email admin@abm-order.ru

Пароль спросит интерактивно. Варианты без интерактива:
    ADMIN_PASSWORD='...' python seed_admin.py --email ...
    python seed_admin.py --email ... --password '...'
    python seed_admin.py --email ... --update      # сменить пароль существующему

Локально (без Docker):
    cd backend && python seed_admin.py --email admin@localhost
"""

import argparse
import asyncio
import getpass
import os
import sys

from dotenv import load_dotenv

# .env надо загрузить ДО импорта services.security:
# SECRET_KEY читается на уровне модуля (и от него зависит хэш пароля)
load_dotenv()

# Скрипт может запускаться и как `python seed_admin.py`, и из корня backend/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.mongodb import close_mongo_connection, connect_to_mongo  # noqa: E402
from repositories.user_repo import UserRepository  # noqa: E402
from services.security import get_password_hash  # noqa: E402

MIN_PASSWORD_LENGTH = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Создание администратора ABM Aggregator")
    parser.add_argument(
        "--email",
        default=os.getenv("ADMIN_EMAIL"),
        help="email пользователя (или переменная ADMIN_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("ADMIN_PASSWORD"),
        help="пароль (или переменная ADMIN_PASSWORD). Если не задан — будет запрошен",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="если пользователь уже есть — сменить ему пароль",
    )
    return parser.parse_args()


async def seed(email: str, password: str, update: bool) -> int:
    await connect_to_mongo()
    try:
        repo = UserRepository()
        hashed = get_password_hash(password)
        existing = await repo.get_by_email(email)

        if existing:
            if not update:
                print(f"⚠  Пользователь {email} уже существует.")
                print("   Пароль не изменён. Для смены пароля запустите с --update.")
                return 0
            await repo.set_password(email, hashed)
            print(f"✅ Пароль обновлён: {email}")
            return 0

        created = await repo.create_user(email, hashed)
        if not created:
            print(f"❌ Не удалось создать пользователя {email}")
            return 1

        print(f"✅ Создан пользователь: {email}")
        return 0
    finally:
        await close_mongo_connection()


def main() -> int:
    args = parse_args()

    email = (args.email or "").strip().lower()
    if not email:
        print("❌ Не указан email. Пример: python seed_admin.py --email admin@example.com")
        return 1
    if "@" not in email:
        print("❌ Некорректный email")
        return 1

    password = args.password
    if not password:
        password = getpass.getpass("Пароль: ")
        confirm = getpass.getpass("Повторите пароль: ")
        if password != confirm:
            print("❌ Пароли не совпадают")
            return 1

    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"❌ Пароль короче {MIN_PASSWORD_LENGTH} символов")
        return 1

    return asyncio.run(seed(email, password, args.update))


if __name__ == "__main__":
    raise SystemExit(main())
