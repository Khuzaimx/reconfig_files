"""
update_admin_credentials.py
────────────────────────────
Connects to the production VM via SSH and:
  1. Updates / creates the Django superuser with the new credentials.
  2. Patches the remote .env file to persist the new DJANGO_SUPERUSER_* vars
     so future container restarts don't revert the credentials.
"""

import sys
import paramiko

# ── Remote VM ──────────────────────────────────────────────────────────────────
HOSTNAME = "5 "
SSH_USER = "s"
SSH_PASS = "9 "
REMOTE_BASE = "/ "

# ── New admin credentials ──────────────────────────────────────────────────────
NEW_USERNAME = " "
NEW_EMAIL    = " "
NEW_PASSWORD = " "

# ── Helpers ────────────────────────────────────────────────────────────────────

def run(ssh, cmd, label=""):
    tag = f"[{label}] " if label else ""
    print(f"\n{tag}>>> {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    print(f"Exit code: {code}")
    return code == 0, out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    print("=== Connecting to remote VM ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOSTNAME, username=SSH_USER, password=SSH_PASS, timeout=15)
    print(f"Connected to {HOSTNAME} as {SSH_USER}")

    try:
        # ── Step 1: Update the Django superuser in the live DB ─────────────────
        print("\n=== Step 1: Updating admin credentials in the database ===")

        # Escape the password for the shell
        pwd_escaped = NEW_PASSWORD.replace("'", "'\\''")

        django_cmd = (
            f"cd {REMOTE_BASE} && "
            f"docker compose exec -T backend python manage.py shell -c \""
            f"from django.contrib.auth import get_user_model; "
            f"from users.models import Role; "
            f"User = get_user_model(); "
            f"role, _ = Role.objects.get_or_create(name='Admin'); "
            f"u = None; "
            f"targets = ['{NEW_USERNAME}', 'admin', 'administrator']; "
            f"found = [User.objects.filter(username=n, is_superuser=True).first() for n in targets]; "
            f"u = next((x for x in found if x), None); "
            f"created = False; "
            f"u = u or (User.objects.create_superuser(username='{NEW_USERNAME}', email='{NEW_EMAIL}', password='{pwd_escaped}') or None); "
            f"u.username = '{NEW_USERNAME}'; "
            f"u.email = '{NEW_EMAIL}'; "
            f"u.set_password('{pwd_escaped}'); "
            f"u.role = role; "
            f"u.is_superuser = True; "
            f"u.is_staff = True; "
            f"u.save(); "
            f"print('Admin credentials updated: username={NEW_USERNAME}')\""
        )
        ok, _ = run(ssh, django_cmd, "Django")
        if not ok:
            print("WARNING: Django shell command may have failed — check output above.")

        # ── Step 2: Patch .env on the server ───────────────────────────────────
        print("\n=== Step 2: Patching .env on the remote server ===")

        env_path = f"{REMOTE_BASE}/.env"

        # Remove any old DJANGO_SUPERUSER_* lines then append the new ones
        patch_cmd = (
            f"sed -i '/^DJANGO_SUPERUSER_/d' {env_path} && "
            f"echo 'DJANGO_SUPERUSER_USERNAME={NEW_USERNAME}' >> {env_path} && "
            f"echo 'DJANGO_SUPERUSER_EMAIL={NEW_EMAIL}' >> {env_path} && "
            f"echo 'DJANGO_SUPERUSER_PASSWORD={pwd_escaped}' >> {env_path}"
        )
        run(ssh, patch_cmd, ".env patch")

        # Verify
        run(ssh, f"grep DJANGO_SUPERUSER {env_path}", "Verify .env")

        print("\n=== All done! ===")
        print(f"Admin login: username={NEW_USERNAME}  password={NEW_PASSWORD}")
        print("The credentials are now live in the DB and persisted in .env.")

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
