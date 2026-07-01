import os
import re
import glob
import json
import pandas as pd

reports_dir = "/Users/Zhuanz/Downloads/latest_reports"
html_output_path = "/Users/Zhuanz/deals_analysis_preview.html"

html_files = glob.glob(os.path.join(reports_dir, "*.html"))
print(f"Found {len(html_files)} HTML files to parse.")

# We will collect all deals (both IN and OUT) first
all_raw_deals = []

for file_path in html_files:
    filename = os.path.basename(file_path)
    acct_match = re.match(r"^(\d+)_", filename)
    account_num = acct_match.group(1) if acct_match else "Unknown"
    
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    if not tbody_match:
        continue
        
    tbody_content = tbody_match.group(1)
    rows = re.findall(r"<tr>(.*?)</tr>", tbody_content, re.DOTALL)
    
    for row in rows:
        tds = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)
        if len(tds) < 11:
            continue
            
        ticket = tds[0].strip()
        time_str = tds[1].strip()
        symbol = tds[2].strip()
        type_str = tds[3].strip()
        entry = tds[4].strip()
        volume_str = tds[5].strip()
        price_str = tds[6].strip()
        commission_str = tds[7].strip()
        swap_str = tds[8].strip()
        profit_str = tds[9].strip()
        comment = tds[10].strip()
        
        clean_type = re.sub(r"<[^>]*>", "", type_str).upper()
        
        def clean_money(text):
            text = re.sub(r"<[^>]*>", "", text)
            text = text.replace("$", "").replace(",", "").replace(" ", "").strip()
            try:
                return float(text)
            except ValueError:
                return 0.0
                
        profit_val = clean_money(profit_str)
        commission_val = clean_money(commission_str)
        swap_val = clean_money(swap_str)
        net_val = profit_val + commission_val + swap_val
        
        try:
            date_val = time_str.split(" ")[0].replace(".", "-")
        except Exception:
            date_val = "Unknown"
            
        all_raw_deals.append({
            "Account": account_num,
            "Date": date_val,
            "Time": time_str,
            "Ticket": ticket,
            "Symbol": symbol,
            "Type": clean_type,
            "Entry": entry.upper(),
            "Volume": volume_str,
            "Price": price_str,
            "Commission": commission_val,
            "Swap": swap_val,
            "Profit": profit_val,
            "Net Profit": net_val,
            "Comment": comment,
            "SourceFile": filename
        })

# Perform comment inheritance from IN to OUT deals
processed_deals = []
df_raw = pd.DataFrame(all_raw_deals)

if not df_raw.empty:
    # De-duplicate to avoid processing duplicates
    df_raw = df_raw.drop_duplicates(subset=["Account", "Ticket"])
    
    for acct, acct_df in df_raw.groupby("Account"):
        # Sort by Time to process chronologically
        acct_df = acct_df.sort_values(by="Time")
        open_positions = {} # symbol -> list of IN deals
        
        for idx, row in acct_df.iterrows():
            deal = row.to_dict()
            symbol = deal["Symbol"]
            entry = deal["Entry"]
            
            if entry == "IN":
                open_positions.setdefault(symbol, []).append(deal)
            elif entry == "OUT":
                # Try to inherit comment from the corresponding IN deal
                matching_in = None
                if symbol in open_positions and open_positions[symbol]:
                    # Find first opposite type open position
                    opposite_type = "SELL" if deal["Type"] == "BUY" else "BUY"
                    for o_deal in open_positions[symbol]:
                        if o_deal["Type"] == opposite_type:
                            matching_in = o_deal
                            open_positions[symbol].remove(o_deal)
                            break
                            
                if matching_in:
                    deal["Comment"] = matching_in["Comment"]
                processed_deals.append(deal)
            else:
                # BALANCE etc.
                processed_deals.append(deal)

df_deals = pd.DataFrame(processed_deals)
if df_deals.empty:
    print("No deals found after processing!")
    exit(1)

# Dates of interest for the last week (June 21 to June 26)
target_dates = ["2026-06-21", "2026-06-22", "2026-06-23", "2026-06-24", "2026-06-25", "2026-06-26"]

# Filter to only contain last week's deals
df_deals = df_deals[df_deals["Date"].isin(target_dates)]

# Filter to only contain AI-related trades
df_deals = df_deals[df_deals["Comment"].str.contains("AI|deepseek", case=False, na=False)]

# Generate cumulative P&L stats for each account
accounts = df_deals["Account"].unique().tolist()
chart_data = {}
account_summaries = []

for acct in accounts:
    acct_deals = df_deals[df_deals["Account"] == acct]
    
    # Calculate cumulative metrics (only for this week)
    total_trades = len(acct_deals)
    wins = acct_deals[acct_deals["Profit"] > 0]
    losses = acct_deals[acct_deals["Profit"] < 0]
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    
    cum_win = acct_deals.loc[acct_deals["Profit"] > 0, "Profit"].sum()
    cum_loss = acct_deals.loc[acct_deals["Profit"] < 0, "Profit"].sum()
    cum_commission = acct_deals["Commission"].sum()
    real_net = acct_deals["Net Profit"].sum()
    
    avg_win = acct_deals.loc[acct_deals["Profit"] > 0, "Profit"].mean() if len(wins) > 0 else 0.0
    avg_loss = abs(acct_deals.loc[acct_deals["Profit"] < 0, "Profit"].mean()) if len(losses) > 0 else 0.0
    ratio = (avg_loss / avg_win) if avg_win > 0 else 0.0
    
    # Determine risk state
    if ratio >= 1.5:
        risk_level = "DANGER"
        risk_desc = f"⚠️ 警报：处置效应严重 (均损是均赢的 {ratio:.2f} 倍)！存在小赚大亏扛单恶习。"
    elif real_net < 0:
        risk_level = "WARNING"
        risk_desc = "⚠️ 警报：交易处于净亏损状态，策略表现不佳，需优化盈亏期望。"
    else:
        risk_level = "SAFE"
        risk_desc = "✅ 安全：交易期望值为正，风控及盈亏比指标合理。"

    account_summaries.append({
        "Account": acct,
        "TotalTrades": total_trades,
        "WinRate": f"{win_rate:.1f}%",
        "WinCount": len(wins),
        "LossCount": len(losses),
        "CumWin": f"${cum_win:.2f}",
        "CumLoss": f"${cum_loss:.2f}",
        "Commission": f"${cum_commission:.2f}",
        "RealNetProfit": real_net,
        "RealNetProfitStr": f"${real_net:.2f}",
        "AvgWin": f"${avg_win:.2f}",
        "AvgLoss": f"${avg_loss:.2f}",
        "Ratio": f"{ratio:.2f}x",
        "RiskLevel": risk_level,
        "RiskDesc": risk_desc
    })
    
    # Calculate daily P&L for the target week starting from 0.0
    daily_net = []
    current_cum = 0.0
    daily_net.append(current_cum)
    
    for d in target_dates:
        day_deals = acct_deals[acct_deals["Date"] == d]
        day_profit = day_deals["Net Profit"].sum()
        current_cum += day_profit
        daily_net.append(current_cum)
        
    chart_data[acct] = daily_net

# Labels for chart include "Start" then the dates
chart_labels = ["Start"] + [d.replace("2026-", "") for d in target_dates]

# Embed JSON data in HTML
chart_data_json = json.dumps(chart_data)
chart_labels_json = json.dumps(chart_labels)
account_summaries_json = json.dumps(account_summaries)

html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MT5 Multi-Account Weekly Performance Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #080c14;
            --bg-secondary: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.45);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --border-color: rgba(255, 255, 255, 0.07);
            
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', sans-serif;
        }}

        body {{
            background-color: var(--bg-primary);
            color: var(--text-primary);
            padding: 2rem;
            min-height: 100vh;
            background-image: 
                radial-gradient(circle at 5% 5%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 95% 95%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
        }}

        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 2.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.4rem;
            font-weight: 800;
            background: linear-gradient(135deg, #60a5fa 0%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
            margin-top: 0.25rem;
        }}

        /* Grid Layout */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: 1.8fr 1.2fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }}

        @media (max-width: 1024px) {{
            .dashboard-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Glassmorphism Cards */
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 2rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
        }}

        .card:hover {{
            border-color: rgba(255, 255, 255, 0.12);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        }}

        .card-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: #93c5fd;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        /* Active Accounts Toggles */
        .toggle-container {{
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
        }}

        .toggle-btn {{
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.5rem 1rem;
            border-radius: 30px;
            cursor: pointer;
            font-weight: 500;
            font-size: 0.85rem;
            transition: all 0.2s ease;
        }}

        .toggle-btn:hover {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
        }}

        .toggle-btn.active {{
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
        }}

        /* Apex/Chart container */
        .chart-wrapper {{
            height: 380px;
            position: relative;
        }}

        /* KPI cards list */
        .account-cards-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-height: 520px;
            overflow-y: auto;
            padding-right: 0.5rem;
        }}

        /* Custom Scrollbar */
        .account-cards-list::-webkit-scrollbar {{
            width: 6px;
        }}
        .account-cards-list::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }}

        .acct-card {{
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 14px;
            padding: 1.25rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .acct-card:hover {{
            background: rgba(255, 255, 255, 0.03);
            border-color: rgba(255, 255, 255, 0.1);
            transform: translateX(3px);
        }}

        .acct-card.selected {{
            border-color: var(--accent-blue);
            background: rgba(59, 130, 246, 0.06);
        }}

        .acct-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }}

        .acct-id {{
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 1.1rem;
            color: #ffffff;
        }}

        .acct-profit {{
            font-weight: 700;
            font-size: 1.15rem;
        }}

        .acct-profit.plus {{
            color: var(--success);
            text-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
        }}

        .acct-profit.minus {{
            color: var(--danger);
            text-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
        }}

        .acct-meta-row {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .meta-val {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        /* Detail Panel Card */
        .details-panel {{
            grid-column: span 2;
        }}

        .details-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-top: 1rem;
        }}

        .kpi-box {{
            background: rgba(15, 23, 42, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
        }}

        .kpi-title {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }}

        .kpi-val {{
            font-size: 1.6rem;
            font-weight: 700;
            font-family: 'Outfit', sans-serif;
        }}

        /* Win Rate Ring and Progress Bar */
        .progress-bar-bg {{
            background: rgba(255, 255, 255, 0.05);
            height: 8px;
            border-radius: 4px;
            margin-top: 0.5rem;
            overflow: hidden;
        }}

        .progress-bar-fill {{
            background: linear-gradient(90deg, var(--accent-blue) 0%, var(--accent-purple) 100%);
            height: 100%;
            border-radius: 4px;
            width: 0%;
            transition: width 1s ease-in-out;
        }}

        /* Alerts and Risk Badges */
        .risk-badge {{
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 700;
        }}

        .risk-badge.SAFE {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .risk-badge.WARNING {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .risk-badge.DANGER {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
            border: 1px solid rgba(239, 68, 68, 0.3);
            animation: pulse 2s infinite;
        }}

        .risk-banner {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.25rem;
            margin-top: 1.5rem;
        }}

        .risk-banner.DANGER {{
            border-color: rgba(239, 68, 68, 0.2);
            background: rgba(239, 68, 68, 0.03);
        }}

        .risk-banner.WARNING {{
            border-color: rgba(245, 158, 11, 0.2);
            background: rgba(245, 158, 11, 0.03);
        }}

        @keyframes pulse {{
            0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }}
            70% {{ box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
        }}
    </style>
</head>
<body>

<div class="container">
    <header>
        <div>
            <h1>多账户交易曲线监测分析大屏</h1>
            <p class="subtitle">最近一周（6月21日 - 6月28日）已平仓交易真实盈亏（剔除充值本金）</p>
        </div>
        <div>
            <span class="risk-badge DANGER" style="font-size: 0.85rem; padding: 0.5rem 1rem;">
                ⚠️ 包含高风险预警账户
            </span>
        </div>
    </header>

    <div class="dashboard-grid">
        <!-- Chart Column -->
        <div class="card">
            <div class="card-title">
                <span>📈 累计资金曲线变化 (P&L Trend)</span>
                <div class="toggle-container" id="chart-toggles">
                    <!-- Toggles inserted by JS -->
                </div>
            </div>
            <div class="chart-wrapper">
                <canvas id="pnlLineChart"></canvas>
            </div>
        </div>

        <!-- Accounts Performance Sidebar -->
        <div class="card">
            <div class="card-title">
                <span>📋 各账号累计交易绩效</span>
            </div>
            <div class="account-cards-list" id="acct-list-container">
                <!-- Cards inserted by JS -->
            </div>
        </div>

        <!-- Selected Account Detail Panel -->
        <div class="card details-panel" id="detail-panel" style="display: none;">
            <div class="card-title">
                <span id="detail-title">🔍 账户详情诊断</span>
                <span id="detail-risk-badge" class="risk-badge">SAFE</span>
            </div>
            
            <div class="details-grid">
                <div class="kpi-box">
                    <div class="kpi-title">累计交易净利润 (Net Profit)</div>
                    <div class="kpi-val" id="kpi-net-profit">$0.00</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-title">交易胜率 (Win Rate)</div>
                    <div class="kpi-val" id="kpi-win-rate">0.0%</div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" id="kpi-win-rate-fill"></div>
                    </div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-title">总交易笔数 (Trades)</div>
                    <div class="kpi-val" id="kpi-trades">0</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-title">盈亏均比 (Avg Loss / Win)</div>
                    <div class="kpi-val" id="kpi-loss-ratio">1.00x</div>
                </div>
            </div>

            <div class="details-grid" style="margin-top: 1rem;">
                <div class="kpi-box">
                    <div class="kpi-title">累计毛盈利 / 毛亏损</div>
                    <div style="display: flex; justify-content: space-between; margin-top: 0.5rem;">
                        <span style="color: var(--success); font-weight: 600;" id="kpi-cum-win">+$0.00</span>
                        <span style="color: var(--danger); font-weight: 600;" id="kpi-cum-loss">-$0.00</span>
                    </div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-title">平均单笔盈利 / 亏损</div>
                    <div style="display: flex; justify-content: space-between; margin-top: 0.5rem;">
                        <span style="color: var(--success); font-weight: 500;" id="kpi-avg-win">+$0.00</span>
                        <span style="color: var(--danger); font-weight: 500;" id="kpi-avg-loss">-$0.00</span>
                    </div>
                </div>
            </div>

            <div class="risk-banner" id="detail-risk-banner">
                <div style="font-size: 1.5rem;" id="risk-banner-icon">💡</div>
                <div id="risk-banner-text">诊断意见加载中...</div>
            </div>
        </div>
    </div>
</div>

<script>
    // Embedded parsed JSON data from Python
    const chartLabels = {chart_labels_json};
    const chartData = {chart_data_json};
    const accountSummaries = {account_summaries_json};

    let activeChart = null;
    let selectedAccountId = null;

    // Colors list for multiple account lines
    const colors = [
        '#3b82f6', // blue
        '#10b981', // green
        '#ef4444', // red
        '#f59e0b', // amber
        '#8b5cf6', // purple
        '#06b6d4', // cyan
        '#ec4899', // pink
        '#6366f1'  // indigo
    ];

    document.addEventListener("DOMContentLoaded", () => {{
        initToggles();
        initAccountList();
        renderChart();
        
        // Select first account by default
        if (accountSummaries.length > 0) {{
            selectAccount(accountSummaries[0].Account);
        }}
    }});

    function initToggles() {{
        const container = document.getElementById("chart-toggles");
        container.innerHTML = "";

        // All button
        const allBtn = document.createElement("button");
        allBtn.className = "toggle-btn active";
        allBtn.id = "toggle-all-btn";
        allBtn.innerText = "🔍 显示所有账户";
        allBtn.onclick = () => showAllLines();
        container.appendChild(allBtn);

        accountSummaries.forEach((sum) => {{
            const btn = document.createElement("button");
            btn.className = "toggle-btn";
            btn.id = `toggle-btn-${{sum.Account}}`;
            btn.innerText = sum.Account;
            btn.onclick = () => showSingleLine(sum.Account);
            container.appendChild(btn);
        }});
    }}

    function initAccountList() {{
        const container = document.getElementById("acct-list-container");
        container.innerHTML = "";

        accountSummaries.forEach((sum, idx) => {{
            const div = document.createElement("div");
            div.className = `acct-card ${{sum.Account === selectedAccountId ? 'selected' : ''}}`;
            div.id = `acct-card-${{sum.Account}}`;
            div.onclick = () => selectAccount(sum.Account);

            const isProfit = sum.RealNetProfit >= 0;
            const profitClass = isProfit ? "plus" : "minus";
            const profitSign = isProfit ? "+" : "";

            div.innerHTML = `
                <div class="acct-header">
                    <span class="acct-id">💰 账户 ${{sum.Account}}</span>
                    <span class="acct-profit ${{profitClass}}">${{profitSign}}${{sum.RealNetProfit.toFixed(2)}}</span>
                </div>
                <div class="acct-meta-row">
                    <div>胜率: <span class="meta-val">${{sum.WinRate}}</span></div>
                    <div>笔数: <span class="meta-val">${{sum.TotalTrades}}</span></div>
                    <div>风险: <span class="risk-badge ${{sum.RiskLevel}}" style="font-size: 0.65rem; padding: 0.1rem 0.3rem;">${{sum.RiskLevel}}</span></div>
                </div>
            `;
            container.appendChild(div);
        }});
    }}

    function selectAccount(acctId) {{
        selectedAccountId = acctId;
        
        // Update cards selection UI
        document.querySelectorAll(".acct-card").forEach(c => c.classList.remove("selected"));
        const selectedCard = document.getElementById(`acct-card-${{acctId}}`);
        if (selectedCard) selectedCard.classList.add("selected");

        // Load Details
        const details = accountSummaries.find(s => s.Account === acctId);
        if (details) {{
            document.getElementById("detail-panel").style.display = "block";
            document.getElementById("detail-title").innerText = `🔍 账户 ${{acctId}} 的纯交易数据深度诊断`;
            
            const kpiNetProfit = document.getElementById("kpi-net-profit");
            kpiNetProfit.innerText = details.RealNetProfitStr;
            kpiNetProfit.className = "kpi-val " + (details.RealNetProfit >= 0 ? "plus" : "minus");
            kpiNetProfit.style.color = details.RealNetProfit >= 0 ? "var(--success)" : "var(--danger)";

            document.getElementById("kpi-win-rate").innerText = details.WinRate;
            const wrPercent = parseFloat(details.WinRate.replace('%', ''));
            document.getElementById("kpi-win-rate-fill").style.width = `${{wrPercent}}%`;

            document.getElementById("kpi-trades").innerText = details.TotalTrades;
            document.getElementById("kpi-loss-ratio").innerText = details.Ratio;

            // Colors for ratios
            const ratioVal = parseFloat(details.Ratio.replace('x', ''));
            const lossRatioElement = document.getElementById("kpi-loss-ratio");
            if (ratioVal >= 1.5) {{
                lossRatioElement.style.color = "var(--danger)";
            }} else {{
                lossRatioElement.style.color = "var(--text-primary)";
            }}

            document.getElementById("kpi-cum-win").innerText = details.CumWin;
            document.getElementById("kpi-cum-loss").innerText = details.CumLoss;
            document.getElementById("kpi-avg-win").innerText = details.AvgWin;
            document.getElementById("kpi-avg-loss").innerText = details.AvgLoss;

            // Risk Banner
            const riskBadge = document.getElementById("detail-risk-badge");
            riskBadge.className = `risk-badge ${{details.RiskLevel}}`;
            riskBadge.innerText = details.RiskLevel;

            const banner = document.getElementById("detail-risk-banner");
            banner.className = `risk-banner ${{details.RiskLevel}}`;
            
            const bannerIcon = document.getElementById("risk-banner-icon");
            const bannerText = document.getElementById("risk-banner-text");
            bannerText.innerText = details.RiskDesc;

            if (details.RiskLevel === "DANGER") {{
                bannerIcon.innerText = "🚨";
                banner.style.borderColor = "rgba(239, 68, 68, 0.3)";
            }} else if (details.RiskLevel === "WARNING") {{
                bannerIcon.innerText = "⚠️";
                banner.style.borderColor = "rgba(245, 158, 11, 0.3)";
            }} else {{
                bannerIcon.innerText = "✅";
                banner.style.borderColor = "rgba(16, 185, 129, 0.3)";
            }}
        }}

        // Also highlight in chart
        showSingleLine(acctId, false); // highlight line in chart
    }}

    function renderChart() {{
        const ctx = document.getElementById('pnlLineChart').getContext('2d');
        
        // Prepare datasets
        const datasets = [];
        accountSummaries.forEach((sum, idx) => {{
            const color = colors[idx % colors.length];
            datasets.push({{
                label: `账户 ${{sum.Account}}`,
                data: chartData[sum.Account],
                borderColor: color,
                backgroundColor: color + '10',
                borderWidth: 3,
                tension: 0.15,
                fill: false,
                hidden: false
            }});
        }});

        activeChart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: chartLabels,
                datasets: datasets
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        display: false // We use our own toggles
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        titleColor: '#ffffff',
                        bodyColor: '#e2e8f0',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {{
                            label: function(context) {{
                                let label = context.dataset.label || '';
                                if (label) {{
                                    label += ': ';
                                }}
                                if (context.parsed.y !== null) {{
                                    label += new Intl.NumberFormat('en-US', {{ style: 'currency', currency: 'USD' }}).format(context.parsed.y);
                                }}
                                return label;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.05)',
                        }},
                        ticks: {{
                            color: '#94a3b8',
                            font: {{
                                family: 'Inter'
                            }}
                        }}
                    }},
                    y: {{
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.05)',
                        }},
                        ticks: {{
                            color: '#94a3b8',
                            font: {{
                                family: 'Inter'
                            }},
                            callback: function(value) {{
                                return '$' + value;
                            }}
                        }}
                    }}
                }}
            }}
        }});
    }}

    function showAllLines() {{
        // Reset active toggles
        document.querySelectorAll(".toggle-btn").forEach(btn => btn.classList.remove("active"));
        document.getElementById("toggle-all-btn").classList.add("active");

        activeChart.data.datasets.forEach(dataset => {{
            dataset.hidden = false;
            dataset.borderWidth = 3;
            // Restore opacity
            const hexColor = dataset.borderColor.substring(0, 7);
            dataset.borderColor = hexColor;
        }});
        activeChart.update();
    }}

    function showSingleLine(acctId, selectToggle = true) {{
        if (selectToggle) {{
            document.querySelectorAll(".toggle-btn").forEach(btn => btn.classList.remove("active"));
            const btn = document.getElementById(`toggle-btn-${{acctId}}`);
            if (btn) btn.classList.add("active");
        }}

        activeChart.data.datasets.forEach(dataset => {{
            const isMatch = dataset.label.includes(acctId);
            if (isMatch) {{
                dataset.hidden = false;
                dataset.borderWidth = 4;
                const hexColor = dataset.borderColor.substring(0, 7);
                dataset.borderColor = hexColor; // Full visibility
            }} else {{
                dataset.hidden = false;
                dataset.borderWidth = 1.5;
                const hexColor = dataset.borderColor.substring(0, 7);
                dataset.borderColor = hexColor + '20'; // Fade out other lines
            }}
        }});
        activeChart.update();
    }}
</script>

</body>
</html>
"""

with open(html_output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Successfully generated interactive dashboard at: {html_output_path}")
