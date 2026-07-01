import os

target_file = "/Users/Zhuanz/Downloads/DeepSeek_EA_v4.50.mq5"

with open(target_file, "rb") as f:
    content = f.read().decode('utf-8', errors='ignore')

# Normalize to \n
content_norm = content.replace('\r\n', '\n')

# 1. Ensure winhttp is imported
winhttp_imports = """#import "winhttp.dll"
long WinHttpOpen(string pwszUserAgent, uint dwAccessType, string pwszProxyName, string pwszProxyBypass, uint dwFlags);
long WinHttpConnect(long hSession, string pswzServerName, int nServerPort, uint dwReserved);
long WinHttpOpenRequest(long hConnect, string pwszVerb, string pwszObjectName, string pwszVersion, string pwszReferrer, long ppwszAcceptTypes, uint dwFlags);
int  WinHttpSendRequest(long hRequest, string pwszHeaders, uint dwHeadersLength, char &lpOptional[], uint dwOptionalLength, uint dwTotalLength, long dwContext);
int  WinHttpReceiveResponse(long hRequest, long lpReserved);
int  WinHttpQueryDataAvailable(long hRequest, uint &lpdwNumberOfBytesAvailable);
int  WinHttpReadData(long hRequest, char &lpBuffer[], uint dwNumberOfBytesToRead, uint &lpdwNumberOfBytesRead);
int  WinHttpCloseHandle(long hInternet);
int  WinHttpSetOption(long hInternet, uint dwOption, int &lpBuffer, uint dwBufferLength);
int  WinHttpSetTimeouts(long hInternet, int nResolveTimeout, int nConnectTimeout, int nSendTimeout, int nReceiveTimeout);
#import"""

if 'winhttp.dll' not in content_norm:
    content_norm = content_norm.replace('#import\n\n#import "shell32.dll"', '#import\n\n' + winhttp_imports.replace('\r\n', '\n') + '\n\n#import "shell32.dll"')

# 2. Dynamic replacement
start_marker = 'long hOpen = InternetOpenW("MQL5 DeepSeek EA"'
end_marker = 'if(InpDebugMode) WriteLog("RAW API RESPONSE: \\n" + response_str);'

start_idx = content_norm.find(start_marker)
end_idx = content_norm.find(end_marker)

if start_idx != -1 and end_idx != -1:
    replacement_send_block = """long hOpen = WinHttpOpen("MQL5 DeepSeek EA", 0, NULL, NULL, 0);
    if(hOpen == 0) { last_ai_result_1 = "网络初始化失败"; return; }
    
    // 显式配置超时时间为 120 秒
    WinHttpSetTimeouts(hOpen, 120000, 120000, 120000, 120000);
    
    // 强制开启 TLS 1.2 & TLS 1.3 支持
    int protocols = 0x00002800; // WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2 | WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_3
    WinHttpSetOption(hOpen, 9, protocols, 4); // 9 = WINHTTP_OPTION_SECURE_PROTOCOLS
    
    long hConnect = WinHttpConnect(hOpen, host, 443, 0);
    if(hConnect == 0) { last_ai_result_1 = "服务器连接失败"; WinHttpCloseHandle(hOpen); return; }
    
    long hRequest = WinHttpOpenRequest(hConnect, "POST", path, NULL, NULL, 0, 0x00800000); // 0x00800000 = WINHTTP_FLAG_SECURE
    if(hRequest == 0) { last_ai_result_1 = "构建请求失败"; WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hOpen); return; }
     
    // 忽略 SSL 证书验证错误，防止 VPS 的 CA 证书链缺失导致 SSL 握手超时失败
    int sec_flags = 0x00003300; // Ignore CA, Date, CN errors
    WinHttpSetOption(hRequest, 31, sec_flags, 4); // 31 = WINHTTP_OPTION_SECURITY_FLAGS
    
    string headers = "Authorization: Bearer " + g_api_key + "\\r\\nContent-Type: application/json\\r\\n";
    int res = WinHttpSendRequest(hRequest, headers, StringLen(headers), post_data, ArraySize(post_data), ArraySize(post_data), 0);
    
    if(res != 0)
      {
       res = WinHttpReceiveResponse(hRequest, 0);
      }
      
    if(res != 0)
      {
       char buffer[];
       ArrayResize(buffer, 1024);
       uint read = 0;
       string response_str = "";
       uint available = 0;
       
       while(WinHttpQueryDataAvailable(hRequest, available) && available > 0)
         {
          uint bytes_to_read = available;
          if(bytes_to_read > 1024) bytes_to_read = 1024;
          
          if(WinHttpReadData(hRequest, buffer, bytes_to_read, read) && read > 0)
            {
             response_str += CharArrayToString(buffer, 0, (int)read, CP_UTF8);
            }
          else
            {
             break;
            }
         }
       
       """
    
    content_norm = content_norm[:start_idx] + replacement_send_block + content_norm[end_idx:]
    print("Main request sending block successfully patched index-wise!")
else:
    print("ERROR: Start or end markers not found!")

# 3. Double check closing block replacement
target_close_block = """   InternetCloseHandle(hRequest);
   InternetCloseHandle(hConnect);
   InternetCloseHandle(hOpen);"""

replacement_close_block = """   WinHttpCloseHandle(hRequest);
   WinHttpCloseHandle(hConnect);
   WinHttpCloseHandle(hOpen);"""

# Let's search for the end of the file or function where InternetCloseHandle are called
close_idx = content_norm.rfind(target_close_block)
if close_idx != -1:
    content_norm = content_norm[:close_idx] + replacement_close_block + content_norm[close_idx + len(target_close_block):]
    print("Handles closing block successfully patched rfind-wise!")
else:
    # If already patched in the previous run
    if 'WinHttpCloseHandle(hRequest)' in content_norm:
        print("Handles closing block already patched!")
    else:
        print("WARNING: Close block not found!")

# Write back
content_final = content_norm.replace('\n', '\r\n')
with open(target_file, "wb") as f:
    f.write(content_final.encode('utf-8'))
print("Finished index-based patching!")
