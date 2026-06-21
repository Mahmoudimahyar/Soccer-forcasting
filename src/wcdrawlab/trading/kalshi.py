from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .models import TradeIntent


class LiveTradingDisabled(PermissionError):
    """Raised whenever a caller tries to execute without explicit production arming."""


@dataclass(frozen=True)
class KalshiConfig:
    environment: str = "demo"  # demo | production
    api_key_id: str | None = None
    private_key_path: str | None = None
    enable_live_trading: bool = False
    live_trading_ack: str | None = None
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "KalshiConfig":
        env = os.getenv("KALSHI_ENV", "demo").lower()
        return cls(
            environment="production" if env in {"production", "prod", "live"} else "demo",
            api_key_id=os.getenv("KALSHI_API_KEY_ID"),
            private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH"),
            enable_live_trading=os.getenv("KALSHI_ENABLE_LIVE_TRADING", "false").lower() == "true",
            live_trading_ack=os.getenv("KALSHI_LIVE_TRADING_ACK"),
        )

    @property
    def base_url(self) -> str:
        if self.environment == "production":
            return "https://external-api.kalshi.com/trade-api/v2"
        return "https://external-api.demo.kalshi.co/trade-api/v2"


class KalshiClient:
    """Official-style REST client with production execution disabled by default.

    Use `submit_v2_limit_order` only after `RiskGate` approves a mapped TradeIntent.
    The client does not know how a football outcome maps to a Kalshi contract; that
    mapping must be created explicitly in a versioned market-map file.
    """

    def __init__(self, config: KalshiConfig | None = None) -> None:
        self.config = config or KalshiConfig.from_env()
        self._private_key = None

    def _load_key(self):
        if self._private_key is None:
            if not self.config.private_key_path or not self.config.api_key_id:
                raise ValueError("KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH are required for authenticated calls.")
            raw = Path(self.config.private_key_path).expanduser().read_bytes()
            self._private_key = serialization.load_pem_private_key(raw, password=None)
        return self._private_key

    def _headers(self, method: str, endpoint_path: str) -> dict[str, str]:
        key = self._load_key()
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        full_path = urlparse(self.config.base_url + endpoint_path).path.split("?")[0]
        message = f"{timestamp}{method.upper()}{full_path}".encode("utf-8")
        signature = key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": str(self.config.api_key_id),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
            "Content-Type": "application/json",
        }

    def public_markets(self, status: str = "open", limit: int = 200) -> dict:
        resp = requests.get(f"{self.config.base_url}/markets", params={"status": status, "limit": limit}, timeout=self.config.timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def get_orderbook(self, market_ticker: str, depth: int = 10) -> dict:
        # Kalshi's current orderbook endpoint is authenticated according to the API spec.
        resp = requests.get(
            f"{self.config.base_url}/markets/{market_ticker}/orderbook",
            params={"depth": depth},
            headers=self._headers("GET", f"/markets/{market_ticker}/orderbook"),
            timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def get_balance(self) -> dict:
        resp = requests.get(
            f"{self.config.base_url}/portfolio/balance",
            headers=self._headers("GET", "/portfolio/balance"),
            timeout=self.config.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def _assert_execution_armed(self, require_live: bool) -> None:
        if self.config.environment == "production":
            if not require_live:
                raise LiveTradingDisabled("Production order submission requires require_live=True.")
            if not self.config.enable_live_trading:
                raise LiveTradingDisabled("Set KALSHI_ENABLE_LIVE_TRADING=true outside Claude Code to arm production.")
            if self.config.live_trading_ack != "I_ACCEPT_AUTOMATED_TRADING_RISK":
                raise LiveTradingDisabled("KALSHI_LIVE_TRADING_ACK is missing or incorrect.")

    def submit_v2_limit_order(self, intent: TradeIntent, *, require_live: bool = False, time_in_force: str = "immediate_or_cancel") -> dict:
        """Submit a V2 bid/ask order to demo or explicitly armed production.

        The V2 schema uses a single book. `intent.book_side` must be one of `bid` or
        `ask`, and must come from a manually reviewed market mapping.
        """
        self._assert_execution_armed(require_live=require_live)
        if intent.book_side not in {"bid", "ask"}:
            raise ValueError("book_side must be bid or ask")
        payload = {
            "ticker": intent.market_ticker,
            "side": intent.book_side,
            "count": str(intent.contracts),
            "price": f"{intent.limit_price_cents / 100:.4f}",
            "time_in_force": time_in_force,
            "self_trade_prevention_type": "taker_at_cross",
            "client_order_id": intent.client_order_id,
            "cancel_order_on_pause": True,
        }
        endpoint = "/portfolio/events/orders"
        resp = requests.post(
            f"{self.config.base_url}{endpoint}",
            headers=self._headers("POST", endpoint),
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Kalshi order error {resp.status_code}: {resp.text[:1000]}")
        return resp.json()
