# utils/time.py
from datetime import datetime, timezone
from typing import Optional, Union, Any, Dict, List

_DATETIME_FIELDS_DEFAULT = (
    "order_date",
    "send_date",
    "my_send_date",
    "created_at",
    "updated_at",
    "started_at",
    "finished_at",
)


def now_ts() -> int:
    """Текущее время в Unix Timestamp (секунды)"""
    return int(datetime.now(timezone.utc).timestamp())


def ts_to_datetime(ts: Optional[int]) -> Optional[datetime]:
    """Unix Timestamp → datetime (для ответа фронту)"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def datetime_to_ts(dt: Optional[datetime]) -> Optional[int]:
    """datetime → Unix Timestamp"""
    if dt is None:
        return None
    return int(dt.timestamp())


def ts_to_iso(ts: Optional[int]) -> Optional[str]:
    """Unix Timestamp → ISO-строка (для JSON-ответа)"""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def iso_to_ts(iso_str: Optional[str]) -> Optional[int]:
    """ISO-строка → Unix Timestamp"""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except:
        return None

def to_datetime(value: Optional[Union[datetime, int, float, str]]) -> Optional[datetime]:
    """
    Приводит любое значение к aware datetime (UTC).
    Нужно для сравнения значений, которые могут прийти из разных источников
    (Mongo как naive datetime, Pydantic как aware, из API как int, из JSON как str).
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        # отличаем секунды от миллисекунд по порядку величины
        if value > 1e11:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=timezone.utc)

    # Если пришла строка — парсим
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    return None


def to_timestamp(value: Optional[Union[datetime, int, float, str]]) -> Optional[int]:
    """Приводит любое значение к Unix Timestamp (секунды)."""
    dt = to_datetime(value)
    return int(dt.timestamp()) if dt else None


def is_same_moment(a, b) -> bool:
    """
    Сравнивает два значения как моменты времени с точностью до секунды.
    Возвращает True, если это один и тот же момент (в т.ч. оба None).
    """
    ta = to_timestamp(a)
    tb = to_timestamp(b)
    return ta == tb


def to_iso(value: Optional[Union[datetime, int, float, str]]) -> Optional[str]:
    """Приводит любое значение к ISO-строке (UTC). Удобно для записи в changes."""
    dt = to_datetime(value)
    return dt.isoformat() if dt else None



def serialize_datetime_field(value: Any) -> Any:
    """int → ISO, datetime → ISO, None → None, str → как есть."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except Exception:
            return None
    return value


def serialize_order_doc(
    doc: Dict[str, Any],
    datetime_fields: tuple = _DATETIME_FIELDS_DEFAULT,
) -> Dict[str, Any]:
    """Превращает date-поля документа в ISO-строки. Рекурсивно для items."""
    if not isinstance(doc, dict):
        return doc

    result = dict(doc)

    for field in datetime_fields:
        if field in result:
            result[field] = serialize_datetime_field(result[field])

    items = result.get("items")
    if isinstance(items, list):
        result["items"] = [
            serialize_order_doc(it, datetime_fields)
            if isinstance(it, dict) else it
            for it in items
        ]

    return result


def serialize_order_list(
    docs: List[Dict[str, Any]],
    datetime_fields: tuple = _DATETIME_FIELDS_DEFAULT,
) -> List[Dict[str, Any]]:
    return [serialize_order_doc(d, datetime_fields) for d in docs]