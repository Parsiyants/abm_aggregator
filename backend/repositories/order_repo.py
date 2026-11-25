# repositories/order_repo.py
from database.mongodb import get_db
from models.order import BulkItemStatusUpdate, ItemStatusUpdate, Order, OrderIn, OrderItem, OrderItemHandle
from repositories.order_history_repo import OrderHistoryRepository
from utils.time import (
    now_ts,
    to_datetime,
    to_iso,
    is_same_moment,
    serialize_order_doc,
    serialize_order_list,
)
from typing import List, Optional, Tuple, Dict, Any
from bson import ObjectId
from datetime import datetime, timedelta, timezone


# ────────────────────────────────────────────────────────────────────────
# HELPERS: единый формат фильтров по датам
# ────────────────────────────────────────────────────────────────────────

def _date_range_filter(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    storage: str = "int",  # "int" | "datetime"
) -> Optional[Dict[str, Any]]:
    """
    Строит $gte/$lte фильтр для поля, которое в БД лежит либо как int (Unix ts),
    либо как datetime. Возвращает None, если оба аргумента пустые.

    storage="int"      → сравниваем с int(ts)
    storage="datetime" → сравниваем с aware datetime (UTC)
    """
    if not date_from and not date_to:
        return None

    filters: Dict[str, Any] = {}

    if date_from:
        if storage == "int":
            filters["$gte"] = int(
                datetime.combine(date_from.date(), datetime.min.time(), tzinfo=timezone.utc).timestamp()
            )
        else:
            filters["$gte"] = datetime.combine(
                date_from.date(), datetime.min.time(), tzinfo=timezone.utc
            )

    if date_to:
        if storage == "int":
            filters["$lte"] = int(
                datetime.combine(date_to.date(), datetime.max.time(), tzinfo=timezone.utc).timestamp()
            )
        else:
            filters["$lte"] = datetime.combine(
                date_to.date(), datetime.max.time(), tzinfo=timezone.utc
            )

    return filters or None


class OrderRepository:
    def __init__(self):
        pass

    def _get_db(self):
        db = get_db()
        if db is None:
            raise Exception("Database connection is not available.")
        return db

    # ------------------------------------------------------------------------
    # BASE MATCH
    # ------------------------------------------------------------------------

    def _build_base_match(
        self,
        process_status: Optional[List[str]] = None,
        market_type: Optional[List[str]] = None,
        cabinet_name: Optional[List[str]] = None,
        market_status: Optional[List[str]] = None,
        cancellation_type: Optional[str] = None,
        order_date_from: Optional[datetime] = None,
        order_date_to: Optional[datetime] = None,
        send_date_from: Optional[datetime] = None,
        send_date_to: Optional[datetime] = None,
        my_send_date_from: Optional[datetime] = None,
        my_send_date_to: Optional[datetime] = None,
    ) -> Dict:
        """
        Базовый $match для коллекции orders.

        ВАЖНО про форматы хранения:
        - order_date, send_date — int (Unix ts) — как пишет поллер
        - my_send_date — datetime (его ставит оператор через handle_order_processing)
        Поэтому для my_send_date используем storage="datetime".
        """
        match_stage: Dict[str, Any] = {}

        # === Множественные фильтры ($in) ===
        if process_status and len(process_status) > 0:
            match_stage["process_status"] = {"$in": process_status}

        if market_type and len(market_type) > 0:
            match_stage["market_type"] = {"$in": market_type}

        if cabinet_name and len(cabinet_name) > 0:
            match_stage["cabinet_name"] = {"$in": cabinet_name}

        if market_status and len(market_status) > 0:
            match_stage["market_status"] = {"$in": market_status}

        if cancellation_type:
            match_stage["cancellation_type"] = cancellation_type

        # === Диапазоны дат ===
        od = _date_range_filter(order_date_from, order_date_to, storage="int")
        if od:
            match_stage["order_date"] = od

        sd = _date_range_filter(send_date_from, send_date_to, storage="int")
        if sd:
            match_stage["send_date"] = sd

        msd = _date_range_filter(my_send_date_from, my_send_date_to, storage="int")
        if msd:
            match_stage["my_send_date"] = msd

        return match_stage

    # ------------------------------------------------------------------------
    # PIPELINE
    # ------------------------------------------------------------------------

    def _build_orders_pipeline(
        self,
        base_match: Dict,
        skip: int,
        limit: int,
        search: Optional[str] = None,
        item_status: Optional[List[str]] = None,
        item_provider: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Полный пайплайн для orders + все items"""
        pipeline: List[Dict] = []

        # 1. Базовые фильтры по заказам
        if base_match:
            pipeline.append({"$match": base_match})

        # 2. Lookup всех orderitems
        pipeline.append({
            "$lookup": {
                "from": "orderitems",
                "let": {"order_id_str": {"$toString": "$_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$order_id_ref", "$$order_id_str"]}}}
                ],
                "as": "items"
            }
        })

        # 3. Lookup кабинетов
        pipeline.append({
            "$lookup": {
                "from": "cabinets",
                "localField": "cabinet_name",
                "foreignField": "name",
                "as": "cabinet_info"
            }
        })
        pipeline.append({"$unwind": {"path": "$cabinet_info", "preserveNullAndEmptyArrays": True}})
        pipeline.append({"$set": {"cabinet_info._id": {"$toString": "$cabinet_info._id"}}})

        # 4. Условия фильтрации по items
        item_condition_parts = []

        if item_status:
            item_condition_parts.append({"$in": ["$$item.status", item_status]})

        if item_provider:
            item_condition_parts.append({"$in": ["$$item.provider", item_provider]})

        if search:
            regex_pattern = f".*{search}.*"
            item_condition_parts.append({
                "$or": [
                    {"$regexMatch": {"input": "$$item.name", "regex": regex_pattern, "options": "i"}},
                    {"$regexMatch": {"input": "$$item.article", "regex": regex_pattern, "options": "i"}}
                ]
            })

        if item_condition_parts:
            if len(item_condition_parts) == 1:
                item_condition = item_condition_parts[0]
            else:
                item_condition = {"$and": item_condition_parts}

            pipeline.append({
                "$addFields": {
                    "__has_matching_item": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$items",
                                        "as": "item",
                                        "cond": item_condition
                                    }
                                }
                            },
                            0
                        ]
                    }
                }
            })
        else:
            pipeline.append({"$addFields": {"__has_matching_item": True}})

        # 5. Условия поиска по текстовым полям заказа (order_id, comment)
        if search:
            regex_pattern = f".*{search}.*"
            pipeline.append({
                "$addFields": {
                    "__order_id_matches": {
                        "$regexMatch": {"input": "$order_id", "regex": regex_pattern, "options": "i"}
                    },
                    "__comment_matches": {
                        "$regexMatch": {
                            "input": {"$ifNull": ["$comment", ""]},
                            "regex": regex_pattern,
                            "options": "i"
                        }
                    }
                }
            })
            pipeline.append({
                "$match": {
                    "$expr": {
                        "$or": [
                            {"$eq": ["$__order_id_matches", True]},
                            {"$eq": ["$__comment_matches", True]},
                            {"$eq": ["$__has_matching_item", True]}
                        ]
                    }
                }
            })
        else:
            if item_condition_parts:
                pipeline.append({"$match": {"__has_matching_item": True}})

        # 6. Убираем вспомогательные поля
        pipeline.append({"$project": {"__has_matching_item": 0}})
        if search:
            pipeline[-1]["$project"]["__order_id_matches"] = 0
            pipeline[-1]["$project"]["__comment_matches"] = 0

        # 7. Сортировка и пагинация
        pipeline.extend([
            {"$sort": {"order_date": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ])

        return pipeline

    # ------------------------------------------------------------------------
    # 1. ЧТЕНИЕ (ДЛЯ ROUTER)
    # ------------------------------------------------------------------------

    async def get_orders_list(
        self,
        skip: int = 0,
        limit: int = 100,
        process_status: Optional[List[str]] = None,
        market_type: Optional[List[str]] = None,
        market_status: Optional[List[str]] = None,
        cancellation_type: Optional[str] = None,
        search: Optional[str] = None,
        cabinet_name: Optional[List[str]] = None,
        order_date_from: Optional[datetime] = None,
        order_date_to: Optional[datetime] = None,
        send_date_from: Optional[datetime] = None,
        send_date_to: Optional[datetime] = None,
        my_send_date_from: Optional[datetime] = None,
        my_send_date_to: Optional[datetime] = None,
        item_status: Optional[List[str]] = None,
        item_provider: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        db = self._get_db()

        base_match = self._build_base_match(
            process_status=process_status,
            market_type=market_type,
            market_status=market_status,
            cancellation_type=cancellation_type,
            cabinet_name=cabinet_name,
            order_date_from=order_date_from,
            order_date_to=order_date_to,
            send_date_from=send_date_from,
            send_date_to=send_date_to,
            my_send_date_from=my_send_date_from,
            my_send_date_to=my_send_date_to,
        )

        pipeline = self._build_orders_pipeline(
            base_match=base_match,
            skip=skip,
            limit=limit,
            search=search,
            item_status=item_status,
            item_provider=item_provider,
        )

        try:
            cursor = db["orders"].aggregate(pipeline)
            docs = await cursor.to_list(None)
            return serialize_order_list(docs)
        except Exception as e:
            print(f"[ERROR] get_orders_list failed: {str(e)}")
            return []

    async def get_orders_list_count(
        self,
        skip: int = 0,
        limit: int = 100,
        process_status: Optional[List[str]] = None,
        market_type: Optional[List[str]] = None,
        market_status: Optional[List[str]] = None,
        cancellation_type: Optional[str] = None,
        search: Optional[str] = None,
        cabinet_name: Optional[List[str]] = None,
        order_date_from: Optional[datetime] = None,
        order_date_to: Optional[datetime] = None,
        send_date_from: Optional[datetime] = None,
        send_date_to: Optional[datetime] = None,
        my_send_date_from: Optional[datetime] = None,
        my_send_date_to: Optional[datetime] = None,
        item_status: Optional[List[str]] = None,
        item_provider: Optional[List[str]] = None,
    ) -> int:
        db = self._get_db()

        base_match = self._build_base_match(
            process_status=process_status,
            market_type=market_type,
            market_status=market_status,
            cancellation_type=cancellation_type,
            cabinet_name=cabinet_name,
            order_date_from=order_date_from,
            order_date_to=order_date_to,
            send_date_from=send_date_from,
            send_date_to=send_date_to,
            my_send_date_from=my_send_date_from,
            my_send_date_to=my_send_date_to,
        )

        pipeline = self._build_orders_pipeline(
            base_match=base_match,
            skip=0,
            limit=0,
            search=search,
            item_status=item_status,
            item_provider=item_provider,
        )

        # Убираем $sort, $skip, $limit и добавляем $count
        pipeline = pipeline[:-3]
        pipeline.append({"$count": "total"})

        try:
            result = await db["orders"].aggregate(pipeline).to_list(1)
            return result[0]["total"] if result else 0
        except Exception as e:
            print(f"[ERROR] get_orders_list_count failed: {e}")
            return 0

    async def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Получает полный заказ вместе с его позициями (items)."""
        db = self._get_db()

        order = await db["orders"].find_one({"_id": ObjectId(order_id)})
        if not order:
            order = await db["orders"].find_one({"order_id": order_id})

        if order:
            items_cursor = db["orderitems"].find({"order_id_ref": str(order["_id"])})
            order["items"] = await items_cursor.to_list(length=None)

            cabinet_cursor = await db["cabinets"].find_one({"name": order["cabinet_name"]})
            order["cabinet"] = {
                k: str(v) if isinstance(v, ObjectId) else v
                for k, v in cabinet_cursor.items()
            } if cabinet_cursor else None

            return serialize_order_doc(order)

        return None

    async def get_all_active_cabinets(self) -> List[Dict[str, Any]]:
        db = self._get_db()
        cursor = db["cabinets"].find({"active": True})
        return await cursor.to_list(length=None)

    async def get_analytics(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        market_types: Optional[List[str]] = None,
        cabinet_names: Optional[List[str]] = None,
        process_statuses: Optional[List[str]] = None,
        item_providers: Optional[List[str]] = None,
        item_statuses: Optional[List[str]] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:

        db = self._get_db()

        # ====================== BASE MATCH ======================
        match = {}

        
        if date_from or date_to:
            date_filter = {}
            if date_from:
                date_filter["$gte"] = int(date_from.timestamp())
            if date_to:
                date_filter["$lte"] = int(date_to.timestamp())
            if date_filter:
                match["my_send_date"] = date_filter

        if market_types:
            match["market_type"] = {"$in": market_types}
        if cabinet_names:
            match["cabinet_name"] = {"$in": cabinet_names}
        if process_statuses:
            match["process_status"] = {"$in": process_statuses}
        if search:
            match["$or"] = [
                {"order_id": {"$regex": search, "$options": "i"}},
                {"comment": {"$regex": search, "$options": "i"}},
            ]

        pipeline = []
        if match:
            pipeline.append({"$match": match})

        # ====================== ITEMS LOOKUP + FILTER ======================
        items_match = {}
        if item_statuses:
            items_match["status"] = {"$in": item_statuses}
        if item_providers:
            items_match["provider"] = {"$in": item_providers}

        pipeline.append({
            "$lookup": {
                "from": "orderitems",
                "let": {"order_id_str": {"$toString": "$_id"}},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$order_id_ref", "$$order_id_str"]}}},
                    {"$match": items_match} if items_match else {"$match": {}},
                ],
                "as": "items"
            }
        })

        if items_match:
            pipeline.append({"$match": {"items.0": {"$exists": True}}})

        pipeline.append({
            "$addFields": {
                "items_count": {"$size": {"$ifNull": ["$items", []]}},
                "purchase_total": {
                    "$sum": {
                        "$map": {
                            "input": "$items",
                            "as": "item",
                            "in": {
                                "$multiply": [
                                    {"$ifNull": ["$$item.purchase", 0]},
                                    {"$ifNull": ["$$item.count", 1]}
                                ]
                            }
                        }
                    }
                },
                "send_date_only": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": {"$toDate": {"$multiply": ["$my_send_date", 1000]}}
                    }
                }
            }
        })

        # ====================== FACET ======================
        pipeline.append({
            "$facet": {
                "market_groups": [
                    {
                        "$group": {
                            "_id": {"market_type": "$market_type", "cabinet_name": "$cabinet_name"},
                            "total_price": {"$sum": "$price"},
                            "total_orders": {"$sum": 1},
                            "total_items": {"$sum": "$items_count"},
                            "total_purchase": {"$sum": "$purchase_total"},

                            "total_expenses": {"$sum": {"$ifNull": ["$analytics.total_expenses", 0]}},
                            "total_profit": {"$sum": {"$ifNull": ["$analytics.profit", 0]}},

                            "commission_market_total": {"$sum": {"$ifNull": ["$analytics.commission_market_total", 0]}},
                            "commission_payment_total": {"$sum": {"$ifNull": ["$analytics.commission_payment_total", 0]}},
                            "last_mile_total": {"$sum": {"$ifNull": ["$analytics.last_mile_total", 0]}},
                            "processing_fixed_total": {"$sum": {"$ifNull": ["$analytics.processing_fixed", 0]}},
                            "logistics_total": {"$sum": {"$ifNull": ["$analytics.logistics_total", 0]}},
                        }
                    },
                    {
                        "$group": {
                            "_id": "$_id.market_type",
                            "cabinet_details": {
                                "$push": {
                                    "cabinet_name": "$_id.cabinet_name",
                                    "total_price": "$total_price",
                                    "total_orders": "$total_orders",
                                    "total_items": "$total_items",
                                    "total_purchase": "$total_purchase",
                                    "total_expenses": "$total_expenses",
                                    "total_profit": "$total_profit",
                                    "commission_market_total": "$commission_market_total",
                                    "commission_payment_total": "$commission_payment_total",
                                    "last_mile_total": "$last_mile_total",
                                    "processing_fixed_total": "$processing_fixed_total",
                                    "logistics_total": "$logistics_total",
                                }
                            },
                            "total_price": {"$sum": "$total_price"},
                            "total_orders": {"$sum": "$total_orders"},
                            "total_items": {"$sum": "$total_items"},
                            "total_purchase": {"$sum": "$total_purchase"},
                            "total_expenses": {"$sum": "$total_expenses"},
                            "total_profit": {"$sum": "$total_profit"},
                            "commission_market_total": {"$sum": "$commission_market_total"},
                            "commission_payment_total": {"$sum": "$commission_payment_total"},
                            "last_mile_total": {"$sum": "$last_mile_total"},
                            "processing_fixed_total": {"$sum": "$processing_fixed_total"},
                            "logistics_total": {"$sum": "$logistics_total"},
                        }
                    },
                    {"$sort": {"total_price": -1}}
                ],

                "providers": [
                    {"$unwind": "$items"},
                    {
                        "$group": {
                            "_id": "$items.provider",
                            "total_price": {"$sum": "$price"},
                            "total_expenses": {"$sum": "$total_expenses"},
                            "total_items": {"$sum": 1},
                            "total_count": {"$sum": {"$ifNull": ["$items.count", 1]}},
                            "total_purchase": {
                                "$sum": {"$multiply": ["$items.purchase", {"$ifNull": ["$items.count", 1]}]}
                            }
                        }
                    },
                    {"$sort": {"total_price": -1}}
                ],

                "daily_stats": [
                    {
                        "$group": {
                            "_id": "$send_date_only",
                            "total_orders": {"$sum": 1},
                            "total_price": {"$sum": "$price"},
                            "total_purchase": {"$sum": "$purchase_total"},
                            "total_profit": {"$sum": {"$ifNull": ["$analytics.profit", 0]}},
                            "total_items": {"$sum": "$items_count"}
                        }
                    },
                    {"$sort": {"_id": 1}}
                ],

                "orders_list": [
                    {"$sort": {"my_send_date": -1}},
                    {"$limit": 300}
                ]
            }
        })

        result = await db["orders"].aggregate(pipeline).to_list(1)
        if not result:
            return {"market_groups": [], "providers": [], "daily_stats": [], "orders_list": [], "grand_total": {}}

        data = result[0]

        grand_total = {
            "total_price": sum(x.get("total_price", 0) for x in data["market_groups"]),
            "total_orders": sum(x.get("total_orders", 0) for x in data["market_groups"]),
            "total_items": sum(x.get("total_items", 0) for x in data["market_groups"]),
            "total_purchase": sum(x.get("total_purchase", 0) for x in data["market_groups"]),
            "total_expenses": sum(x.get("total_expenses", 0) for x in data["market_groups"]),
            "total_profit": sum(x.get("total_profit", 0) for x in data["market_groups"]),
            "commission_market_total": sum(x.get("commission_market_total", 0) for x in data["market_groups"]),
            "commission_payment_total": sum(x.get("commission_payment_total", 0) for x in data["market_groups"]),
            "last_mile_total": sum(x.get("last_mile_total", 0) for x in data["market_groups"]),
            "processing_fixed_total": sum(x.get("processing_fixed_total", 0) for x in data["market_groups"]),
            "logistics_total": sum(x.get("logistics_total", 0) for x in data["market_groups"]),
        }

        return {
            "market_groups": data["market_groups"],
            "providers": data["providers"],
            "daily_stats": data["daily_stats"],
            "orders_list": serialize_order_list(data["orders_list"]),
            "grand_total": grand_total
        }

    async def get_market_status_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по market_status в разрезе маркетплейсов."""
        db = self._get_db()

        pipeline = [
            {
                "$group": {
                    "_id": {
                        "market_type": "$market_type",
                        "market_status": "$market_status"
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": "$_id.market_type",
                    "statuses": {
                        "$push": {
                            "status": "$_id.market_status",
                            "count": "$count"
                        }
                    },
                    "total": {"$sum": "$count"}
                }
            },
            {
                "$project": {
                    "market_type": "$_id",
                    "total": 1,
                    "statuses": {
                        "$sortArray": {
                            "input": "$statuses",
                            "sortBy": {"count": -1}
                        }
                    }
                }
            },
            {
                "$sort": {"total": -1}
            }
        ]

        results = await db["orders"].aggregate(pipeline).to_list(None)
        total_orders = await db["orders"].count_documents({})

        return {
            "markets": results,
            "total_orders": total_orders
        }

    # ------------------------------------------------------------------------
    # 2. UPSERT (ДЛЯ ПОЛЛЕРА)
    # ------------------------------------------------------------------------

    async def get_order_by_external_id(self, order_id: str, market_slug: str) -> Optional[Dict]:
        db = self._get_db()
        return await db["orders"].find_one({
            "order_id": order_id,
            "market_type": market_slug
        })

    async def get_active_orders_by_market(
        self,
        market_slug: str,
        exclude_statuses: List[str],
        days_back: int = 14
    ) -> List[Dict]:
        """
        Получает активные заказы за последние N дней.
        Используется для обновления статусов (WB, Ozon).
        """
        db = self._get_db()

        min_ts = now_ts() - (days_back * 86400)

        cursor = db["orders"].find({
            "market_type": market_slug,
            "process_status": {"$nin": exclude_statuses},
            "order_date": {"$gte": min_ts}
        })
        return await cursor.to_list(None)

    async def upsert_order(self, order_in: OrderIn) -> Dict[str, Any]:
        db = self._get_db()
        orders_collection = db["orders"]
        items_collection = db["orderitems"]
        history_repo = OrderHistoryRepository()

        order_dict = order_in.order_data.model_dump()
        items_dicts = [item.model_dump() for item in order_in.items_data]

        query = {
            "order_id": order_dict['order_id'],
            "market_type": order_dict['market_type']
        }
        existing_order = await orders_collection.find_one(query)

        market_status_from_api = order_dict.get('market_status', '')
        market_status_upper = market_status_from_api.upper()

        canceled_map = [
            'CANCELLED', 'CANCELED', 'CANCELED_BY_CLIENT', 'DECLINED_BY_CLIENT',
            'DEFECT', 'CANCELED_BY_CARRIER', 'CANCELLED_FROM_SPLIT_PENDING',
            'NOT_ACCEPTED', 'ARBITRATION', 'CLIENT_ARBITRATION', 'UNKNOWN'
        ]
        delivered_map = ['DELIVERED', 'SOLD']

        if existing_order:
            # ─────────────────────────────────────────────────────
            # 1. ЛОГИКА ОБНОВЛЕНИЯ
            # ─────────────────────────────────────────────────────

            # EARLY EXIT: если статус и служебные поля не изменились — не трогаем БД
            old_status = existing_order.get('market_status')
            status_changed = old_status != market_status_from_api

            # Поля, которые могут обновиться независимо от статуса
            # (детализированный статус, трек-номер, штрихкод отправления)
            extra_updates = {
                field: order_dict.get(field)
                for field in (
                    "substatus",
                    "tracking_number",
                    "scanit",
                    "delivery_schema",
                    "order_number",
                )
                if order_dict.get(field) and existing_order.get(field) != order_dict.get(field)
            }

            if not status_changed and not extra_updates:
                items = await items_collection.find(
                    {"order_id_ref": str(existing_order['_id'])}
                ).to_list(length=None)
                existing_order["items"] = items

                return {
                    "order": existing_order,
                    "status_changed": False,
                    "is_new": False,
                }

            # Статус изменился — обновляем
            update_fields = {
                "updated_at": now_ts(),
            }
            if status_changed:
                update_fields["market_status"] = market_status_from_api
            update_fields.update(extra_updates)

            # Обновляем аналитику только если заказ не обработан
            if status_changed and existing_order.get('process_status') == 'New':
                update_fields["analytics"] = order_dict.get('analytics')

            history_entries = []

            if status_changed:
                # Маппинг статусов
                if market_status_upper in canceled_map and existing_order.get('process_status') != 'Cancel':
                    update_fields['process_status'] = 'Cancel'
                    history_entries.append({
                        'event_type': 'status_changed',
                        'old_status': old_status,
                        'new_status': market_status_from_api,
                        'comment': f'Статус изменён на "Отменён" ({market_status_from_api})',
                        'changes': {
                            'process_status': {
                                'old': existing_order.get('process_status'),
                                'new': 'Cancel'
                            }
                        }
                    })
                elif market_status_upper in delivered_map and existing_order.get('process_status') != 'Done':
                    update_fields['process_status'] = 'Done'
                    history_entries.append({
                        'event_type': 'status_changed',
                        'old_status': old_status,
                        'new_status': market_status_from_api,
                        'comment': f'Статус изменён на "Доставлен" ({market_status_from_api})',
                        'changes': {
                            'process_status': {
                                'old': existing_order.get('process_status'),
                                'new': 'Done'
                            }
                        }
                    })
                else:
                    history_entries.append({
                        'event_type': 'status_changed',
                        'old_status': old_status,
                        'new_status': market_status_from_api,
                        'comment': f'Статус на маркетплейсе изменился: {old_status} → {market_status_from_api}',
                        'changes': {
                            'market_status': {
                                'old': old_status,
                                'new': market_status_from_api
                            }
                        }
                    })

            await orders_collection.update_one(query, {"$set": update_fields})
            existing_order.update(update_fields)

            for entry in history_entries:
                await history_repo.add_entry(
                    order_id_ref=str(existing_order['_id']),
                    order_id=order_dict['order_id'],
                    market_type=order_dict['market_type'],
                    event_type=entry['event_type'],
                    event_source='poller',
                    old_status=entry.get('old_status'),
                    new_status=entry.get('new_status'),
                    comment=entry.get('comment'),
                    changes=entry.get('changes', {}),
                )

            items = await items_collection.find(
                {"order_id_ref": str(existing_order['_id'])}
            ).to_list(length=None)
            existing_order["items"] = items

            return {"order": existing_order, "status_changed": True, "is_new": False}

        else:
            # ─────────────────────────────────────────────────────
            # 2. ЛОГИКА СОЗДАНИЯ
            # ─────────────────────────────────────────────────────

            if market_status_upper in canceled_map:
                order_dict['process_status'] = 'Cancel'
            elif market_status_upper in delivered_map:
                order_dict['process_status'] = 'Done'
            else:
                order_dict['process_status'] = 'New'

            now = now_ts()
            order_dict['created_at'] = now
            order_dict['updated_at'] = now

            inserted_result = await orders_collection.insert_one(order_dict)
            order_mongo_id = inserted_result.inserted_id
            order_dict['_id'] = order_mongo_id

            items_to_insert = [
                {**item, "order_id_ref": str(order_mongo_id), "created_at": now, "updated_at": now}
                for item in items_dicts
            ]

            if items_to_insert:
                await items_collection.insert_many(items_to_insert)

            order_dict["items"] = items_to_insert

            await history_repo.add_entry(
                order_id_ref=str(order_mongo_id),
                order_id=order_dict['order_id'],
                market_type=order_dict['market_type'],
                event_type='created',
                event_source='poller',
                new_status=order_dict.get('market_status'),
                comment=f'Заказ создан. Статус МП: {order_dict.get("market_status")}',
                changes={
                    'order_created': True,
                    'market_status': order_dict.get('market_status'),
                    'process_status': order_dict.get('process_status'),
                },
            )

            return {"order": order_dict, "status_changed": True, "is_new": True}

    # ------------------------------------------------------------------------
    # 3. ОБНОВЛЕНИЕ (ДЛЯ ОПЕРАТОРА)
    # ------------------------------------------------------------------------

    async def handle_order_processing(
        self,
        order_id: str,
        my_send_date: Optional[datetime] = None,
        comment: Optional[str] = None,
        items: Optional[List[OrderItemHandle]] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Обновляет заказ и позиции.
        Меняет process_status на "Process" ТОЛЬКО если:
        1. Текущий статус == "New"
        2. ВСЕ позиции обработаны (purchase > 0 и status заполнен)

        Пишет в историю все изменения.
        """
        db = self._get_db()
        history_repo = OrderHistoryRepository()
        items = items or []

        has_changes = False
        status_changed = False
        order_oid = ObjectId(order_id)

        order_doc = await db["orders"].find_one(
            {"_id": order_oid},
            projection={
                "_id": 1, "process_status": 1, "market_status": 1,
                "order_id": 1, "market_type": 1,
                "my_send_date": 1, "comment": 1,
            }
        )
        if not order_doc:
            return {"has_changes": False, "status_changed": False}

        current_status = order_doc.get("process_status")
        order_external_id = order_doc.get("order_id")
        market_type = order_doc.get("market_type")

        # ─────────────────────────────────────────────────────
        # 1. Обновление самого заказа
        # ─────────────────────────────────────────────────────
        order_update = {}
        order_changes = {}

        if my_send_date is not None:
            new_ts = int(my_send_date.timestamp()) if isinstance(my_send_date, datetime) else int(my_send_date)
            old_ts = order_doc.get("my_send_date")

            # Приводим old к int (на случай legacy-данных)
            if isinstance(old_ts, datetime):
                old_ts = int(old_ts.timestamp())

            if old_ts != new_ts:
                order_update["my_send_date"] = new_ts
                order_changes["my_send_date"] = {
                    "old": to_iso(old_ts),
                    "new": to_iso(new_ts),
        }

        if comment is not None:
            old_comment = order_doc.get("comment")
            if old_comment != comment:
                order_update["comment"] = comment
                order_changes["comment"] = {"old": old_comment, "new": comment}

        if order_update:
            order_update["updated_at"] = now_ts()
            result = await db["orders"].update_one(
                {"_id": order_oid},
                {"$set": order_update}
            )
            if result.modified_count > 0:
                has_changes = True

                await history_repo.add_entry(
                    order_id_ref=str(order_oid),
                    order_id=order_external_id,
                    market_type=market_type,
                    event_type="updated",
                    event_source="user",
                    comment="Заказ обновлён оператором",
                    changes=order_changes,
                    user_id=user_id,
                    user_email=user_email,
                )

        # ─────────────────────────────────────────────────────
        # 2. Обновление позиций
        # ─────────────────────────────────────────────────────
        items_modified = 0
        item_history_events = []

        for item in items:
            try:
                item_oid = ObjectId(item.item_id)
            except Exception:
                continue

            current_item = await db["orderitems"].find_one(
                {"_id": item_oid, "order_id_ref": order_id},
                projection={"article": 1, "purchase": 1, "provider": 1, "status": 1}
            )
            if not current_item:
                continue

            item_update = {}
            item_changes = {}

            if item.purchase is not None and current_item.get("purchase") != item.purchase:
                item_update["purchase"] = item.purchase
                item_changes["purchase"] = {"old": current_item.get("purchase"), "new": item.purchase}

            if item.provider is not None and current_item.get("provider") != item.provider:
                item_update["provider"] = item.provider
                item_changes["provider"] = {"old": current_item.get("provider"), "new": item.provider}

            if item.status is not None and current_item.get("status") != item.status:
                item_update["status"] = item.status
                item_changes["status"] = {"old": current_item.get("status"), "new": item.status}

            if item_update:
                item_update["updated_at"] = now_ts()
                result = await db["orderitems"].update_one(
                    {"_id": item_oid, "order_id_ref": order_id},
                    {"$set": item_update}
                )
                if result.modified_count > 0:
                    items_modified += 1
                    has_changes = True

                    item_history_events.append({
                        "article": current_item.get("article"),
                        "changes": item_changes,
                        "old_status": current_item.get("status"),
                        "new_status": item.status or current_item.get("status"),
                    })

        # ─────────────────────────────────────────────────────
        # 3. Авто-переход process_status New → Process
        # ─────────────────────────────────────────────────────
        if current_status == "New" and items_modified > 0:
            unprocessed_count = await db["orderitems"].count_documents({
                "order_id_ref": order_oid,
                "$or": [
                    {"purchase": {"$in": [None, 0]}},
                    {"status": {"$in": [None, "", "В ожидании"]}},
                ]
            })

            if unprocessed_count == 0:
                status_result = await db["orders"].update_one(
                    {"_id": order_oid, "process_status": "New"},
                    {"$set": {"process_status": "Process", "updated_at": now_ts()}}
                )
                if status_result.modified_count > 0:
                    status_changed = True
                    has_changes = True

                    await history_repo.add_entry(
                        order_id_ref=str(order_oid),
                        order_id=order_external_id,
                        market_type=market_type,
                        event_type="status_changed",
                        event_source="system",
                        old_status=current_status,
                        new_status="Process",
                        comment="Все позиции обработаны — заказ переведён в статус «В обработке»",
                        changes={"process_status": {"old": current_status, "new": "Process"}},
                        user_id=user_id,
                        user_email=user_email,
                    )

        # ─────────────────────────────────────────────────────
        # 4. Запись в историю изменений позиций
        # ─────────────────────────────────────────────────────
        if item_history_events:
            for ev in item_history_events:
                changes_flat = {k: v["new"] for k, v in ev["changes"].items()}
                await history_repo.add_entry(
                    order_id_ref=str(order_oid),
                    order_id=order_external_id,
                    market_type=market_type,
                    event_type="item_status_changed",
                    event_source="user",
                    old_status=ev.get("old_status"),
                    new_status=ev.get("new_status"),
                    comment=f"Обновлена позиция {ev['article']}",
                    changes={
                        "article": ev["article"],
                        **changes_flat,
                    },
                    user_id=user_id,
                    user_email=user_email,
                )

        return {
            "has_changes": has_changes,
            "status_changed": status_changed,
        }

    async def bulk_update_item_statuses(
        self,
        data: BulkItemStatusUpdate,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> int:
        """Массовое обновление статусов позиций заказа с записью в историю."""
        db = self._get_db()
        history_repo = OrderHistoryRepository()
        modified_count = 0

        events_by_order: Dict[str, List[Dict[str, Any]]] = {}

        for update in data.updates:
            try:
                item_oid = ObjectId(update.item_id)
            except Exception:
                continue

            current_item = await db["orderitems"].find_one(
                {"_id": item_oid},
                projection={"order_id_ref": 1, "article": 1, "status": 1}
            )
            if not current_item:
                continue

            old_status = current_item.get("status")
            if old_status == update.status:
                continue

            result = await db["orderitems"].update_one(
                {"_id": item_oid},
                {"$set": {"status": update.status, "updated_at": now_ts()}},
                upsert=False
            )

            if result.modified_count > 0:
                modified_count += 1
                order_ref = current_item.get("order_id_ref")
                events_by_order.setdefault(order_ref, []).append({
                    "article": current_item.get("article"),
                    "old_status": old_status,
                    "new_status": update.status,
                })

        for order_ref, events in events_by_order.items():
            order_doc = await db["orders"].find_one(
                {"_id": ObjectId(order_ref)},
                projection={"order_id": 1, "market_type": 1}
            )
            if not order_doc:
                continue

            for ev in events:
                await history_repo.add_entry(
                    order_id_ref=order_ref,
                    order_id=order_doc.get("order_id"),
                    market_type=order_doc.get("market_type"),
                    event_type="item_status_changed",
                    event_source="user",
                    old_status=ev["old_status"],
                    new_status=ev["new_status"],
                    comment=f"Статус товара {ev['article']} изменён: {ev['old_status'] or '—'} → {ev['new_status']}",
                    changes={
                        "article": ev["article"],
                        "status": {"old": ev["old_status"], "new": ev["new_status"]},
                    },
                    user_id=user_id,
                    user_email=user_email,
                )

        return modified_count