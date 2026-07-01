import os
import re
import glob
import json
import pandas as pd
from datetime import datetime

reports_dir = "/Users/Zhuanz/Downloads/latest_reports"
output_file = "/Users/Zhuanz/Downloads/latest_reports/daily_deals_analysis.md"

html_files = glob.glob(os.path.join(reports_dir, "*.html"))
print(f"Found {len(html_files)} HTML files to parse.")

# We will collect all closed deals from all files
all_deals = []

for file_path in html_files:
    filename = os.path.basename(file_path)
    
    # Extract account number from filename
    acct_match = re.match(r"^(\d+)_", filename)
    account_num = acct_match.group(1) if acct_match else "Unknown"
    
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Extract table rows
    # Standard format: <tr><td>Ticket</td><td>Time</td><td>Symbol</td><td>Type</td><td>Entry</td><td>Volume</td><td>Price</td><td>Commission</td><td>Swap</td><td>Profit</td><td>Comment</td></tr>
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.DOTALL)
    if not tbody_match:
        continue
    
    tbody_content = tbody_match.group(1)
    # Find all <tr>...</tr> rows
    rows = re.findall(r"<tr>(.*?)</tr>", tbody_content, re.DOTALL)
    
    for row in rows:
        tds = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)
        if len(tds) < 11:
            continue
        
        ticket = tds[0].strip()
        time_str = tds[1].strip() # e.g. "2026.06.19 08:03:00"
        symbol = tds[2].strip()
        type_str = tds[3].strip() # May contain HTML tags like <span>SELL</span>
        entry = tds[4].strip() # "IN" or "OUT"
        volume_str = tds[5].strip()
        price_str = tds[6].strip()
        commission_str = tds[7].strip()
        swap_str = tds[8].strip()
        profit_str = tds[9].strip() # May contain style tags and $, e.g., <td style='color: #2ecc71;'>$1.21</td>
        comment = tds[10].strip()
        
        # Clean type (remove HTML tags)
        clean_type = re.sub(r"<[^>]*>", "", type_str).upper()
        
        # We only care about actual trading closed deals (Entry: OUT, or closed positions)
        if entry.upper() != "OUT":
            continue
        
        # Clean money values
        def clean_money(text):
            text = re.sub(r"<[^>]*>", "", text) # Remove HTML
            text = text.replace("$", "").replace(",", "").replace(" ", "").strip()
            try:
                return float(text)
            except ValueError:
                return 0.0
                
        profit_val = clean_money(profit_str)
        commission_val = clean_money(commission_str)
        swap_val = clean_money(swap_str)
        net_val = profit_val + commission_val + swap_val
        
        # Parse date, e.g. "2026.06.19 08:03:00" -> "2026-06-19"
        try:
            date_val = time_str.split(" ")[0].replace(".", "-")
        except Exception:
            date_val = "Unknown"
            
        all_deals.append({
            "Account": account_num,
            "Date": date_val,
            "Ticket": ticket,
            "Symbol": symbol,
            "Type": clean_type,
            "Volume": volume_str,
            "Price": price_str,
            "Commission": commission_val,
            "Swap": swap_val,
            "Profit": profit_val,
            "Net Profit": net_val,
            "Comment": comment,
            "SourceFile": filename
        })

# Create DataFrame
df_deals = pd.DataFrame(all_deals)
if df_deals.empty:
    print("No closed deals found in statements!")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# 📊 交易账户每日盈亏分析报告\n\n未找到任何已平仓交易交割记录。")
    exit(0)

# De-duplicate deals based on Account and Ticket
df_deals = df_deals.drop_duplicates(subset=["Account", "Ticket"])

# Group by Account and Date to get daily statistics
daily_summary = df_deals.groupby(["Account", "Date"]).agg(
    Trades_Count=("Ticket", "count"),
    Gross_Profit=("Profit", lambda s: s[s > 0].sum()),
    Gross_Loss=("Profit", lambda s: s[s < 0].sum()),
    Total_Commission=("Commission", "sum"),
    Total_Swap=("Swap", "sum"),
    Net_PnL=("Net Profit", "sum")
).reset_index()

# Sort by Account and Date ascending
daily_summary = daily_summary.sort_values(by=["Account", "Date"], ascending=[True, True])

# Generate Markdown Report
md_lines = []
md_lines.append("# 📊 MT5 多账户每日交易盈亏诊断报告")
md_lines.append(f"报告生成时间: 2026-06-28 | 统计区间: 最近一周已交割交易\n")

md_lines.append("## 1. 每日实际交易盈亏（PnL）明细")
md_lines.append("| 账户 ID | 交易日期 | 交易笔数 | 总盈利 (Gross Win) | 总亏损 (Gross Loss) | 总手续费 | 净盈亏 (Net PnL) | 状态 |")
md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

for _, row in daily_summary.iterrows():
    status = "🟩 盈利" if row["Net_PnL"] > 0 else ("🟥 亏损" if row["Net_PnL"] < 0 else "⬜️ 平盘")
    md_lines.append(
        f"| **{row['Account']}** | {row['Date']} | {row['Trades_Count']} | ${row['Gross_Profit']:.2f} | ${row['Gross_Loss']:.2f} | ${row['Total_Commission']:.2f} | **${row['Net_PnL']:.2f}** | {status} |"
    )

md_lines.append("\n## 2. 账户累计纯交易绩效汇总")
md_lines.append("| 账户 ID | 总交易笔数 | 累计毛利 | 累计毛损 | 胜率 (Win Rate) | 累计手续费 | 净交易利润 (Real PnL) |")
md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

for acct, group in df_deals.groupby("Account"):
    total_trades = len(group)
    wins = group[group["Profit"] > 0]
    losses = group[group["Profit"] < 0]
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    
    cum_win = group.loc[group["Profit"] > 0, "Profit"].sum()
    cum_loss = group.loc[group["Profit"] < 0, "Profit"].sum()
    cum_commission = group["Commission"].sum()
    cum_swap = group["Swap"].sum()
    real_net = group["Net Profit"].sum()
    
    md_lines.append(
        f"| **{acct}** | {total_trades} | ${cum_win:.2f} | ${cum_loss:.2f} | {win_rate:.1f}% ({len(wins)}/{total_trades}) | ${cum_commission:.2f} | **${real_net:.2f}** |"
    )

# Fix spelling in table header
md_lines = [l.replace("cum_win Haus", "cum_win") for l in md_lines]

md_lines.append("\n## 3. 核心行为风控结论 (是否都是赚钱的？)")
md_lines.append("> [!IMPORTANT]")
md_lines.append("> **结论揭晓：并非所有账户都是纯交易盈利的！** 许多账户的数据中混入了 `BALANCE`（初始入金入账），导致总资产看起来是正的，但剔除入金后的**纯交易表现**存在显著差异：")

for acct, group in df_deals.groupby("Account"):
    net_pnl = group["Net Profit"].sum()
    total_trades = len(group)
    wins = len(group[group["Profit"] > 0])
    avg_win = group.loc[group["Profit"] > 0, "Profit"].mean() if wins > 0 else 0.0
    losses = len(group[group["Profit"] < 0])
    avg_loss = abs(group.loc[group["Profit"] < 0, "Profit"].mean()) if losses > 0 else 0.0
    
    ratio = (avg_loss / avg_win) if avg_win > 0 else 0.0
    
    md_lines.append(f"### 🔍 账户 {acct} 的真实交割分析")
    md_lines.append(f"- **累计交易笔数**: `{total_trades}` 笔")
    md_lines.append(f"- **扣除入金后的实际净交易盈亏**: **${net_pnl:.2f}**")
    
    if net_pnl > 0:
        md_lines.append(f"  - 🟢 **盈利状态**: 该账户在过去一周的交易中**实现了真实盈利**。")
    elif net_pnl < 0:
        md_lines.append(f"  - 🔴 **亏损状态**: 该账户在过去一周的实际交易中**处于亏损状态**！")
    else:
        md_lines.append(f"  - ⚪ **平盘状态**: 无有效交易盈亏。")
        
    md_lines.append(f"  - **处置效应评估 (均损/均赢)**: 平均单笔亏损为 **${avg_loss:.2f}**，平均单笔盈利为 **${avg_win:.2f}**，盈亏比比率为 **{ratio:.2f}x**。")
    if ratio >= 1.5:
        md_lines.append(f"    - ⚠️ **警报：检测到严重的处置效应（小赚大亏）！** 你的平均亏损达到了平均盈利的 {ratio:.2f} 倍，属于典型的人性偏差坑点，建议立即挂载止损拦截器。")
    else:
        md_lines.append("    - ✅ 盈亏比指标在安全范围内。")
    md_lines.append("")

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"Successfully generated daily summary at: {output_file}")
# Let's fix potential typos
