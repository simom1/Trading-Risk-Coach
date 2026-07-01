import re

md_path = "/Users/Zhuanz/Downloads/latest_reports/daily_deals_analysis.md"
html_output_path = "/Users/Zhuanz/deals_analysis_preview.html"

with open(md_path, "r", encoding="utf-8") as f:
    md_content = f.read()

html_body = md_content
# Escape headers
html_body = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", html_body, flags=re.MULTILINE)
html_body = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", html_body, flags=re.MULTILINE)
html_body = re.sub(r"^### (.*?)$", r"<h3>\1</h3>", html_body, flags=re.MULTILINE)
# Replace bold
html_body = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html_body)
# Replace bullet points
html_body = re.sub(r"^\-\s+(.*?)$", r"<li>\1</li>", html_body, flags=re.MULTILINE)
html_body = re.sub(r"(<li>.*?</li>\n?)+", lambda m: f"<ul>{m.group(0)}</ul>", html_body)
# Replace lists inside list items
html_body = re.sub(r"^\s+\-\s+(.*?)$", r"<li>\1</li>", html_body, flags=re.MULTILINE)

# Parse table
def replace_table(match):
    lines = match.group(0).strip().split("\n")
    table_html = "<table><thead>"
    headers = [h.strip() for h in lines[0].split("|")[1:-1]]
    table_html += "<tr>" + "".join([f"<th>{h}</th>" for h in headers]) + "</tr></thead><tbody>"
    
    for row in lines[2:]:
        cols = [c.strip() for c in row.split("|")[1:-1]]
        table_html += "<tr>" + "".join([f"<td>{c}</td>" for c in cols]) + "</tr>"
    table_html += "</tbody></table>"
    return table_html

html_body = re.sub(r"(\|.*\|.*?)\n(\|[\s\-:|]*\|.*?)\n((\|.*\|.*?)\n?)+", replace_table, html_body)

html_full_page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MT5 Multi-Account Trading Performance Summary</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --border-color: rgba(255, 255, 255, 0.08);
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
            line-height: 1.6;
            background-image: 
                radial-gradient(circle at 10% 10%, rgba(59, 130, 246, 0.06) 0%, transparent 40%),
                radial-gradient(circle at 90% 90%, rgba(139, 92, 246, 0.06) 0%, transparent 40%);
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: rgba(17, 24, 39, 0.7);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 3rem;
            backdrop-filter: blur(16px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        }}

        p.subtitle {{
            color: var(--text-secondary);
            margin-bottom: 2rem;
            font-size: 1.05rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
        }}

        h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: #93c5fd;
            border-left: 4px solid var(--accent-blue);
            padding-left: 0.75rem;
        }}

        h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            margin-top: 2rem;
            margin-bottom: 0.75rem;
            color: #c084fc;
        }}

        p {{
            margin-bottom: 1.25rem;
            color: #d1d5db;
        }}

        ul {{
            margin-left: 1.5rem;
            margin-bottom: 1.25rem;
            color: #d1d5db;
        }}

        li {{
            margin-bottom: 0.5rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 2.5rem;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
        }}

        th, td {{
            padding: 1rem 1.25rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background: rgba(30, 41, 59, 0.6);
            color: #ffffff;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
        }}

        tr:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}

        td strong {{
            color: #10b981;
        }}

        hr {{
            border: 0;
            height: 1px;
            background: var(--border-color);
            margin: 2.5rem 0;
        }}
    </style>
</head>
<body>

<div class="container">
    <h1>MT5 账户交易数据分析汇总</h1>
    <p class="subtitle">Multi-Account Performance Report & Behavioral Risk Analysis</p>
    
    <div class="content">
        {html_body}
    </div>
</div>

</body>
</html>
"""

with open(html_output_path, "w", encoding="utf-8") as f:
    f.write(html_full_page)

print(f"Successfully generated analysis HTML preview at: {html_output_path}")
