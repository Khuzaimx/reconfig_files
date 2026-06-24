import paramiko
import sys
import os

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    hostname = "
    username = "s"
    password = "9 "
    remote_base = "/h "

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to remote VM {hostname}...")
        ssh.connect(hostname, username=username, password=password, timeout=15)
        print("Connected successfully!")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        python_inspect_code = """
import django
import os
import sys
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import EmailVerificationOTP, User

try:
    print("=== OTP Verification Records Created Today (June 24, 2026) ===")
    today = timezone.localdate()
    otps = EmailVerificationOTP.objects.filter(created_at__date=today).order_by('-created_at')
    
    print(f"Total OTPs generated today: {otps.count()}")
    for o in otps[:15]:
        local_created = o.created_at + timedelta(hours=5)
        print(f"ID: {o.id} | Email: {o.email} | OTP: {o.otp} | Verified: {o.is_verified} | Created (Local): {local_created}")
        
    print("\\n=== Checking if users were successfully created for these emails ===")
    emails = otps.values_list('email', flat=True).distinct()
    for email in emails:
        user_exists = User.objects.filter(email=email).exists()
        print(f"Email: {email} -> Registered in User Table? {user_exists}")

except Exception as e:
    print(f"Error: {e}")
"""
        
        # Write script to VM
        sftp = ssh.open_sftp()
        temp_script_path = f"{remote_base}/backend/inspect_otp_failures_temp.py"
        with sftp.file(temp_script_path, "w") as f:
            f.write(python_inspect_code)
        sftp.close()

        # Run script
        print("\n=== DB QUERY: OTP GENERATION STATS ===")
        cmd_run = f"cd {remote_base} && docker compose exec -T backend python inspect_otp_failures_temp.py"
        stdin, stdout, stderr = ssh.exec_command(cmd_run)
        print(stdout.read().decode('utf-8', errors='ignore'))
        print(stderr.read().decode('utf-8', errors='ignore'))

        # Cleanup inspection script
        ssh.exec_command(f"rm {temp_script_path}")

        # Fetch celery logs containing send_otp_email_task or email errors for today
        print("\n=== GREPING CELERY WORKER LOGS FOR TODAY'S OTP TASKS ===")
        cmd_celery = f"cd {remote_base} && docker compose logs celery_worker | grep -i -E 'send_otp_email_task|email|smtp|error|fail' | grep '2026-06-24' | tail -n 100"
        stdin, stdout, stderr = ssh.exec_command(cmd_celery)
        print(stdout.read().decode('utf-8', errors='ignore'))

        print("\n=== GREPING BACKEND LOGS FOR TODAY'S OTP/EMAIL ERRORS ===")
        cmd_backend = f"cd {remote_base} && docker compose logs backend | grep -i -E 'otp|email|smtp|error|fail' | grep '2026-06-24' | tail -n 50"
        stdin, stdout, stderr = ssh.exec_command(cmd_backend)
        print(stdout.read().decode('utf-8', errors='ignore'))

    finally:
        ssh.close()

if __name__ == '__main__':
    main()
