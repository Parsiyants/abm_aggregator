from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.exceptions import HTTPException
from services.security import get_current_user_id # Предполагая, что у вас есть функция для декодирования\
from models.user import User # Предполагаем модель пользователя

router = APIRouter()

# --- Менеджер активных соединений ---
class ConnectionManager:
    def __init__(self):
        # Словарь: {user_id: WebSocket}
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"WS: Пользователь {user_id} подключился.")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"WS: Пользователь {user_id} отключился.")

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json({"type": "personal_message", "data": message})
  
    # Рассылка всем авторизованным пользователям
    async def broadcast(self, message: dict):
        bad_users = []
        
        # Используем list(...items()), чтобы итерироваться по копии 
        # и избежать ошибок при изменении словаря во время цикла
        for user_id, websocket in list(self.active_connections.items()):
            try:
                # ВАЖНО: websocket — это объект сокета, а не ID пользователя
                await websocket.send_json(message)
            except Exception as e:
                print(f"WS Error для пользователя {user_id}: {e}")
                bad_users.append(user_id)
    
        # Очищаем мертвые соединения по их ID
        for user_id in bad_users:
            self.disconnect(user_id)

manager = ConnectionManager()

# --- Роутер WebSocket ---
@router.websocket("/v1/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Эндпоинт WebSocket.
    Токен передается как query-параметр: /api/v1/ws?token=...
    """
    
    # 1. Проверка и аутентификация токена
    try:
        # Мы используем ту же логику декодирования токена, что и для REST.
        # Токен в WebSocket приходит в виде строки.
        user_id = get_current_user_id(token=token)

        print(f"WS: Аутентификация успешна для пользователя {user_id}")
        # Получаем user_id из токена. Используйте `sub` или `user_id` из вашего токена.
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
    except Exception as e:
        # Если токен невалиден, не принимаем соединение и закрываем его
        print(f"WS: Отклонено - Неверный токен: {e}")
        await websocket.close(code=1008)
        return

    # 2. Устанавливаем соединение и добавляем в менеджер
    await manager.connect(user_id, websocket)

    initial_data = {"status": "connected", "message": "Добро пожаловать в менеджер заказов."}
    await manager.send_personal_message(initial_data, user_id)

    try:
        while True:
            # Ожидаем входящие сообщения от клиента (например, действие пользователя)
            data = await websocket.receive_json()
            
            print(f"WS: Получено от {user_id}: {data}")

            message_type = data.get("type")
            message_data = data.get("data", {})

            if message_type == "get_order_status":
                # Запрос статуса конкретного заказа
                order_id = message_data.get("order_id")
                # Здесь будет логика обращения к базе данных
                status_message = f"Статус заказа {order_id}: В обработке."
                await manager.send_personal_message(
                    {"type": "order_update", "order_id": order_id, "status": status_message}, 
                    user_id
                )
            
            elif message_type == "start_sync":
                # Запрос на запуск синхронизации с маркетплейсом
                sync_source = message_data.get("source", "All")
                response_message = f"Запущена синхронизация с {sync_source}..."
                
                # В реальном приложении: запуск фоновой задачи (Celery/Asyncio)
                await manager.send_personal_message({"type": "sync_status", "message": response_message}, user_id)

            elif message_type == "pong":
                # Пинг/понг для поддержания соединения
                pass
            
            else:
                await manager.send_personal_message({"type": "error", "message": "Неизвестный тип сообщения."}, user_id)


    except WebSocketDisconnect:
        # 3. Обработка отключения
        manager.disconnect(user_id)
        
    except Exception as e:
        print(f"WS: Ошибка при обработке данных для {user_id}: {e}")
        manager.disconnect(user_id)