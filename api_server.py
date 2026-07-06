import http.server
import json
import urllib.parse
import sys
import subprocess
import os
import pandas as pd
import numpy as np

TRADES_PATH = "/Users/Zhuanz/trading-risk-coach/trading_risk_coach/data/real_trades.csv"
M1_PATH = "/Users/Zhuanz/trading-risk-coach/trading_risk_coach/data/XAUUSD_M1.csv"
ADK_BIN_PATH = "/Users/Zhuanz/trading-risk-coach/venv/bin/adk"
PROJECT_ROOT = "/Users/Zhuanz/trading-risk-coach"

# Pre-load dataframes in memory at startup to keep queries ultra-fast (sub-millisecond)
print("Risk Coach API: Preloading datasets into memory...", flush=True)
try:
    TRADES_DF = pd.read_csv(TRADES_PATH)
    TRADES_DF["open_time"] = pd.to_datetime(TRADES_DF["open_time"])
    TRADES_DF["close_time"] = pd.to_datetime(TRADES_DF["close_time"])
    
    M1_DF = pd.read_csv(M1_PATH, parse_dates=["time"])
    print(f"Risk Coach API: Loaded {len(TRADES_DF)} trades and {len(M1_DF)} candles successfully!", flush=True)
except Exception as e:
    print(f"Risk Coach API: Preload error: {e}", flush=True)
    sys.exit(1)

class RiskCoachHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/cases":
            self.handle_cases()
        elif path == "/api/stats":
            self.handle_stats()
        elif path == "/api/replay":
            self.handle_replay(query)
        elif path == "/api/custom_replay":
            self.handle_custom_replay(query)
        elif path == "/api/run_agent":
            self.handle_run_agent(query)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def handle_stats(self):
        try:
            wins = TRADES_DF[TRADES_DF["pnl"] > 0]
            win_rate = round(len(wins) / len(TRADES_DF) * 100, 1) if len(TRADES_DF) > 0 else 0
            
            response = {
                "trades": len(TRADES_DF),
                "candles": len(M1_DF),
                "win_rate": win_rate,
                "disposition_ratio": 0.99
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def handle_cases(self):
        try:
            # Find the top 5 worst trades
            worst = TRADES_DF.sort_values(by="pnl").head(5)
            cases = []
            for _, row in worst.iterrows():
                open_time = row["open_time"]
                close_time = row["close_time"]
                
                # Align GMT+8 trade times to UTC K-line database times (8-hour shift)
                open_time_utc = open_time - pd.Timedelta(hours=8)
                close_time_utc = close_time - pd.Timedelta(hours=8)
                
                # Fetch M1 path for each of the worst cases
                win = M1_DF[(M1_DF["time"] >= open_time_utc) & (M1_DF["time"] <= close_time_utc)]
                prices = win["close"].tolist()
                
                if len(prices) > 45:
                    indices = np.linspace(0, len(prices)-1, 45, dtype=int)
                    prices = [prices[i] for i in indices]
                
                if prices:
                    prices[-1] = float(row["close_price"])
                else:
                    prices = [float(row["open_price"]), float(row["close_price"])]

                cases.append({
                    "id": str(row["position_id"]),
                    "direction": str(row["direction"]).upper(),
                    "lot_size": float(row["lot_size"]),
                    "open_price": float(row["open_price"]),
                    "close_price": float(row["close_price"]),
                    "open_time": open_time.strftime("%Y-%m-%d %H:%M"),
                    "close_time": close_time.strftime("%Y-%m-%d %H:%M"),
                    "actual_pnl": float(row["pnl"]),
                    "status": str(row["status"]),
                    "path": [round(p, 2) for p in prices]
                })
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(cases, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def handle_replay(self, query):
        try:
            position_id = int(query.get("position_id", [0])[0])
            row_matches = TRADES_DF[TRADES_DF["position_id"] == position_id]
            if row_matches.empty:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Position not found")
                return
            row = row_matches.iloc[0]
            
            open_time = row["open_time"]
            close_time = row["close_time"]
            
            # Align GMT+8 trade times to UTC K-line database times (8-hour shift)
            open_time_utc = open_time - pd.Timedelta(hours=8)
            close_time_utc = close_time - pd.Timedelta(hours=8)
            
            # Slice K-lines in memory instantly
            win = M1_DF[(M1_DF["time"] >= open_time_utc) & (M1_DF["time"] <= close_time_utc)]
            prices = win["close"].tolist()
            
            # Downsample to 45 points max
            if len(prices) > 45:
                indices = np.linspace(0, len(prices)-1, 45, dtype=int)
                prices = [prices[i] for i in indices]
            
            if prices:
                prices[-1] = float(row["close_price"])
            else:
                prices = [float(row["open_price"]), float(row["close_price"])]

            response = {
                "id": str(row["position_id"]),
                "direction": str(row["direction"]).upper(),
                "lot_size": float(row["lot_size"]),
                "open_price": float(row["open_price"]),
                "close_price": float(row["close_price"]),
                "open_time": open_time.strftime("%Y-%m-%d %H:%M"),
                "close_time": close_time.strftime("%Y-%m-%d %H:%M"),
                "actual_pnl": float(row["pnl"]),
                "status": str(row["status"]),
                "path": [round(p, 2) for p in prices]
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def handle_custom_replay(self, query):
        try:
            direction = query.get("direction", ["B"])[0].upper()
            entry = float(query.get("entry", [5100])[0])
            close = float(query.get("close", [5080])[0])
            lot = float(query.get("lot", [1.0])[0])
            
            # Generate random walk path with drift
            steps = 40
            step_size = (close - entry) / steps
            current = entry
            vol = abs(close - entry) * 0.15 or 5.0
            
            path = []
            for i in range(steps + 1):
                noise = (np.random.random() - 0.45) * vol
                current += step_size + noise
                path.append(round(current, 2))
            
            path[0] = round(entry, 2)
            path[-1] = round(close, 2)
            
            pnl_dir = 1 if direction == "B" else -1
            actual_pnl = (close - entry) * lot * 100 * pnl_dir
            
            response = {
                "id": "CUSTOM_" + str(int(np.random.randint(1000, 9999))),
                "direction": direction,
                "lot_size": lot,
                "open_price": entry,
                "close_price": close,
                "open_time": "Real-time",
                "close_time": "Real-time",
                "actual_pnl": actual_pnl,
                "path": path
            }
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def handle_run_agent(self, query):
        try:
            position_id = query.get("position_id", ["817860"])[0]
            sl = query.get("sl", ["5.0"])[0]
            breaker = query.get("breaker", ["10.0"])[0]

            # Construct prompt target for the ADK agents
            prompt = f"Please perform a historical risk simulation for position {position_id}, assessing what would happen if a stop loss of {sl} points and a breaker of {breaker} points were set. Provide the final risk diagnostic recommendation."
            
            # Command to run root agent in automated mode
            cmd = [
                ADK_BIN_PATH,
                "run",
                os.path.join(PROJECT_ROOT, "trading_risk_coach"),
                "--default_llm_model",
                "gemini-3.1-flash-lite",
                prompt
            ]
            
            # Execute synchronously
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            
            stdout_text = result.stdout or ""
            stderr_text = result.stderr or ""
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "stdout": stdout_text,
                "stderr": stderr_text,
                "status_code": result.returncode
            }, ensure_ascii=False).encode("utf-8"))
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

def run():
    server_address = ('127.0.0.1', 8123)
    httpd = http.server.HTTPServer(server_address, RiskCoachHandler)
    print("Risk Coach Local API Server running on http://127.0.0.1:8123", flush=True)
    httpd.serve_forever()

if __name__ == '__main__':
    run()
