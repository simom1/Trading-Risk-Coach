import os
import re
import glob
import json
import pandas as pd

reports_dir = "/Users/Zhuanz/Downloads/latest_reports"
output_file = "/Users/Zhuanz/Downloads/latest_reports/deals_analysis_summary.md"

html_files = glob.glob(os.path.join(reports_dir, "*.html"))
print(f"Found {len(html_files)} HTML statement files in {reports_dir}")

summary_data = []

for file_path in html_files:
    filename = os.path.basename(file_path)
    
    # Extract date from filename, e.g., 209131474_20260628_060002.html -> 2026-06-28
    date_match = re.search(r"_(\d{8})_", filename)
    file_date = date_match.group(1) if date_match else "Unknown"
    # Format date to YYYY-MM-DD
    if len(file_date) == 8:
        file_date = f"{file_date[0:4]}-{file_date[4:6]}-{file_date[6:8]}"
    
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Parse metrics using regex based on HTML structure
    account = re.search(r"<h3>交易账户.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    company = re.search(r"<h3>经纪商.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    server = re.search(r"<h3>服务器.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    equity = re.search(r"<h3>净值.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    profit = re.search(r"<h3>交易总盈亏.*?</h3><p.*?>(.*?)</p>", html, re.DOTALL)
    commission = re.search(r"<h3>总手续费.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    swap = re.search(r"<h3>总库存利息.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    net_profit = re.search(r"<h3>净利润.*?</h3><p.*?>(.*?)</p>", html, re.DOTALL)
    win_rate = re.search(r"<h3>交易胜率.*?</h3><p>(.*?)</p>", html, re.DOTALL)
    
    # Safe extracts
    account_val = account.group(1).strip() if account else "Unknown"
    company_val = company.group(1).strip() if company else "Unknown"
    server_val = server.group(1).strip() if server else "Unknown"
    
    # Clean money values
    def clean_val(match):
        if not match: return 0.0
        val = match.group(1).replace("$", "").replace(",", "").strip()
        try:
            return float(val)
        except ValueError:
            return 0.0

    equity_val = clean_val(equity)
    profit_val = clean_val(profit)
    commission_val = clean_val(commission)
    swap_val = clean_val(swap)
    net_profit_val = clean_val(net_profit)
    
    win_rate_str = win_rate.group(1).strip() if win_rate else "0.0% (0/0)"
    
    summary_data.append({
        "Account": account_val,
        "Date": file_date,
        "Broker": company_val,
        "Server": server_val,
        "Equity": equity_val,
        "Profit": profit_val,
        "Commission": commission_val,
        "Swap": swap_val,
        "Net Profit": net_profit_val,
        "Win Rate": win_rate_str,
        "Filename": filename
    })

# Convert to DataFrame and sort by Account then Date descending
df = pd.DataFrame(summary_data)
df = df.sort_values(by=["Account", "Date"], ascending=[True, False])

# Write Markdown report
md_lines = []
md_lines.append("# 📊 MT5 账户交易数据分析汇总报告")
md_lines.append(f"报告生成时间: 2026-06-28 | 样本文件数量: {len(df)} 份\n")

md_lines.append("## 1. 全账户交易汇总表")
md_lines.append("| 账户 ID | 报告日期 | 经纪商 | 净值 (Equity) | 交易盈亏 | 手续费 | 净利润 (Net Profit) | 胜率 (Win Rate) |")
md_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

for _, row in df.iterrows():
    md_lines.append(
        f"| **{row['Account']}** | {row['Date']} | {row['Broker']} | ${row['Equity']:.2f} | ${row['Profit']:.2f} | ${row['Commission']:.2f} | **${row['Net Profit']:.2f}** | {row['Win Rate']} |"
    )

md_lines.append("\n## 2. 各账户最新数据诊断（行为风控分析）")

# Group by account to analyze changes
for acct, group in df.groupby("Account"):
    md_lines.append(f"### 🛡️ 账户 {acct} 诊断意见")
    sorted_group = group.sort_values(by="Date", ascending=True) # Oldest to newest
    latest = sorted_group.iloc[-1]
    
    md_lines.append(f"- **基本信息**: 运行于 经纪商 `{latest['Broker']}` ({latest['Server']})")
    md_lines.append(f"- **最新状态 ({latest['Date']})**: 账户净值为 **${latest['Equity']:.2f}**，总净盈亏为 **${latest['Net Profit']:.2f}**，胜率为 `{latest['Win Rate']}`。")
    
    if len(sorted_group) > 1:
        oldest = sorted_group.iloc[0]
        diff_profit = latest['Net Profit'] - oldest['Net Profit']
        md_lines.append(f"- **周期变化 ({oldest['Date']} ➡️ {latest['Date']})**:")
        if diff_profit > 0:
            md_lines.append(f"  - 🟩 净利润增长了 **${diff_profit:.2f}**。表现优异。")
        elif diff_profit < 0:
            md_lines.append(f"  - 🟥 净利润出现回撤，下滑了 **${abs(diff_profit):.2f}**。")
        else:
            md_lines.append("  - 🟦 净利润持平，无新交割单上传。")
    else:
        md_lines.append("- **周期变化**: 该账户最近仅有 1 期交割记录，暂无历史周期对比数据。")
        
    md_lines.append("")

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

print(f"Successfully generated summary report at: {output_file}")
