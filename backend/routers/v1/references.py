from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from models.reference import Marketplace, Cabinet, MyStatus, Provider, MongoBase
from repositories.reference_repo import ReferenceRepository
from typing import List, Dict, Any, Type, Callable

router = APIRouter()
repo = ReferenceRepository()

# Справочники, для которых поддерживается ручная очерёдность
ORDERED_REFS = {"statuses", "providers"}


class ReorderPayload(BaseModel):
    """Список id в новом порядке (первый — выше всех)."""
    ids: List[str]

# Словарь для маппинга URL на имя коллекции и Pydantic-модель
REFERENCE_MAP: Dict[str, Dict[str, Any]] = {
    "marketplaces": {"name": "marketplaces", "model": Marketplace},
    "cabinets": {"name": "cabinets", "model": Cabinet},
    "statuses": {"name": "mystatuses", "model": MyStatus},
    "providers": {"name": "providers", "model": Provider},
}

def get_ref_settings(ref_type: str) -> Dict[str, Any]:
    """Вспомогательная функция для получения настроек справочника."""
    if ref_type not in REFERENCE_MAP:
        raise HTTPException(status_code=404, detail="Reference type not found")
    return REFERENCE_MAP[ref_type]

# --- ГЕНЕРИРУЕМ CRUD ЭНДПОИНТЫ ДЛЯ ВСЕХ СПРАВОЧНИКОВ ---

@router.get("/{ref_type}")
async def get_all_references(ref_type: str):
    settings = get_ref_settings(ref_type)
    data = await repo.get_all(settings["name"])
    
    result = []
    for doc in data:
        obj_id = str(doc.pop("_id"))
        # Создаем экземпляр нужной модели (напр. Cabinet)
        model_instance = settings["model"](**doc, _id=obj_id)
        # Превращаем его обратно в словарь, чтобы FastAPI не срезал поля
        result.append(model_instance.model_dump(by_alias=True))

    # Для справочников с ручной очерёдностью — сортируем по index
    if ref_type in ORDERED_REFS:
        result.sort(key=lambda item: (item.get("index") is None, item.get("index") or 0))

    return result


@router.post("/{ref_type}/reorder")
async def reorder_references(ref_type: str, payload: ReorderPayload):
    """
    Сохраняет ручную очерёдность справочника (статусы, поставщики).
    Принимает полный список id в нужном порядке и проставляет index 1..N.
    """
    if ref_type not in ORDERED_REFS:
        raise HTTPException(
            status_code=400,
            detail=f"Reorder is supported only for: {', '.join(sorted(ORDERED_REFS))}",
        )

    settings = get_ref_settings(ref_type)

    if not payload.ids:
        raise HTTPException(status_code=400, detail="ids must not be empty")

    updated = await repo.reorder(settings["name"], payload.ids)

    return {
        "success": True,
        "updated": updated,
        "total": len(payload.ids),
    }


@router.post("/{ref_type}", status_code=201, response_model=MongoBase)
async def create_reference(ref_type: str, item: Dict[str, Any]):
    """Создать новый элемент справочника."""
    settings = get_ref_settings(ref_type)
    
    # Валидация входных данных через Pydantic-модель
    try:
        validated_item = settings["model"](**item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
        
    data_dict = validated_item.model_dump(by_alias=True, exclude_none=True)
    
    new_doc = await repo.create(settings["name"], data_dict)
    if not new_doc:
        raise HTTPException(status_code=500, detail="Failed to create item")
        
    return settings["model"](**new_doc)


@router.put("/{ref_type}/{item_id}") # Убрали response_model=MongoBase, чтобы не срезало поля
async def update_reference(ref_type: str, item_id: str, item: Dict[str, Any]):
    """Обновить существующий элемент справочника."""
    settings = get_ref_settings(ref_type)
    
    # 1. Валидация
    try:
        # Убираем _id из входящих данных, если он там есть, чтобы Pydantic не ругался
        item.pop("_id", None)
        item.pop("id", None)
        settings["model"](**item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
        
    # 2. Обновление
    updated_count = await repo.update(settings["name"], item_id, item)
    
    if updated_count == 0:
        raise HTTPException(status_code=404, detail=f"{settings['name']} with id {item_id} not found")
        
    # 3. Возвращаем обновленный объект
    updated_doc = await repo.get_by_id(settings["name"], item_id)
    
    # ИЗВЛЕКАЕМ _id, чтобы избежать дублирования аргумента
    obj_id = str(updated_doc.pop("_id"))
    
    # Создаем модель и возвращаем её как словарь со всеми полями
    return settings["model"](**updated_doc, _id=obj_id).model_dump(by_alias=True)


@router.delete("/{ref_type}/{item_id}", status_code=204)
async def delete_reference(ref_type: str, item_id: str):
    """Удалить элемент справочника."""
    settings = get_ref_settings(ref_type)
    deleted_count = await repo.delete(settings["name"], item_id)
    
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"{settings['name']} with id {item_id} not found")
    
    return