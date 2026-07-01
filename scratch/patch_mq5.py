import os

target_file = "/Users/Zhuanz/Downloads/DeepSeek_EA_v4.50.mq5"

with open(target_file, "rb") as f:
    content = f.read()

# Target bytes to find
target_bytes = b"InternetSetOptionW(hRequest, 31, sec_flags, 4); // 31 = INTERNET_OPTION_SECURITY_FLAGS"

# Replacement bytes
replacement_bytes = (
    b"InternetSetOptionW(hRequest, 31, sec_flags, 4); // 31 = INTERNET_OPTION_SECURITY_FLAGS\r\n"
    b"    \r\n"
    b"    // \xe6\x9c\xac\xe5\x9c\xb0\xe6\x98\xb7\xe5\xbc\x8f\xe9\x85\x8d\xe7\xbd\xae\xe8\xb6\x85\xe6\x97\xb6\xe6\x97\xb6\xe9\x97\xb4\xe5\x88\xb0 hRequest\r\n"
    b"    int req_timeout = 120000;\r\n"
    b"    InternetSetOptionW(hRequest, 2, req_timeout, 4);\r\n"
    b"    InternetSetOptionW(hRequest, 5, req_timeout, 4);\r\n"
    b"    InternetSetOptionW(hRequest, 6, req_timeout, 4);"
)

if target_bytes in content:
    new_content = content.replace(target_bytes, replacement_bytes, 1)
    with open(target_file, "wb") as f:
        f.write(new_content)
    print("Successfully patched MQ5 file with explicit timeouts!")
else:
    print("Target bytes not found in MQ5 file!")
