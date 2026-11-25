# services/yml_parser.py
import httpx
import xml.etree.ElementTree as ET
from typing import Dict, Any


class YmlParser:
    """
    Парсер YML-файла с ценами и остатками.
    Извлекает: offer_id, vendor, vendor_code, name, price, instock, warehouse_id.
    """

    def __init__(self, url: str):
        self.url = url

    async def fetch_and_parse(self) -> Dict[str, Any]:
        """
        Загружает YML по URL и парсит его.
        Следует редиректам (например, abmauto.ru → prdownload.nodacdn.ru).
        """
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(self.url)
            response.raise_for_status()
            xml_content = response.text

        return self._parse(xml_content)

    def _parse(self, xml_content: str) -> Dict[str, Any]:
        """Парсит XML-строку"""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise Exception(f"Ошибка парсинга YML: {e}")

        shop = root.find("shop")
        if shop is None:
            raise Exception("Тег <shop> не найден в YML")

        # warehouse_id из <company>
        company_el = shop.find("company")
        warehouse_id = None
        if company_el is not None and company_el.text:
            try:
                warehouse_id = int(company_el.text.strip())
            except ValueError:
                warehouse_id = None

        shop_name_el = shop.find("name")
        shop_name = shop_name_el.text.strip() if shop_name_el is not None and shop_name_el.text else None

        offers_el = shop.find("offers")
        if offers_el is None:
            raise Exception("Тег <offers> не найден в YML")

        items = {}
        for offer in offers_el.findall("offer"):
            offer_id = offer.get("id")
            if not offer_id:
                continue

            vendor = self._get_text(offer, "vendor", "")
            vendor_code = self._get_text(offer, "vendorCode", "")
            name = self._get_text(offer, "name", "")

            price_str = self._get_text(offer, "price", "0")
            try:
                price = float(price_str)
            except ValueError:
                price = 0.0

            # instock из outlet
            instock = 0
            outlets = offer.find("outlets")
            if outlets is not None:
                outlet = outlets.find("outlet")
                if outlet is not None:
                    instock_str = outlet.get("instock", "0")
                    try:
                        instock = int(instock_str)
                    except ValueError:
                        instock = 0

            items[offer_id] = {
                "vendor": vendor,
                "vendor_code": vendor_code,
                "name": name,
                "price": price,
                "instock": instock,
            }

        return {
            "warehouse_id": warehouse_id,
            "shop_name": shop_name,
            "items": items,
        }

    @staticmethod
    def _get_text(parent: ET.Element, tag: str, default: str = "") -> str:
        el = parent.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return default