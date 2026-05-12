"""
Polymarket CLOB execution layer.
Requires POLY_PRIVATE_KEY and POLY_API_KEY in .env.
Install: pip install py-clob-client
"""
import os
from typing import Optional

_CHAIN_ID = 137  # Polygon mainnet
_HOST = "https://clob.polymarket.com"


def is_configured() -> bool:
    return bool(os.getenv("POLY_PRIVATE_KEY") and os.getenv("POLY_API_KEY"))


def get_wallet_address() -> Optional[str]:
    """Derive public address from private key without connecting to network."""
    pk = os.getenv("POLY_PRIVATE_KEY")
    if not pk:
        return None
    try:
        from eth_account import Account
        acct = Account.from_key(pk)
        return acct.address
    except Exception:
        return None


def get_clob_client():
    """Return an authenticated ClobClient. Raises if not configured."""
    if not is_configured():
        raise RuntimeError("Polymarket not configured — set POLY_PRIVATE_KEY and POLY_API_KEY in .env")
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
    except ImportError:
        raise RuntimeError("py-clob-client not installed — run: pip install py-clob-client")

    pk = os.getenv("POLY_PRIVATE_KEY")
    api_key = os.getenv("POLY_API_KEY")
    api_secret = os.getenv("POLY_API_SECRET", "")
    api_passphrase = os.getenv("POLY_API_PASSPHRASE", "")

    creds = ApiCreds(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
    )
    client = ClobClient(host=_HOST, key=pk, chain_id=_CHAIN_ID, creds=creds)
    return client


def find_market(entity1: str, entity2: str) -> Optional[str]:
    """Search Polymarket CLOB for a market matching the two teams/fighters."""
    try:
        client = get_clob_client()
        query = f"{entity1} {entity2}".lower()
        resp = client.get_markets(next_cursor="MA==")
        markets = resp.get("data", []) if isinstance(resp, dict) else []

        e1_words = set(entity1.lower().split())
        e2_words = set(entity2.lower().split())

        for mkt in markets:
            q = (mkt.get("question") or "").lower()
            has_e1 = any(w in q for w in e1_words if len(w) > 3)
            has_e2 = any(w in q for w in e2_words if len(w) > 3)
            if has_e1 and has_e2 and mkt.get("active") and not mkt.get("closed"):
                return mkt.get("condition_id") or mkt.get("market_id")
    except Exception:
        pass
    return None


def place_bet(
    market_id: str,
    outcome: str,
    amount_usdc: float,
    slippage: float = 0.02,
) -> dict:
    """
    Place a limit order on Polymarket CLOB.
    outcome: 'yes' or 'no' (or outcome token id)
    amount_usdc: USDC amount to stake
    Returns {order_id, status, price} or {error: str}
    """
    try:
        from py_clob_client.clob_types import OrderArgs, OrderType
        from py_clob_client.order_builder.constants import BUY

        client = get_clob_client()

        # Get current best price
        book = client.get_order_book(market_id)
        bids = book.get("bids", []) if isinstance(book, dict) else []
        asks = book.get("asks", []) if isinstance(book, dict) else []

        if asks:
            best_ask = float(asks[0].get("price", 0.5))
        else:
            best_ask = 0.5

        limit_price = round(min(best_ask + slippage, 0.99), 4)
        size = round(amount_usdc / limit_price, 2)

        order_args = OrderArgs(
            price=limit_price,
            size=size,
            side=BUY,
            token_id=market_id,
        )
        signed = client.create_order(order_args)
        resp = client.post_order(signed, OrderType.GTC)

        return {
            "order_id": resp.get("orderID") or resp.get("order_id"),
            "status": resp.get("status", "submitted"),
            "price": limit_price,
            "size": size,
            "amount_usdc": amount_usdc,
        }

    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Order failed: {str(e)}"}
