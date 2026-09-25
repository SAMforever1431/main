import os
import time
import json
import threading
import requests
import websocket
from flask import Flask

# Flask web app to keep Render service alive
app = Flask(__name__)

@app.route('/')
def health_check():
    return "XAU/USDT Order Flow WebSocket Bot is Live!"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SYMBOL = "xauusdt"

# Live in-memory market state
live_data = {
    "close_price": 0.0,
    "total_volume": 0.0,
    "taker_buy": 0.0,
    "bids": [],
    "asks": []
}

def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Post Error: {e}")

# Handle incoming live messages from Binance WebSocket
def on_message(ws, message):
    try:
        msg = json.loads(message)
        stream = msg.get("stream", "")
        data = msg.get("data", {})

        if "kline" in stream:
            k = data.get("k", {})
            live_data["close_price"] = float(k.get("c", 0))
            live_data["total_volume"] = float(k.get("v", 0))
            live_data["taker_buy"] = float(k.get("V", 0))

        elif "depth" in stream:
            bids = [[float(p), float(q)] for p, q in data.get("b", [])]
            asks = [[float(p), float(q)] for p, q in data.get("a", [])]
            if bids:
                live_data["bids"] = bids
            if asks:
                live_data["asks"] = asks
    except Exception as e:
        print(f"WS Parse Error: {e}")

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed. Auto-reconnecting...")

# Maintain persistent streaming connection to Binance
def start_websocket():
    ws_url = f"wss://fstream.binance.com/stream?streams={SYMBOL}@kline_5m/{SYMBOL}@depth20"
    while True:
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever()
        except Exception as e:
            print(f"WS Exception: {e}")
        time.sleep(5)  # Pause before reconnecting

# Dispatch formatted alert every 5 minutes
def telegram_timer_loop():
    print("Starting 5-minute alert loop...")
    time.sleep(10)  # Warmup wait for initial WS data arrival
    while True:
        try:
            close_price = live_data["close_price"]
            total_volume = live_data["total_volume"]
            taker_buy = live_data["taker_buy"]
            bids = live_data["bids"]
            asks = live_data["asks"]

            if close_price > 0 and bids and asks:
                taker_sell = total_volume - taker_buy
                net_delta = taker_buy - taker_sell
                delta_type = "🟢 BULLISH DELTA" if net_delta > 0 else "🔴 BEARISH DELTA"

                top_bid = max(bids, key=lambda x: x[1])
                top_ask = max(asks, key=lambda x: x[1])

                msg = (
                    f"📊 *XAU/USDT 5-Min Order Flow Alert*\n\n"
                    f"💰 *Current Price:* `${close_price:,.2f}`\n"
                    f"⚡ *Net Delta:* `{net_delta:+,.2f} XAU` ({delta_type})\n"
                    f"🟢 *Market Buys:* `{taker_buy:,.2f} XAU`\n"
                    f"🔴 *Market Sells:* `{taker_sell:,.2f} XAU`\n\n"
                    f"🛡️ *Largest Bid Support:* `${top_bid[0]:,.2f}` (`{top_bid[1]:,.2f} XAU` wall)\n"
                    f"🧱 *Largest Ask Resistance:* `${top_ask[0]:,.2f}` (`{top_ask[1]:,.2f} XAU` wall)"
                )
                send_telegram(msg)
                print("Alert sent to Telegram via WebSocket feed.")
            else:
                print("Waiting for WebSocket market data...")
        except Exception as e:
            print(f"Timer Loop Error: {e}")

        time.sleep(300)  # Wait 5 minutes

if __name__ == "__main__":
    # Launch WebSocket listener thread
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    # Launch Telegram notification thread
    timer_thread = threading.Thread(target=telegram_timer_loop, daemon=True)
    timer_thread.start()

    # Launch Flask HTTP service for Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
