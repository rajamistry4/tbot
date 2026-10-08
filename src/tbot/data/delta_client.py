"""Small public REST client for Delta Exchange India. No trading or credentials."""
import json
import time
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class DeltaAPIError(RuntimeError):
    pass


class DeltaIndiaClient:
    BASE_URL = "https://api.india.delta.exchange"

    def __init__(self, timeout=20, retries=2):
        self.timeout = timeout
        self.retries = retries

    def get(self, path, params=None):
        url = self.BASE_URL + path
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "tbot/0.2"})
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response, parse_float=Decimal)
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == self.retries:
                    raise DeltaAPIError(f"Delta HTTP {error.code} at {path}") from error
                # Respect a numeric Retry-After, with a bounded wait.
                retry_after = error.headers.get("Retry-After", "")
                delay = min(float(retry_after), 30) if retry_after.isdigit() else 2 ** attempt
                time.sleep(delay)
                continue
            except (URLError, TimeoutError, OSError) as error:
                if attempt == self.retries:
                    raise DeltaAPIError(f"Cannot reach Delta India at {path}: {error}") from error
                time.sleep(2 ** attempt)
                continue
            except (ValueError, UnicodeError) as error:
                raise DeltaAPIError("Delta returned invalid JSON") from error
            if not isinstance(payload, dict) or payload.get("success") is not True:
                raise DeltaAPIError(f"Delta rejected request at {path}: {payload.get('error') if isinstance(payload, dict) else 'invalid response'}")
            return payload

    def products(self):
        """Fetch all product pages; never silently return a partial catalogue."""
        products, seen = [], set()
        after = None
        while True:
            params = {"page_size": 100}
            if after:
                params["after"] = after
            payload = self.get("/v2/products", params)
            rows = payload.get("result")
            if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                raise DeltaAPIError("Product result must be a list of objects")
            products.extend(rows)
            metadata = payload.get("meta") or {}
            if not isinstance(metadata, dict):
                raise DeltaAPIError("Invalid product pagination metadata")
            after = metadata.get("after")
            if after is not None and not isinstance(after, str):
                raise DeltaAPIError("Invalid product pagination cursor")
            if not after:
                return products
            if after in seen:
                raise DeltaAPIError("Delta repeated a product pagination cursor")
            seen.add(after)

    def candles(self, symbol, resolution, start, end):
        payload = self.get("/v2/history/candles", {
            "symbol": symbol, "resolution": resolution, "start": start, "end": end,
        })
        if not isinstance(payload.get("result"), list):
            raise DeltaAPIError("Candle result must be a list")
        return payload["result"]
