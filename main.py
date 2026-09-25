import os
import time
import threading
import requests
from flask import Flask

# Flask app to satisfy Render Web Service health checks
app = Flask(__name__)

@app.route('/')
def health_check():
    return "XAU/USDT Order Flow Bot is Running Live!"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SYMBOL = "XAUUSDT"

def fetch_order_flow():
    try:
        # 1. Fetch 5m Kline directly from Binance (EU Server)
        kline_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={SYMBOL}&interval=5m&limit=1"
        res = requests.get(kline_url, timeout=10)
        kline_data = res.json()

        if isinstance(kline_data, dict) and "code" in kline_data:
            return f"⚠️ *Binance Error:* {kline_data.get('msg')}"

        kline_res = kline_data[0]
        close_price = float(kline_res[4])
        total_volume = float(kline_res[5])
        taker_buy_volume = float(kline_res[9])
        taker_sell_volume = total_volume - taker_buy_volume
        net_delta = taker_buy_volume - taker_sell_volume

        # 2. Fetch Order Book Depth
        depth_url = f"https://fapi.binance.com/fapi/v1/depth?symbol={SYMBOL}&limit=100"
        depth_data = requests.get(depth_url, timeout=10).json()

        bids = [[float(p), float(q)] for p, q in depth_data.get("bids", [])]
        asks = [[float(p), float(q)] for p, q in depth_data.get("asks", [])]

        if not bids or not asks:
            return "⚠️ *Error:* Could not fetch Order Book Data."

        top_bid = max(bids, key=lambda x: x[1])  # Largest buy wall
        top_ask = max(asks, key=lambda x: x[1])  # Largest sell wall

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
    except Exception as e:
        return f"⚠️ *Bot Error:* `{str(e)}`"

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def order_flow_loop():
    print("Starting 5-minute loop...")
    while True:
        msg = fetch_order_flow()
        send_telegram(msg)
        print("Alert sent to Telegram.")
        time.sleep(300)  # Wait 5 minutes

if __name__ == "__main__":
    # Run Telegram bot loop in background thread
    thread = threading.Thread(target=order_flow_loop, daemon=True)
    thread.start()

    # Bind to Render's required port
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
