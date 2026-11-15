"""Prints the two secrets you need. Run:  python scripts/generate_secrets.py   (needs `pip install cryptography`)"""
import secrets
from cryptography.fernet import Fernet
print("SECRET_KEY=" + secrets.token_urlsafe(48))
print("FIELD_ENCRYPTION_KEYS=" + Fernet.generate_key().decode())
print("\nStore FIELD_ENCRYPTION_KEYS in a password manager. If it is lost, encrypted fields (phone, address, notes, face data, report text) cannot be recovered.")
