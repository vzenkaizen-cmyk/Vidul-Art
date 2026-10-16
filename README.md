# Art Competition Platform

A Streamlit + Neon PostgreSQL starter platform for the art competition.

## Features

- Colorful welcome page using the supplied art-competition landscape image.
- Sign-in and account creation in separate role tabs.
- Student accounts: name, father's name, age category, site, username and password.
- Site supervisor accounts: Vidullanka email, password and assigned site.
- Teachers and admins: Vidullanka email and password.
- Supervisors can see students and upload/replace a student's artwork PDF only at their assigned site.
- Teachers can see entries from all sites, download PDFs, save marks and feedback, and publish three winners for each age category.
- Public winners page and admin overview.
- Passwords are stored as PBKDF2 hashes, not plaintext.

## 1. Create a Neon database

1. Create a PostgreSQL project in Neon.
2. Copy the connection string from Neon.
3. In the connection string, keep SSL enabled (`sslmode=require`).

## 2. Configure the app

For local development, copy `.env.example` to `.env` and set `DATABASE_URL`. Streamlit does not automatically load `.env`; either export the variables in your shell or install `python-dotenv` and load it at the top of `app.py`.

PowerShell example:

```powershell
$env:DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
$env:ALLOWED_STAFF_EMAIL_DOMAINS="vidullanka.com"
```

Change `ALLOWED_STAFF_EMAIL_DOMAINS` to the actual company email domain(s). The default is a placeholder and may not match your organization's real domain.

## 3. Install and run

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The database tables are created automatically at startup.

## 4. Deploy on Streamlit Community Cloud

1. Push this folder to a private GitHub repository if it contains internal information.
2. Deploy `app.py`.
3. In app settings, add secrets:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
ALLOWED_STAFF_EMAIL_DOMAINS = "vidullanka.com"
```

If using Streamlit secrets, the app reads `DATABASE_URL`; the staff domain is currently read from the environment. Set it in the environment too, or change the code to read `st.secrets["ALLOWED_STAFF_EMAIL_DOMAINS"]`.

## Important production notes

- This starter allows staff accounts to self-register if they use an authorized email domain. For a real competition, admin account creation should be invitation-only or manually approved. Email-domain checking alone does not prove that an email belongs to the person creating the account.
- Consider email verification, password reset, login rate limiting, audit logs, file scanning, backups, and a formal retention policy before production use.
- PDF uploads are stored in Neon as binary data. Keep the 15 MB per-file limit, and monitor database storage. For larger volumes, use object storage and store file references in PostgreSQL.
- The list of sites and age categories is configurable near the top of `app.py`.
- The sign-in background uses the supplied second image (the notebook sketch) as requested. Replace `assets/signin_background.jpg` with another image if you intended a different background. The welcome page uses the supplied fourth image.
- Streamlit is used for the complete application. React is not required for this version; Streamlit CSS provides the colorful layout while keeping deployment simple.


## Fix for existing Neon database schema

The app now runs safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations at startup, including the missing `father_name` column. Restart Streamlit after replacing `app.py`.

## Reset the previously registered admin account (optional)

If you want to register the admin account again, open Neon Console → SQL Editor and run `reset_existing_admin.sql`. Check that the email in that file is the account you intend to remove before running it. Then return to the website and create the admin account again.
