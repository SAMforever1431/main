import os
import requests
from urllib.parse import quote

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SYMBOL = "XAUUSDT"

def fetch_via_proxy(target_url):
    """
    Routes requests through a public gateway to bypass GitHub Actions US IP restrictions.
    Falls back to a direct request if proxy fails.
    """
    proxy_gateway = f"https://corsproxy.io/?{quote(target_url, safe='')}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(proxy_gateway, headers=headers, timeout=10)
        data = res.json()
        if isinstance(data, (list, dict)):
            return data
    except Exception:
        pass

    # Direct fallback attempt
    try:
        res = requests.get(target_url, headers=headers, timeout=10)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def fetch_order_flow():
    # 1. Fetch 5m Kline via proxy
    kline_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={SYMBOL}&interval=5m&limit=1"
    response = fetch_via_proxy(kline_url)

    # Validate response
    if isinstance(response, dict) and ("code" in response or "error" in response):
        err_msg = response.get("msg") or response.get("error") or "Unknown error"
        return f"⚠️ *Binance API Error:* `{err_msg}`\n_(GitHub Actions IP block or Proxy failure)_"

    if not isinstance(response, list) or len(response) == 0:
        return "⚠️ *Error:* Received invalid data format from Binance."

    kline_res = response[0]
    close_price = float(kline_res[4])
    total_volume = float(kline_res[5])
    taker_buy_volume = float(kline_res[9])
    taker_sell_volume = total_volume - taker_buy_volume
    net_delta = taker_buy_volume - taker_sell_volume

    # 2. Fetch Order Book depth via proxy
    depth_url = f"https://fapi.binance.com/fapi/v1/depth?symbol={SYMBOL}&limit=100"
    depth_res = fetch_via_proxy(depth_url)

    if not isinstance(depth_res, dict) or "bids" not in depth_res:
        return f"⚠️ *Error:* Could not fetch Order Book Data."

    bids = [[float(p), float(q)] for p, q in depth_res.get("bids", [])]
    asks = [[float(p), float(q)] for p, q in depth_res.get("asks", [])]

    if not bids or not asks:
        return f"⚠️ *Error:* Empty order book received."

    top_bid = max(bids, key=lambda x: x[1])  # Largest buy wall
    top_ask = max(asks, key=lambda x: x[1])  # Largest sell wall

    # 3. Format Telegram Alert
    delta_type = "🟢 BULLISH DELTA" if net_delta > 0 else "🔴 BEARISH DELTA"

    return (
        f"📊 *XAU/USDT 5-Min Order Flow Alert*\n\n"
        f"💰 *Current Price:* `${close_price:,.2f}`\n"
        f"⚡ *Net Delta:* `{net_delta:+,.2f} XAU` ({delta_type})\n"
        f"🟢 *Market Buys:* `{taker_buy_volume:,.2f} XAU`\n"
        f"🔴 *Market Sells:* `{taker_sell_volume:,.2f} XAU`\n\n"
        f"🛡️ *Largest Bid Support:* `${top_bid[0]:,.2f}` (`{top_bid[1]:,.2f} XAU` wall)\n"
        f"🧱 *Largest Ask Resistance:* `${top_ask[0]:,.2f}` (`{top_ask[1]:,.2f} XAU` wall)"
    )

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets are missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    message = fetch_order_flow()
    send_telegram(message)
    print("Execution completed.")
