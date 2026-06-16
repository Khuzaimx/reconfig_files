import paramiko
import sys

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    hostname = "5"
    username = ""
    password = "9"
    remote_base = "/home/sj/psych_experiment_platform"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname, username=username, password=password, timeout=15)
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

    try:
        python_inspect_code = """
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from groups.models import Group
from activities.models import Activity
from questionnaires.models import ResponseSet

print("=== Groups in DB ===")
for g in Group.objects.all():
    print(f"Group: {g.name} | Active: {g.is_active} | Capacity: {g.capacity}")

print("\\n=== Total Activities in DB ===")
print(f"Total: {Activity.objects.count()}")

print("\\n=== Activities for Group 4 ===")
g4_acts = Activity.objects.filter(group__name='Group 4')
print(f"Total for Group 4: {g4_acts.count()}")
for act in g4_acts:
    print(f"ID: {act.id} | Title: {act.title} | Day: {act.day_number}")

print("\\n=== Activities without Group ===")
no_grp_acts = Activity.objects.filter(group__isnull=True)
print(f"Total without group: {no_grp_acts.count()}")
for act in no_grp_acts:
    print(f"ID: {act.id} | Title: {act.title} | Day: {act.day_number}")

print("\\n=== Completed ResponseSets in DB ===")
print(f"Total Completed: {ResponseSet.objects.filter(status='COMPLETED').count()}")
"""
        
        # Write and run the inspection script
        sftp = ssh.open_sftp()
        with sftp.file(f"{remote_base}/backend/inspect_db_temp.py", "w") as f:
            f.write(python_inspect_code)
        sftp.close()

        cmd_run = f"cd {remote_base} && docker compose exec -T backend python inspect_db_temp.py"
        stdin, stdout, stderr = ssh.exec_command(cmd_run)
        
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        
        print("\n=== INSPECTION OUTPUT ===")
        print(out)
        print("=== INSPECTION ERROR ===")
        print(err)

        # Cleanup
        ssh.exec_command(f"rm {remote_base}/backend/inspect_db_temp.py")

    finally:
        ssh.close()

if __name__ == "__main__":
    main()
