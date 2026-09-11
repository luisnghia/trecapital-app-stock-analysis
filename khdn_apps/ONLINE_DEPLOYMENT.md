# KHDN Ops V2.23 - Online deployment

Entrypoint when embedded in the Trecapital Streamlit app: `pages/KHDNApps.py`.

## Required secret

For public Internet deployment, configure a strong secret in Streamlit Community Cloud:

```toml
KHDN_ADMIN_PASSWORD = "<strong initial admin password>"
```

The online build deliberately does **not** fall back to `admin / Admin@123`.

## Persistence warning

The current KHDN engine uses SQLite. Streamlit Community Cloud local files are not guaranteed to survive rebuilds/restarts. Use the page as an online preview or configure a persistent host/database before production operational data is entered.
