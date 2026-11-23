"""Create the platform-owner (Super Admin) account.

Usage (from backend/):  python -m scripts.create_super_admin
Prompts for email + password (never stored in shell history or the repo)."""
import asyncio
import getpass

from app import db as database
from app.security import hash_password, validate_password_strength
from app.utils import new_id, utcnow


async def main():
    await database.connect()
    db = database.get_db()
    if await db.users.find_one({"role": "super_admin"}):
        print("A Super Admin already exists. Nothing to do.")
        return
    name = input("Name [Machellix]: ").strip() or "Machellix"
    email = input("Email: ").strip().lower()
    pw = getpass.getpass("Password (min 10 chars, letters+numbers): ")
    if pw != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    validate_password_strength(pw, email)
    await db.users.insert_one({"_id": new_id(), "name": name, "email": email, "role": "super_admin", "password_hash": hash_password(pw),
                               "is_active": True, "must_change_password": False, "token_version": 0, "created_at": utcnow(), "updated_at": utcnow()})
    print("Super Admin created. Sign in at /super-admin/login and enable MFA from your profile.")
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
