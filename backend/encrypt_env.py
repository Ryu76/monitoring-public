import os
from cryptography.fernet import Fernet

def generate_key():
    key = Fernet.generate_key()
    with open("env.key", "wb") as key_file:
        key_file.write(key)
    return key

def load_key():
    if not os.path.exists("env.key"):
        return generate_key()
    with open("env.key", "rb") as key_file:
        return key_file.read()

def encrypt_file(filename, key):
    f = Fernet(key)
    with open(filename, "rb") as file:
        file_data = file.read()
    encrypted_data = f.encrypt(file_data)
    with open(filename.replace(".raw", ".enc"), "wb") as file:
        file.write(encrypted_data)

if __name__ == "__main__":
    raw_env_file = ".env.raw"
    if os.path.exists(raw_env_file):
        key = load_key()
        encrypt_file(raw_env_file, key)
        print("Encryption complete. Generated env.key and .env.enc")
    else:
        print(f"Error: {raw_env_file} not found.")
