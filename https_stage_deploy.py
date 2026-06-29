import paramiko
import sys
import time

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

def run_ssh_command_silent(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return exit_status == 0, out, err

def main():
    hostname = "1 "
    username = " "
    password = "K "
    remote_base = "/root/psych_experiment_platform"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to Hostinger VPS {hostname}...")
        ssh.connect(hostname, username=username, password=password, timeout=15)
        print("Connected successfully!")

        print("\n--- Step 1: Extract Application Source ---")
        # Extract tarball
        run_ssh_command_stream(ssh, "tar -xzf /root/app_source.tar.gz -C /root/")

        print("\n--- Step 2: Configure Environment (.env) for Port 80 and new Host IP ---")
        # Read old .env
        ok, env_content, err = run_ssh_command_silent(ssh, f"cat {remote_base}/.env")
        if not ok:
            print("Failed to read .env file on new server!")
            sys.exit(1)

        # Update environment values
        lines = env_content.split('\n')
        new_lines = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("NGINX_PORT="):
                new_lines.append("NGINX_PORT=80")
            elif line_str.startswith("CSRF_TRUSTED_ORIGINS="):
                new_lines.append("CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,http://187.127.146.182,https://psycheversity.com,http://psycheversity.com")
            elif line_str.startswith("CORS_ALLOWED_ORIGINS="):
                new_lines.append("CORS_ALLOWED_ORIGINS=http://localhost,http://127.0.0.1,http://187.127.146.182,https://psycheversity.com,http://psycheversity.com")
            else:
                new_lines.append(line)

        new_env_content = '\n'.join(new_lines)
        
        # Write back .env
        print("Writing updated .env file...")
        sftp = ssh.open_sftp()
        with sftp.file(f"{remote_base}/.env", 'w') as f:
            f.write(new_env_content)
        sftp.close()

        print("\n--- Step 3: Start database and cache services ---")
        # Run docker compose up for db and redis
        run_ssh_command_stream(ssh, f"cd {remote_base} && docker compose up -d db redis")

        print("\n--- Step 4: Wait for database container to be healthy ---")
        # Check pg_isready
        max_attempts = 15
        db_ready = False
        for attempt in range(max_attempts):
            ok, out, err = run_ssh_command_silent(ssh, "docker exec -t psych_db pg_isready -U psych_user -d psych_db")
            if "accepting connections" in out:
                db_ready = True
                print("Database is healthy and accepting connections!")
                break
            else:
                print(f"Database not ready yet (attempt {attempt+1}/{max_attempts}). Waiting 3 seconds...")
                time.sleep(3)

        if not db_ready:
            print("Database container failed to initialize within time limit!")
            sys.exit(1)

        print("\n--- Step 5: Restore PostgreSQL database dump ---")
        # Restore dump into the postgres container
        run_ssh_command_stream(ssh, f"docker exec -i psych_db psql -U psych_user -d psych_db < /root/db_dump.sql")

        print("\n--- Step 6: Launch all remaining services ---")
        # Start all services
        run_ssh_command_stream(ssh, f"cd {remote_base} && docker compose up -d --build")

        print("\n--- Step 7: Run migrations ---")
        # Verify migrations
        run_ssh_command_stream(ssh, f"cd {remote_base} && docker compose exec -T backend python manage.py migrate")

    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == '__main__':
    main()
