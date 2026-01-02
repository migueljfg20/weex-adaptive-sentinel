from flask import Flask, request, jsonify
import requests
import json
import time
import hmac
import hashlib
import base64
import random
import os

app = Flask(__name__)

# =======================================================
# 1. CONFIGURAÇÕES & CHAVES
# =======================================================
WEEX_API_KEY = "YOUR_WEEX_API_KEY"
WEEX_SECRET_KEY = "YOUR_WEEX_SECRET_KEY"
WEEX_PASSPHRASE = "YOUR_WEEX_PASSPHRASE"

GROQ_API_KEY = "YOUR_GROQ_API_KEY" 

# =======================================================
# 2. DRIVER NATIVO WEEX
# =======================================================
def generate_signature(secret_key, timestamp, method, request_path, query_string, body):
    message = timestamp + method.upper() + request_path + query_string + str(body)
    signature = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(signature).decode()

def send_weex_order(symbol, side, quantity, tp=None, sl=None):
    if not WEEX_API_KEY or WEEX_API_KEY == "":
        print(f"📡 [WEEX API] MOCK ORDER -> {side.upper()} {symbol}")
        return {"id": "mock", "status": "simulated"}

    method = "POST"
    request_path = "/capi/v2/order/placeOrder"
    query_string = ""
    order_type_weex = "1" if side == "buy" else "3" 

    # Tratamento de Símbolo
    s = symbol.lower()
    if "cmt_" in s: s = s.replace("cmt_", "") 
    s = s.replace("/", "").replace("_", "").replace("-", "").replace("usdt", "")
    formatted_symbol = s + "_usdt"

    body = {
        "symbol": "cmt_btcusdt", 
        "client_oid": str(int(time.time() * 1000)),
        "size": str(quantity), 
        "type": "2", # Market Order
        "order_type": "0",
        "side": order_type_weex,
        "match_price": "1" # Obrigatório na Weex
    }
    
    timestamp = str(int(time.time() * 1000))
    body_json = json.dumps(body)
    signature = generate_signature(WEEX_SECRET_KEY, timestamp, method, request_path, query_string, body_json)
    headers = {
        "ACCESS-KEY": WEEX_API_KEY, "ACCESS-SIGN": signature, "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": WEEX_PASSPHRASE, "Content-Type": "application/json", "locale": "en-US"
    }
    try:
        print(f"📡 [WEEX API] Sending Order to {formatted_symbol}...")
        response = requests.post("https://api-contract.weex.com" + request_path, headers=headers, data=body_json)
        print(f"🔙 [WEEX RES] Status: {response.status_code} | Body: {response.text}")
        return response.json()
    except Exception as e:
        print(f"❌ [WEEX ERROR] {str(e)}")
        return {"error": str(e)}

# =======================================================
# 3. CÉREBRO AI (AGORA USANDO GROQ CLOUD ⚡)
# =======================================================
def ask_ai_analysis(symbol, trend, volatility, adx, action):
    special_context = ""
    if "CRASH" in symbol.upper():
        special_context = "CRITICAL: SIMULATE A GLOBAL BLACK SWAN EVENT. MARKET IS CRASHING."

    system_prompt = "You are a senior hedge fund risk manager. Reply ONLY in JSON."
    user_prompt = f"""
    CONTEXT: {special_context}
    ASSET: {symbol}
    ACTION: {action.upper()}
    DATA: Trend={trend}, Volatility={volatility}, ADX={adx}
    
    RULES:
      1. If BLACK SWAN: BLOCK 'BUY'. APPROVE 'SELL'.
      2. If ADX > 60: Profile = "Parabolic".
      3. If Squeeze or ADX > 40: Profile = "Scalping".
      4. Else: Profile = "Standard".
    
    OUTPUT JSON: {{ "decision": "APPROVED"/"BLOCKED", "profile": "...", "reason": "..." }}
    """

    print(f"\n🧠 [AI ENGINE] Connecting to Groq Cloud (Llama 3)...")
    print(f"---------------- 📤 PROMPT SENT ----------------")
    print(f"USER: {user_prompt.strip()}")
    print(f"------------------------------------------------")

    if not GROQ_API_KEY:
        print("⚠️ [WARN] No API Key. Using Fallback.")
        return {"decision": "APPROVED", "profile": "Standard", "reason": "Fallback"}

    try:
        # URL da GROQ (A mais rápida do mundo)
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "model": "llama-3.3-70b-versatile", # Modelo super inteligente
            "temperature": 0.0
        }
        
        req_start = time.time()
        response = requests.post(url, headers=headers, json=payload)
        req_time = time.time() - req_start

        if response.status_code != 200:
            print(f"❌ [GROQ API ERROR] {response.text}")
            return {"decision": "APPROVED", "profile": "Standard", "reason": "API Error"}

        result = response.json()
        raw = result['choices'][0]['message']['content']
        
        # Limpar markdown se houver
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        ai_response = json.loads(cleaned)

        print(f"---------------- 📥 GROQ RESPONSE ({req_time:.4f}s) ----------------")
        print(json.dumps(ai_response, indent=2))
        print(f"-------------------------------------------------------------------")
        return ai_response

    except Exception as e:
        print(f"❌ [AI EXCEPTION] {e}")
        return {"decision": "APPROVED", "profile": "Standard", "reason": "Exception"}

# =======================================================
# 4. EXECUTOR
# =======================================================
def smart_execution(symbol, action, ai_profile, prices):
    print(f"\n⚙️  [EXECUTION ENGINE] Profile: {ai_profile.upper()}")
    
    if ai_profile == "Parabolic":
        print(f"🚀 [STRATEGY] MOON MISSION.")
        return send_weex_order(symbol, action, 0.03)
    elif ai_profile == "Standard":
        print(f"🌊 [STRATEGY] Trend Ride Mode.")
        return send_weex_order(symbol, action, 0.01)
    elif ai_profile == "Scalping":
        print(f"⚡ [STRATEGY] Scalping Mode.")
        return send_weex_order(symbol, action, 0.02)
    return send_weex_order(symbol, action, 0.01)

# =======================================================
# 5. ROTAS DE TESTE
# =======================================================
def process_signal(data):
    try:
        symbol = data.get('ticker')
        action = data.get('action')
        prices = {"sl": data.get('sl',0), "tp1": data.get('tp1',0), "tp2": data.get('tp2',0), "goldenZone": data.get('goldenZone',0)}
        
        print(f"\n" + "="*60)
        print(f"📩 [SIGNAL] {action.upper()} {symbol} | Reason: {data.get('reason')}")
        print("="*60)

        ai_result = ask_ai_analysis(symbol, data.get('trend'), data.get('volatility'), data.get('adx'), action)
        
        if ai_result.get('decision') == "BLOCKED":
            print(f"⛔ [AI VETO] Trade Blocked: {ai_result.get('reason')}")
            return jsonify({"status": "blocked"}), 200

        smart_execution(symbol, action, ai_result.get('profile', 'Standard'), prices)
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test_trend', methods=['GET'])
def test_trend():
    return process_signal({"ticker": "BTC_USDT", "action": "buy", "reason": "Fibo", "price": 95000, "adx": 20, "trend": "Uptrend", "volatility": "Normal"})

@app.route('/test_moon', methods=['GET'])
def test_moon():
    return process_signal({"ticker": "BTC_USDT", "action": "buy", "reason": "Combo", "price": 95000, "adx": 75, "trend": "Uptrend", "volatility": "Normal"})

@app.route('/test_crash', methods=['GET'])
def test_crash():
    return process_signal({"ticker": "CRASH_BTC", "action": "buy", "reason": "RSI", "price": 40000, "adx": 80, "trend": "Down", "volatility": "Extreme"})

@app.route('/webhook', methods=['POST'])
def webhook_listener():
    return process_signal(request.json)

if __name__ == '__main__':
    print("\n🟢 WEEX SENTINEL (POWERED BY GROQ LPU) - ONLINE")
    app.run(host='0.0.0.0', port=80)