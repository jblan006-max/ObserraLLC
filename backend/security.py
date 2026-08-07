"""App-level secret encryption for admin-entered IdP credentials stored in Mongo.

The KEK is a deployment secret (APP_SETTINGS_KEK), never entered by the admin and
never stored alongside the ciphertext.
"""
import os
from cryptography.fernet import Fernet

_cipher = Fernet(os.environ["APP_SETTINGS_KEK"].encode())


def encrypt_secret(value: str) -> str:
    return _cipher.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _cipher.decrypt(value.encode()).decode()
