import paramiko
import os

key_path = "/Users/Zhuanz/.ssh/tencent_124"
host = "124.221.56.81"
user = "Administrator"

print(f"Loading private key from: {key_path}")
private_key = paramiko.Ed25519Key(filename=key_path)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print(f"Connecting to {user}@{host} via Paramiko...")
try:
    ssh.connect(hostname=host, port=22, username=user, pkey=private_key, timeout=15)
    print("Connection Successful!")
    stdin, stdout, stderr = ssh.exec_command("whoami")
    print(f"Remote User: {stdout.read().decode().strip()}")
    ssh.close()
except Exception as e:
    print(f"Connection Failed: {e}")
