"""Local setup and administrator bootstrap. Never prints secrets."""
import argparse
import getpass
import secrets

from sqlalchemy import select

from .core.config import ROOT, Settings
from .core.security import password_hasher
from .database import make_database
from .models import AuditEvent, User, UserSettings
from .schemas import Registration


def init_local():
    (ROOT / "runtime").mkdir(exist_ok=True)
    destination = ROOT / ".env"
    if destination.exists():
        print(".env already exists; configuration preserved.")
        return
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(f"RF_JWT_SECRET={secrets.token_urlsafe(48)}\nRF_ENVIRONMENT=development\nRF_COOKIE_SECURE=false\n")
    print("Created local .env with a random signing secret. Run migrations next.")


def create_admin():
    email = input("Administrator email: ").strip()
    display_name = input("Display name: ").strip()
    password = getpass.getpass("Password (at least 12 characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")
    payload = Registration(email=email, display_name=display_name, password=password)
    engine, sessions = make_database(Settings().database_url)
    try:
        with sessions() as db:
            if db.scalar(select(User).where(User.email == str(payload.email))):
                raise SystemExit("Account exists. Use an existing administrator to manage roles.")
            user = User(email=str(payload.email), display_name=payload.display_name, password_hash=password_hasher.hash(payload.password), role="administrator")
            db.add(user)
            db.flush()
            db.add(UserSettings(user_id=user.id))
            db.add(AuditEvent(actor_id=user.id, action="admin.bootstrap", resource_id=user.id))
            db.commit()
        print("Administrator created.")
    finally:
        engine.dispose()


def init_postgres():
    init_local()
    path = ROOT / ".env"
    if any(line.strip().startswith("RF_POSTGRES_PASSWORD=") for line in path.read_text(encoding="utf-8").splitlines()):
        print("PostgreSQL configuration already exists; preserved.")
        return
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"\nRF_POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n")
    print("Added a random PostgreSQL password to the ignored .env file.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init-local", "create-admin", "init-postgres"])
    args = parser.parse_args()
    {"init-local": init_local, "create-admin": create_admin, "init-postgres": init_postgres}[args.command]()


if __name__ == "__main__":
    main()
