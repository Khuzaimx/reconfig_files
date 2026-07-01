import paramiko
import sys

def main():
    hostname = " 
    username = "s 
    password = " 
    remote_base = "/hom 

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname, username=username, password=password, timeout=15)
        print("Connected successfully!")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        python_inspect_code = """
import django
import os
import glob
import csv

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

export_dir = "/app/media/exports/baselines/*/*/*/*.csv"
csv_files = glob.glob(export_dir)
print(f"Found {len(csv_files)} CSV files in exports directory.")

for file_path in sorted(csv_files):
    print(f"\\nInspecting: {os.path.basename(file_path)}")
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            print("  Empty file!")
            continue
        print(f"  Headers ({len(headers)}): {headers}")
        
        rows = list(reader)
        print(f"  Total Rows: {len(rows)}")
        
        # Check if there are columns where all values are empty
        column_values_count = [0] * len(headers)
        column_empty_count = [0] * len(headers)
        
        for row in rows:
            for idx, val in enumerate(row):
                if idx < len(headers):
                    if val.strip() == "" or val.strip() == "None" or val.strip() == "0.0" or val.strip() == "0":
                        column_empty_count[idx] += 1
                    column_values_count[idx] += 1
                    
        for idx, header in enumerate(headers):
            empty_pct = (column_empty_count[idx] / len(rows) * 100) if len(rows) > 0 else 0
            print(f"    Col {idx}: {header} | Empty/0/None: {column_empty_count[idx]}/{len(rows)} ({empty_pct:.1f}%)")
"""
        sftp = ssh.open_sftp()
        with sftp.file(f"{remote_base}/backend/inspect_generated_files.py", "w") as f:
            f.write(python_inspect_code)
        sftp.close()

        cmd_run = f"cd {remote_base} && docker compose exec -T backend python inspect_generated_files.py"
        stdin, stdout, stderr = ssh.exec_command(cmd_run)
        
        print(stdout.read().decode('utf-8'))
        print(stderr.read().decode('utf-8'))

        ssh.exec_command(f"rm {remote_base}/backend/inspect_generated_files.py")

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
