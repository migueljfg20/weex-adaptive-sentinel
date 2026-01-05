import os, time, json, hmac, hashlib, base64
import requests
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ======================================================
# CONFIG
# ======================================================
WEEX_BASE_URL = "https://api-contract.weex.com"
WEEX_API_KEY = os.getenv("WEEX_API_KEY")
WEEX_SECRET_KEY = os.getenv("WEEX_SECRET_KEY")
WEEX_PASSPHRASE = os.getenv("WEEX_PASSPHRASE")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") # ⚠️ Usa a mesma variavel que ja tens no .env
WEEX_LOCALE = "en-US"

SYMBOLS = ["cmt_btcusdt", "cmt_xrpusdt"]

# 💾 MEMÓRIA LOCAL PARA GUARDAR TP/SL VISUALMENTE
TRADES_MEMORY = {} 

SYMBOL_RULES = {
    "cmt_xrpusdt": {"size_step": 10, "min_size": 10, "decimals": 0},
    "cmt_btcusdt": {"size_step": 0.001, "min_size": 0.001, "decimals": 3},
}

RISK_PER_TRADE = 0.03

# ======================================================
# LOG
# ======================================================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def log_weex_request(title, method, url, body, response):
    log(f"--- {title} ---")
    log(f"METHOD: {method}")
    log(f"URL: {url}")
    log(f"BODY: {json.dumps(body, ensure_ascii=False)}")
    log(f"RESPONSE: {json.dumps(response, ensure_ascii=False)}")
    log(f"--- END {title} ---")

# ======================================================
# 🧠 CÉREBRO AI (GROQ CLOUD - LLAMA 3.3)
# ======================================================
def ask_groq_analysis(symbol, trend, volatility, adx, action):
    log(f"🧠 [AI] Connecting to Groq (Llama 3.3)...")
    
    system_prompt = "You are a Quant Execution Algo. Logic is absolute. Reply ONLY in JSON."
    
    user_prompt = f"""
    ASSET: {symbol} | ACTION: {action.upper()}
    DATA: Trend={trend}, Volatility={volatility}, ADX={adx}
    
    LOGIC RULES:
    
    1. **CHECK BLACK SWAN** (Crash Scenario):
       - IF (Trend == 'Downtrend' AND ADX > 50 AND Action == 'SELL'): Profile = "BlackSwan"
       
    2. **CHECK ALIGNMENT**:
       - IF (Trend == 'Uptrend' AND Action == 'BUY') -> APPROVED.
       - IF (Trend == 'Downtrend' AND Action == 'SELL') -> APPROVED.
       - IF OPPOSITE: 
           - IF ADX < 25: APPROVED (Choppy).
           - ELSE: BLOCKED.

    3. **ASSIGN PROFILE** (If APPROVED and not BlackSwan):
       - IF ADX > 50: Profile = "Parabolic"
       - IF Volatility == "Squeeze Breakout" OR ADX < 25: Profile = "Scalping"
       - ELSE: Profile = "Standard"
       
    OUTPUT JSON: {{ "decision": "APPROVED" or "BLOCKED", "profile": "Standard"/"Scalping"/"Parabolic"/"BlackSwan", "reason": "Logic" }}
    """

    print(f"\n--- 📤 TO GROQ ---\n{user_prompt.strip()}\n------------------\n")

    if not GROQ_API_KEY: return {"decision": "APPROVED", "profile": "Standard", "reason": "No Key"}

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"}
        payload = {
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.0
        }
        
        req_start = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            log(f"❌ [AI ERROR] {response.text}")
            return {"decision": "APPROVED", "profile": "Standard", "reason": "API Error"}

        result = response.json()
        raw = result['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
        ai_res = json.loads(raw)
        
        print(f"--- 📥 FROM GROQ ({time.time()-req_start:.2f}s) ---\n{json.dumps(ai_res, indent=2)}\n--------------------")
        return ai_res

    except Exception as e:
        log(f"❌ [AI EXCEPTION] {e}")
        return {"decision": "APPROVED", "profile": "Standard", "reason": str(e)}

# ======================================================
# WEEX SIGN / REQUEST
# ======================================================
def sign(method, path, query=None, body=None):
    ts = str(int(time.time() * 1000))
    query = query or {}
    body = body or {}
    qs = urlencode(sorted(query.items())) if query else ""
    bs = json.dumps(body, separators=(",", ":")) if body else ""
    msg = ts + method + path + (f"?{qs}" if qs else "") + bs
    sig = hmac.new(WEEX_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()
    signature = base64.b64encode(sig).decode()
    headers = {
        "ACCESS-KEY": WEEX_API_KEY, "ACCESS-SIGN": signature,
        "ACCESS-PASSPHRASE": WEEX_PASSPHRASE, "ACCESS-TIMESTAMP": ts,
        "Content-Type": "application/json", "locale": WEEX_LOCALE
    }
    return headers, qs, bs

def req(method, path, query=None, body=None):
    headers, qs, bs = sign(method, path, query, body)
    url = WEEX_BASE_URL + path + (f"?{qs}" if qs else "")
    try: return requests.request(method, url, headers=headers, data=bs, timeout=10).json()
    except Exception as e: 
        log(f"REQ ERROR: {e}")
        return {}

def data(x):
    if isinstance(x, dict): return x.get("data", {}).get("list", []) or x.get("list", []) or []
    return x or []

# ======================================================
# WEEX ENDPOINTS
# ======================================================
def api_positions(): return data(req("GET", "/capi/v2/account/position/allPosition"))
def api_orders(sym): return data(req("GET", "/capi/v2/order/current", {"symbol": sym}))
def api_plans(sym): return data(req("GET", "/capi/v2/order/currentPlan", {"symbol": sym}))
def api_history(sym): return data(req("GET", "/capi/v2/order/history", {"symbol": sym, "pageSize": 20}))
def api_assets(): return data(req("GET", "/capi/v2/account/assets"))
def api_fills(sym): return data(req("GET", "/capi/v2/order/fills", {"symbol": sym, "pageSize": 100}))

# ⚠️ FUNÇÃO NOVA PARA LIMPAR ERROS DE PRECONDITION
def api_cancel_all(sym):
    return req("POST", "/capi/v2/order/cancelAll", body={"symbol": sym})

def api_close(sym):
    # Ao fechar, limpa a memória visual
    if sym in TRADES_MEMORY: del TRADES_MEMORY[sym]
    return req("POST", "/capi/v2/order/closePositions", body={"symbol": sym})

def api_place_order(sym, side, size):
    path = "/capi/v2/order/placeOrder"
    body = {"symbol": sym, "size": str(size), "type": "1" if side == "buy" else "3", "order_type": "0", "match_price": "1", "client_oid": str(int(time.time()*1000))}
    headers, qs, bs = sign("POST", path, body=body)
    try: 
        r = requests.post(WEEX_BASE_URL+path, headers=headers, data=bs, timeout=10).json()
        log_weex_request("PLACE ORDER", "POST", path, body, r)
        return r
    except Exception as e: return {"error": str(e)}

def api_tpsl(sym, planType, price, size, posSide):
    path = "/capi/v2/order/placeTpSlOrder"
    body = {"symbol": sym, "planType": planType, "triggerPrice": str(price), "executePrice": "0", "size": str(size), "positionSide": posSide, "marginMode": 1, "clientOrderId": str(int(time.time()*1000))}
    headers, qs, bs = sign("POST", path, body=body)
    try: 
        r = requests.post(WEEX_BASE_URL+path, headers=headers, data=bs, timeout=10).json()
        log_weex_request(f"TPSL {planType}", "POST", path, body, r)
        return r
    except Exception as e: return {"error": str(e)}

# ======================================================
# HELPERS 
# ======================================================
def sf(x):
    try: return float(x)
    except: return 0.0

def adjust_size(sym, s):
    s = float(s)
    rules = SYMBOL_RULES.get(sym, {"size_step": 1, "min_size": 1, "decimals": 0})
    step = rules["size_step"]
    steps_count = int(s / step)
    final_size = max(steps_count * step, rules["min_size"])
    return f"{final_size:.{rules['decimals']}f}"

def format_price(sym, price):
    try:
        p = float(price)
        rules = SYMBOL_RULES.get(sym, {"decimals_price": 2})
        return f"{p:.{rules['decimals_price']}f}"
    except: return str(price)

def sanitize_price(sym, val, fallback_price, default_pct=0.01):
    try:
        f_val = float(val)
        if str(f_val).lower() == 'nan' or f_val == 0: raise ValueError()
        return format_price(sym, f_val)
    except: return format_price(sym, fallback_price * (1 + default_pct))

def get_position(sym):
    for p in api_positions():
        if p.get("symbol") == sym and sf(p.get("size")) > 0: return p
    return None

def get_usdt_available():
    for a in api_assets():
        if a.get("coinName") == "USDT":
            try: return float(a.get("available", 0))
            except: return 0.0
    return 0.0

def format_ts(ts):
    if not ts: return "-"
    try:
        ts = int(ts)
        if ts > 10000000000: ts = ts / 1000
        return datetime.fromtimestamp(ts).strftime('%d/%m %H:%M:%S')
    except: return "-"

def calculate_size_by_margin(symbol, entry_price, risk_pct=RISK_PER_TRADE):
    usdt_available = get_usdt_available()
    if usdt_available <= 0 or entry_price <= 0: return adjust_size(symbol, 0)
    
    leverage = 20 
    for p in api_positions():
        if p.get("symbol") == symbol:
            try: leverage = float(p.get("leverage", 20))
            except: pass
            break
            
    margin_usdt = usdt_available * risk_pct
    position_value_usdt = margin_usdt * leverage
    raw_size_coins = position_value_usdt / entry_price
    final_size = adjust_size(symbol, raw_size_coins)
    
    log(f"🔢 CALC {symbol}: Avail=${usdt_available:.2f} | RiskP={risk_pct*100}% | Size={final_size}")
    return final_size

# ======================================================
# CORE TRADING
# ======================================================
def handle_signal(sig):
    sym = "cmt_" + sig["ticker"].lower()
    action = sig["action"]
    side = "buy" if action == "buy" else "sell"
    entry_price = float(sig.get("price", 0))

    # 1. AI CHECK
    ai_trend = sig.get('trend', 'Unknown')
    ai_vol = sig.get('volatility', 'Normal')
    ai_adx = sig.get('adx', 0)
    ai_result = ask_groq_analysis(sym, ai_trend, ai_vol, ai_adx, action)
    
    decision = ai_result.get("decision", "APPROVED")
    profile = ai_result.get("profile", "Standard")
    
    # REGRA BLACK SWAN: SÓ VENDA
    if profile == "BlackSwan" and side == "buy":
        log(f"⛔ [AI VETO] BLACK SWAN MODE: BUY BLOCKED.")
        return

    if decision == "BLOCKED":
        log(f"⛔ [AI VETO] Trade BLOCKED.")
        return

    # 2. DEFINIR RISCO E TARGETS
    risk_to_use = RISK_PER_TRADE 
    target_price = 0.0

    raw_tp1 = float(sig.get("tp1", 0))
    raw_tp2 = float(sig.get("tp2", 0))

    # Lógica de Estratégia
    if profile == "Scalping":
        risk_to_use = 0.015
        target_price = raw_tp1
    elif profile == "Standard":
        risk_to_use = 0.03
        target_price = raw_tp2
    elif profile == "Parabolic" or profile == "BlackSwan":
        risk_to_use = 0.04
        # Target muito longe (5x a distancia do TP2)
        dist = abs(raw_tp2 - entry_price)
        if side == "buy": target_price = entry_price + (dist * 5)
        else: target_price = entry_price - (dist * 5)
        
    log(f"⚙️ [PROFILE] {profile.upper()} | Risk: {risk_to_use*100}% | Target Mode: {'TP1' if profile=='Scalping' else 'TP2+'}")

    # 3. LIMPEZA E FECHO
    log(f"🧹 CLEANING OLD ORDERS...")
    api_cancel_all(sym)
    
    pos = get_position(sym)
    if pos:
        current_side = pos.get("side", "").lower()
        desired_side = "long" if side == "buy" else "short"
        if current_side and current_side != desired_side:
            log(f"⚠️ CLOSING OPPOSITE POSITION")
            api_close(sym)
            time.sleep(2) # Espera Weex processar

    # 4. ENTRADA
    size = calculate_size_by_margin(sym, entry_price, risk_pct=risk_to_use)
    log(f"🚀 SIGNAL {sym} {side.upper()} @ {entry_price} | Size: {size}")
    
    entry_res = api_place_order(sym, side, size)
    if "code" in entry_res and entry_res["code"] not in ["0", "00000"]:
        log(f"❌ ENTRY FAILED: {entry_res}")
        return

    # ⚠️ ESPERA MAIOR PARA EVITAR ERRO DE TP
    time.sleep(3)

    # 5. TPSL SETTING
    sl = sanitize_price(sym, sig.get("sl"), entry_price, -0.01 if side=="buy" else 0.01) 
    tp = sanitize_price(sym, target_price, entry_price, 0.02 if side=="buy" else -0.02)
    
    # Garante que TP é válido matematicamente
    if side == "buy" and float(tp) <= entry_price: 
        tp = sanitize_price(sym, entry_price * 1.015, entry_price) # Força 1.5%
    if side == "sell" and float(tp) >= entry_price:
        tp = sanitize_price(sym, entry_price * 0.985, entry_price)

    pos_side = "long" if side == "buy" else "short"

    # Envia SL
    api_tpsl(sym, "loss_plan", sl, size, pos_side)
    # Envia TP (Total)
    api_tpsl(sym, "profit_plan", tp, size, pos_side)
    
    TRADES_MEMORY[sym] = {"sl": sl, "tp": f"{tp} ({profile})"}
    log(f"✅ SETUP OK | SL: {sl} | TP: {tp}")

# ======================================================
# WEBHOOK
# ======================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        sig = request.get_json(force=True, silent=True)
        if not sig:
            data = request.data.decode("utf-8")
            sig = json.loads(data)
        # ⚠️ LOG COMPLETO RESTAURADO COMO PEDISTE
        log(f"📥 WEBHOOK: {sig}")
        handle_signal(sig)
        return jsonify({"status": "ok"})
    except Exception as e:
        log(f"❌ WEBHOOK ERROR: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 400

# ======================================================
# DASHBOARD
# ======================================================
@app.route("/")
def dashboard():
    orders, fills = [], []
    detailed_positions = []
    
    for s in SYMBOLS:
        for o in api_orders(s): o["symbol"]=s; orders.append(o)
        for f in api_fills(s): f["symbol"]=s; fills.append(f)
        pos = get_position(s)
        if pos:
            # Tenta pegar da Memória primeiro, fallback para "-"
            mem = TRADES_MEMORY.get(s, {})
            display_sl = mem.get("sl", "-")
            display_tp = mem.get("tp", "-")
            
            detailed_positions.append({
                "symbol": s, "side": (pos.get("side") or "").upper(), "size": pos.get("size"),
                "entry": round(sf(pos.get("open_value"))/sf(pos.get("size")), 4) if sf(pos.get("size")) else 0,
                "leverage": pos.get("leverage", "-"), "upnl": pos.get("unrealizePnl", "-"),
                "sl": display_sl, "tp": display_tp
            })

    fills.sort(key=lambda x: int(x.get("createdTime", 0)), reverse=True)
    last_trade = fills[0] if fills else None

    # ESTATÍSTICAS COMPLETAS (W/L/BE)
    wins = 0; losses = 0; breakevens = 0; total_pnl = 0.0
    
    for f in fills:
        pnl = sf(f.get("realizePnl"))
        # Considera trade válida mesmo se 0 (break-even)
        total_pnl += pnl
        if pnl > 0.0001: wins += 1
        elif pnl < -0.0001: losses += 1
        else: breakevens += 1
            
    total_trades = wins + losses + breakevens
    win_rate = round((wins / total_trades) * 100, 2) if total_trades > 0 else 0
    
    usdt_available = 0
    for a in api_assets():
        if a.get("coinName") == "USDT": usdt_available = sf(a.get("available"))

    return render_template_string("""
<!DOCTYPE html>
<html>
<head><meta http-equiv="refresh" content="5"><title>WEEX AI WARRIOR</title>
<style>body{background:#0d1117;color:#c9d1d9;font-family:Consolas;padding:20px}.box{background:#161b22;padding:15px;margin-bottom:15px;border-radius:8px;border:1px solid #30363d}.green{color:#3fb950}.red{color:#f85149}.blue{color:#58a6ff}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:#8b949e;border-bottom:1px solid #30363d;padding:5px}td{padding:5px;border-bottom:1px solid #21262d}.badge{padding:2px 6px;border-radius:4px;font-weight:bold;font-size:11px}.b-green{background:rgba(63,185,80,0.2);color:#3fb950}.b-red{background:rgba(248,81,73,0.2);color:#f85149}</style>
</head><body>
<h1>🧠 WEEX AI WARRIOR (GROQ POWERED)</h1>
<div style="display:flex;gap:15px">
  <div class="box">USDT: <b>${{usdt_available}}</b></div>
  <div class="box">PnL: <b class="{{'green' if total_pnl>=0 else 'red'}}">${{total_pnl}}</b></div>
  <div class="box">WinRate: <b>{{win_rate}}%</b> <span style="font-size:11px;color:#8b949e">({{wins}}W / {{losses}}L / {{breakevens}}BE) | Total: {{total_trades}}</span></div>
</div>
{% if last_trade %}<div class="box"><b>LAST:</b> {{last_trade.symbol}} | <span class="{{'green' if sf(last_trade.realizePnl)>0 else 'red'}}">${{last_trade.realizePnl}}</span> | {{format_ts(last_trade.createdTime)}}</div>{% endif %}
<div class="box"><b>OPEN POSITIONS</b><table><thead><tr><th>SYM</th><th>SIDE</th><th>SIZE</th><th>ENTRY</th><th>TP</th><th>SL</th><th>uPNL</th></tr></thead><tbody>{% for p in detailed_positions %}<tr><td>{{p.symbol}}</td><td><span class="badge {{'b-green' if p.side=='LONG' else 'b-red'}}">{{p.side}}</span></td><td>{{p.size}}</td><td>{{p.entry}}</td><td class="green">{{p.tp}}</td><td class="red">{{p.sl}}</td><td class="{{'green' if sf(p.upnl)>0 else 'red'}}">{{p.upnl}}</td></tr>{% endfor %}</tbody></table></div>
<div class="box"><b>ORDERS</b><table><thead><tr><th>SYM</th><th>SIDE</th><th>TYPE</th><th>PRICE</th><th>SIZE</th></tr></thead><tbody>{% for o in orders %}<tr><td>{{o.symbol}}</td><td>{{o.side}}</td><td>{{o.type}}</td><td>{{o.price or o.triggerPrice}}</td><td>{{o.size}}</td></tr>{% endfor %}</tbody></table></div>
<div class="box"><b>HISTORY (LAST 5)</b><table><thead><tr><th>TIME</th><th>SYM</th><th>SIDE</th><th>PnL</th></tr></thead><tbody>{% for f in fills[:5] %}<tr><td>{{format_ts(f.createdTime)}}</td><td>{{f.symbol}}</td><td>{{f.side}}</td><td class="{{'green' if sf(f.realizePnl)>0 else 'red'}}">{{f.realizePnl}}</td></tr>{% endfor %}</tbody></table></div>
</body></html>
""", usdt_available=round(usdt_available,2), total_pnl=round(total_pnl,2), win_rate=win_rate, wins=wins, losses=losses, breakevens=breakevens, total_trades=total_trades, last_trade=last_trade, detailed_positions=detailed_positions, orders=orders, fills=fills, sf=sf, format_ts=format_ts)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
