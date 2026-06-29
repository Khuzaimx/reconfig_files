import paramiko
import sys
import socket
import time

def check_dns_propagation(domain, expected_ip, max_retries=15, delay=5):
    print(f"Checking DNS propagation for {domain}...")
    for i in range(max_retries):
        try:
            ip = socket.gethostbyname(domain)
            print(f"Attempt {i+1}: Domain {domain} resolves to {ip}")
            if ip == expected_ip:
                print("DNS has propagated successfully!")
                return True
        except socket.gaierror as e:
            print(f"Attempt {i+1}: Failed to resolve {domain}: {e}")
        time.sleep(delay)
    return False

def run_ssh_command_stream(ssh, cmd):
    print(f"\nExecuting command: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Stream stdout
    while True:
        line = stdout.readline()
        if not line:
            break
        safe_line = line.encode('ascii', errors='replace').decode('ascii')
        print(safe_line, end="")
        sys.stdout.flush()

    # Stream stderr
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if err:
        safe_err = err.encode('ascii', errors='replace').decode('ascii')
        print("\nSTDERR:")
        print(safe_err)
        
    exit_status = stdout.channel.recv_exit_status()
    print(f"Exit Code: {exit_status}")
    return exit_status == 0

def main():
    expected_ip = "18 "
    domain = "psycheversity.com"
    
    # Check DNS locally
    dns_ok = check_dns_propagation(domain, expected_ip, max_retries=10, delay=3)
    if not dns_ok:
        print("Warning: DNS has not fully propagated yet. Continuing to request SSL anyway, but certbot might fail if the DNS resolver used by Let's Encrypt isn't updated yet.")

    hostname = "1 "
    username = " "
    password = "K "
    remote_base = " "

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to Hostinger VPS {hostname}...")
        ssh.connect(hostname, username=username, password=password, timeout=15)
        print("Connected successfully!")

        print("\n--- Step 1: Temporarily stop Nginx container to free port 80 ---")
        run_ssh_command_stream(ssh, "docker stop psych_nginx || true")

        print("\n--- Step 2: Request Let's Encrypt SSL Certificates via Standalone Certbot ---")
        certbot_cmd = f"certbot certonly --standalone -d {domain} -d www.{domain} --agree-tos -m admin@{domain} --no-eff-email --non-interactive"
        run_ssh_command_stream(ssh, certbot_cmd)

        print("\n--- Step 3: Verify Certificates obtained ---")
        run_ssh_command_stream(ssh, f"ls -la /etc/letsencrypt/live/{domain}/")

        print("\n--- Step 4: Upload updated config files from local workspace ---")
        sftp = ssh.open_sftp()
        print("Uploading updated docker-compose.yml...")
        sftp.put("docker-compose.yml", f"{remote_base}/docker-compose.yml")
        print("Uploading updated nginx/nginx.conf...")
        sftp.put("nginx/nginx.conf", f"{remote_base}/nginx/nginx.conf")
        sftp.close()

        print("\n--- Step 5: Start Nginx with SSL enabled ---")
        # Build and start Nginx container
        run_ssh_command_stream(ssh, f"cd {remote_base} && docker compose up -d --build nginx")

        print("\n--- Step 6: Verify Nginx is active on port 80 and 443 ---")
        run_ssh_command_stream(ssh, "docker ps | grep psych_nginx")

    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == '__main__':
    main()
