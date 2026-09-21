# Oracle DB Encrypted Config using DPAPI

This project uses Windows DPAPI (Data Protection API) and Fernet to encrypt environment variables safely.

## Setup
To initialize the environment configuration, run the following Conda command from the repository root:

```bash
conda run -n monitor_backend python backend/bootstrap_env.py
```

This script will:
1. Prompt for DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_SERVICE_NAME, and SECRET_KEY.
2. Generate a random Fernet key and encrypt the environment variables into `.env.enc`.
3. Encrypt the Fernet key using DPAPI and write it to `env.key.dpapi`.
4. Clean up any temporary files.

## Loading Configuration
The application automatically reads `env.key.dpapi` and `.env.enc` on startup to load configuration. No secrets are stored in plaintext.

## Testing
To run tests locally from a Windows CMD shell:
```bat
set PYTHONPATH=backend&& conda run -n monitor_backend python -m pytest backend/tests -q
```

From PowerShell use:
```powershell
$env:PYTHONPATH = "backend"; conda run -n monitor_backend python -m pytest backend/tests -q
```
