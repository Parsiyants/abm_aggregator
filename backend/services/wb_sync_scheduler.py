# services/wb_sync_scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from repositories.order_repo import OrderRepository
from services.wb_sync_service import WBSyncService

scheduler = AsyncIOScheduler()


async def sync_all_wb_cabinets():
    """Синхронизирует все активные кабинеты WB."""
    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Starting WB sync cycle...")

    repo = OrderRepository()
    all_cabinets = await repo.get_all_active_cabinets()
    wb_cabinets = [c for c in all_cabinets if c.get('market_slug') == 'wb']

    if not wb_cabinets:
        print("⚠️ Нет активных кабинетов WB")
        return

    print(f"📦 Найдено {len(wb_cabinets)} кабинетов WB")

    for cabinet in wb_cabinets:
        try:
            service = WBSyncService(cabinet, repo)
            result = await service.sync_cabinet()

            if result["success"]:
                print(
                    f"✅ {cabinet.get('name')}: "
                    f"цены {result['prices_updated']}, "
                    f"остатки {result['stocks_updated']}"
                )
            else:
                print(f"❌ {cabinet.get('name')}: {result['errors']}")
        except Exception as e:
            print(f"❌ {cabinet.get('name')}: {e}")

    print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] WB sync cycle finished.")


async def start_wb_sync():
    """Запускает планировщик синхронизации WB: 10:00 и 21:00."""
    scheduler.add_job(
        sync_all_wb_cabinets,
        'cron',
        hour='10,21',
        minute='0',
        id='wb_sync_scheduler',
        max_instances=1,
        coalesce=True,
    )

    if not scheduler.running:
        scheduler.start()
        print("⏰ WB sync scheduler started (10:00, 21:00)")


def stop_wb_sync():
    """Останавливает планировщик."""
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 WB sync scheduler stopped")