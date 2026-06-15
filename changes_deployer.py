import paramiko
import os
import sys
import zipfile

def create_zip_archive(source_dir, output_path):
    """Creates a zip archive of the workspace, excluding local configs, git, and build outputs."""
    print("=== Packaging local codebase ===")
    
    exclude_dirs = {
        '.git', 
        'venv', 
        '.venv', 
        'node_modules', 
        '__pycache__', 
        '.pytest_cache', 
        'dist', 
        'build', 
        'deploy_configs',
        'scratch',
    }
    exclude_files = {
        "project_deployment.zip",
        '.env',
        'db.sqlite3',
        'celerybeat-schedule',
        'django.log',
    }

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files or file.endswith('.log') or file.endswith('.docx') or file.endswith('.jpeg') or file.endswith('.zip') or file.endswith('.png'):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, rel_path)
                
    print(f"Codebase packaged successfully: {output_path} ({os.path.getsize(output_path) / (1024*1024):.2f} MB)")

def run_ssh_command_stream(ssh, cmd):
    """Helper to execute an SSH command and stream stdout/stderr in real-time."""
    print(f"\nExecuting: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    
    # Stream stdout
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end="")
        sys.stdout.flush()

    # Stream stderr
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if err:
        print("\nSTDERR:")
        print(err)
        
    exit_status = stdout.channel.recv_exit_status()
    print(f"\nCommand exited with status code: {exit_status}")
    return exit_status == 0

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    local_base = r"c:\Users\elmir\Desktop\experiment\psych_experiment_platform"
    remote_base = "/home/sj/psych_experiment_platform"
    archive_name = "project_deployment.zip"
    archive_path = os.path.join(local_base, archive_name)

    # 1. Package local codebase
    create_zip_archive(local_base, archive_path)

    hostname = "50...."
    username = "sj..."
    password = "99..."

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"\nConnecting to remote VM {hostname}...")
        ssh.connect(hostname, username=username, password=password, timeout=15)
        sftp = ssh.open_sftp()
        print("Connected successfully!")
    except Exception as e:
        print(f"Connection failed: {e}")
        if os.path.exists(archive_path):
            os.remove(archive_path)
        sys.exit(1)

    try:
        # 2. Upload zip archive with callback
        remote_zip_path = f"{remote_base}/{archive_name}"
        print(f"Uploading {archive_name} -> {remote_zip_path}...")
        
        last_percent = [-1]
        def progress_callback(transferred, total):
            percent = int((transferred / total) * 100)
            if percent % 10 == 0 and percent != last_percent[0]:
                print(f"Uploaded {transferred / (1024*1024):.2f} / {total / (1024*1024):.2f} MB ({percent}%)")
                last_percent[0] = percent
                sys.stdout.flush()

        sftp.put(archive_path, remote_zip_path, callback=progress_callback)
        sftp.close()
        print("Upload completed successfully!")

        # 3. Unpack zip archive on remote host using Python's built-in zipfile module
        print("\nUnpacking codebase on remote server...")
        unpack_cmd = f"cd {remote_base} && python3 -c \"import zipfile; zipfile.ZipFile('{archive_name}').extractall('.')\" && rm {archive_name}"
        run_ssh_command_stream(ssh, unpack_cmd)

        # 4. Rebuild and restart all containers
        print("\nRebuilding and restarting all Docker containers...")
        cmd_build = f"cd {remote_base} && docker compose down && docker compose up -d --build"
        run_ssh_command_stream(ssh, cmd_build)

        # 5. Run database migrations (if any new migrations exist)
        print("\nRunning database migrations on remote VM...")
        cmd_migrate = f"cd {remote_base} && docker compose exec -T backend python manage.py migrate"
        run_ssh_command_stream(ssh, cmd_migrate)

        # 6. Run backend tests to verify stability
        print("\nRunning backend tests on remote VM...")
        cmd_test = f"cd {remote_base} && docker compose exec -T backend pytest"
        run_ssh_command_stream(ssh, cmd_test)

    finally:
        ssh.close()
        # Clean up local zip
        if os.path.exists(archive_path):
            os.remove(archive_path)

    print("\nDeployment execution completed successfully!")

if __name__ == "__main__":
    main()
