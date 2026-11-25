from motor.motor_asyncio import AsyncIOMotorClient
import os

# Глобальные переменные для доступа к клиенту и базе данных
client: AsyncIOMotorClient = None
db = None

async def connect_to_mongo():
    """Устанавливает соединение с MongoDB."""
    global client, db
    try:
        MONGO_URL = os.getenv("MONGO_URL")
        MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
        
        if not MONGO_URL or not MONGO_DB_NAME:
            raise ValueError("MONGO_URL or MONGO_DB_NAME not set in environment.")

        # Создаем асинхронный клиент
        client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        # Получаем объект базы данных
        db = client[MONGO_DB_NAME]
        
        # Проверяем соединение
        await client.admin.command('ping')
        
    except Exception as e:
        print(f"Could not connect to MongoDB: {e}")
        # В реальном проекте здесь может быть более сложная обработка
        raise

async def close_mongo_connection():
    """Закрывает соединение с MongoDB."""
    global client
    if client:
        client.close()


async def init_indexes():
    if db is None or client is None:
        raise RuntimeError("MongoDB connection not initialized.")
    
    # тест пинга (опционально, но полезно)
    try:
        await client.admin.command('ping')
    except Exception as e:
        raise RuntimeError(f"MongoDB ping failed: {e}")

    print("Creating MongoDB indexes...")

    try:
        # orders
        await db["orders"].create_index([("process_status", 1), ("order_date", -1)])
        await db["orders"].create_index("market_type")
        await db["orders"].create_index("cabinet_name")
        await db["orders"].create_index("order_date")
        await db["orders"].create_index("send_date")
        await db["orders"].create_index("my_send_date")
        await db["orders"].create_index("order_id", unique=True)

        # orderitems
        await db["orderitems"].create_index("status")
        await db["orderitems"].create_index("provider")
        await db["orderitems"].create_index([("name", "text"), ("article", "text")])
        await db["orderitems"].create_index("order_id_ref")

        # cabinets
        await db["cabinets"].create_index("name", unique=True)

        # mystatuses
        await db["mystatuses"].create_index("code", unique=True)
        await db["mystatuses"].create_index("name")

        await db["polling_logs"].create_index(
            "started_at",
            expireAfterSeconds=3 * 24 * 3600,  # 7 дней
            name="ttl_polling_logs"
        )
        
        await db["sync_logs"].create_index(
            "started_at",
            expireAfterSeconds=14 * 24 * 3600,  # 30 дней
            name="ttl_sync_logs"
        )
        
        await db["order_history"].create_index(
            "created_at",
            expireAfterSeconds=180 * 24 * 3600,  # 180 дней
            name="ttl_order_history"
        )
        
        # Индексы для быстрого поиска
        await db["polling_logs"].create_index([("started_at", -1)])
        await db["polling_logs"].create_index([("market_type", 1), ("started_at", -1)])
        await db["order_history"].create_index([("order_id_ref", 1), ("created_at", -1)])

        print("MongoDB indexes created successfully.")
    except Exception as e:
        print(f"Error creating indexes: {e}")

# Хелпер для получения доступа к БД в других модулях
def get_db():
    """Возвращает объект базы данных."""
    return db