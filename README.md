# Weex Adaptive Sentinel 🛡️🤖

> **A Hybrid Math-AI Trading Engine for Weex Futures**
> *Built for the DoraHacks Weex AI Trading Hackathon*

## 🚀 Project Overview
Weex Adaptive Sentinel solves the "Black Box" problem of AI trading. Instead of letting AI hallucinate price predictions, we use a **separation of concerns** architecture:
1.  **The Math Engine (Pine Script):** Handles deterministic structure, Fibonacci levels, and technical entry triggers.
2.  **The AI Engine (Python + Groq LPU):** Acts as a Strategic Manager, analyzing volatility (ADX) and global sentiment to switch execution profiles or veto trades (Kill Switch).

## 🧠 Architecture
`[TradingView Webhook]` --> `[Python Flask Server]` --> `[Groq AI Analysis]` --> `[Weex Execution]`

*   **Signal:** Generates TP1, TP2, and Golden Zone targets based on market structure.
*   **AI Logic:**
    *   **Standard Mode:** Rides the trend to TP2.
    *   **Scalping Mode:** Takes profit at TP1 and flips at the Golden Zone.
    *   **Crash Protocol:** Blocks BUY orders during "Black Swan" events.

## 🛠️ Tech Stack
*   **Signal Generation:** TradingView (Pine Script v5)
*   **Backend:** Python (Flask)
*   **AI Model:** Llama 3 via Groq Cloud (Low Latency Inference)
*   **Exchange:** Weex Futures API

## ⚙️ Setup
1.  Clone the repo.
2.  Install dependencies: `pip install flask requests`
3.  Add your API Keys in `main.py`:
    ```python
    WEEX_API_KEY = "..."
    GROK_API_KEY = "..."
    ```
4.  Run the server: `python main.py`

## ⚠️ Disclaimer
This software is for educational and hackathon demonstration purposes. Use at your own risk.
