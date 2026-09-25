import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SYMBOL = "XAUUSDT"

def fetch_order_flow():
    # 1. Fetch latest 5-minute Kline for volume delta
    kline_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={SYMBOL}&interval=5m&limit=1"
    kline_res = requests.get(kline_url).json()[0]
    
    close_price = float(kline_res[4])
    total_volume = float(kline_res[5])
    taker_buy_volume = float(kline_res[9])
    taker_sell_volume = total_volume - taker_buy_volume
    net_delta = taker_buy_volume - taker_sell_volume

    # 2. Fetch order book depth (100 levels) for liquidity walls
    depth_url = f"https://fapi.binance.com/fapi/v1/depth?symbol={SYMBOL}&limit=100"
    depth_res = requests.get(depth_url).json()

    bids = [[float(price), float(qty)] for price, qty in depth_res['bids']]
    asks = [[float(price), float(qty)] for price, qty in depth_res['asks']]

    top_bid = max(bids, key=lambda x: x[1])  # Largest buy wall
    top_ask = max(asks, key=lambda x: x[1])  # Largest sell wall

    # 3. Format Telegram Alert Message
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
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    message = fetch_order_flow()
    send_telegram(message)
