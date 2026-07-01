import os

target_file = "/Users/Zhuanz/Downloads/DeepSeek_EA_v4.50.mq5"

with open(target_file, "rb") as f:
    content = f.read().decode('utf-8', errors='ignore')

content_norm = content.replace('\r\n', '\n')

# Replace text
content_norm = content_norm.replace('last_ai_result_1 += "  (\\u2705 成功做多 "', 'last_ai_result_1 += "  (\\u2705 已提交做多 "')
content_norm = content_norm.replace('last_ai_result_1 += "  (✅ 成功做多 "', 'last_ai_result_1 += "  (✅ 已提交做多 "')

content_norm = content_norm.replace('last_ai_result_1 += "  (\\u2705 成功做空 "', 'last_ai_result_1 += "  (\\u2705 已提交做空 "')
content_norm = content_norm.replace('last_ai_result_1 += "  (✅ 成功做空 "', 'last_ai_result_1 += "  (✅ 已提交做空 "')

content_norm = content_norm.replace('last_ai_result_1 += "  (\\u2705 成功平仓 "', 'last_ai_result_1 += "  (\\u2705 已提交平仓 "')
content_norm = content_norm.replace('last_ai_result_1 += "  (✅ 成功平仓 "', 'last_ai_result_1 += "  (✅ 已提交平仓 "')

# Write back
content_final = content_norm.replace('\n', '\r\n')
with open(target_file, "wb") as f:
    f.write(content_final.encode('utf-8'))
print("Finished patching UI feedback texts!")
