import os
import io
import hmac
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image
from sqlalchemy import (
    create_engine, text, MetaData, Table, Column, Integer, String,
    LargeBinary, DateTime, Float, ForeignKey, UniqueConstraint
)
from sqlalchemy.exc import IntegrityError

# ---------------------------------------------------------------------
# Art Competition Platform — Streamlit + Neon PostgreSQL
# ---------------------------------------------------------------------
st.set_page_config(page_title="Art Competition", page_icon="🎨", layout="wide")

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
AGE_CATEGORIES = ["Under 5", "5–7", "8–10", "11–13", "14–16", "17+"]
SITES = [
    "BBO", "BTO", "BKN", "DPV","EME", "GNT","HRN 1", "HRN 2","LKM","MDP", "MGT","MTR","MVB",
    "ORK","RDP", "UDW", "VBL","WMB"
]
STAFF_EMAIL_DOMAINS = [
    d.strip().lower().lstrip("@")
    for d in os.getenv("ALLOWED_STAFF_EMAIL_DOMAINS", "vidullanka.com").split(",")
    if d.strip()
]
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL and "DATABASE_URL" in st.secrets:
    DATABASE_URL = str(st.secrets["DATABASE_URL"]).strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Keep passwords hashed; never store plaintext passwords.
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{salt.hex()}:{digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 310_000
        ).hex()
        return hmac.compare_digest(digest, digest_hex)
    except (ValueError, TypeError):
        return False

def staff_email_valid(email: str) -> bool:
    email = email.strip().lower()
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1]
    return any(domain == allowed or domain.endswith("." + allowed)
               for allowed in STAFF_EMAIL_DOMAINS)

def get_engine():
    if not DATABASE_URL:
        return None
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

@st.cache_resource
def engine_resource(url: str):
    return create_engine(url, pool_pre_ping=True, pool_recycle=300)

def db_engine():
    if not DATABASE_URL:
        return None
    return engine_resource(DATABASE_URL)

def init_db(engine):
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            role VARCHAR(20) NOT NULL,
            username VARCHAR(120) UNIQUE,
            email VARCHAR(255) UNIQUE,
            password_hash TEXT NOT NULL,
            full_name VARCHAR(255),
            father_name VARCHAR(255),
            age_category VARCHAR(50),
            site VARCHAR(100),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """))
        # Migrate databases created by older versions of the app. CREATE TABLE IF NOT
        # EXISTS does not add columns to an existing table, so add missing columns here.
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS father_name VARCHAR(255)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS age_category VARCHAR(50)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS site VARCHAR(100)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(255)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(120)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20)"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_migrated ON users (username) WHERE username IS NOT NULL"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_migrated ON users (email) WHERE email IS NOT NULL"))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS artworks (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            uploaded_by INTEGER NOT NULL REFERENCES users(id),
            file_name VARCHAR(255) NOT NULL,
            mime_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
            pdf_data BYTEA NOT NULL,
            uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id)
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS artwork_marks (
            id SERIAL PRIMARY KEY,
            artwork_id INTEGER NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
            teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            marks NUMERIC(5,2) NOT NULL CHECK (marks >= 0 AND marks <= 100),
            comments TEXT,
            marked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artwork_id, teacher_id)
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS winners (
            id SERIAL PRIMARY KEY,
            age_category VARCHAR(50) NOT NULL,
            place INTEGER NOT NULL CHECK (place BETWEEN 1 AND 3),
            student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            selected_by INTEGER NOT NULL REFERENCES users(id),
            selected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(age_category, place),
            UNIQUE(age_category, student_id)
        )
        """))

def query_all(sql, params=None):
    with db_engine().begin() as conn:
        return conn.execute(text(sql), params or {}).mappings().all()

def query_one(sql, params=None):
    with db_engine().begin() as conn:
        return conn.execute(text(sql), params or {}).mappings().first()

def execute(sql, params=None):
    with db_engine().begin() as conn:
        return conn.execute(text(sql), params or {})

def inject_css():
    welcome = ASSETS / "welcome_background.png"
    signin = ASSETS / "signin_background.jpg"
    if welcome.exists():
        welcome_uri = "data:image/png;base64," + __import__("base64").b64encode(welcome.read_bytes()).decode()
    else:
        welcome_uri = ""
    if signin.exists():
        signin_uri = "data:image/jpeg;base64," + __import__("base64").b64encode(signin.read_bytes()).decode()
    else:
        signin_uri = ""
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}
    .stApp {{
      background: linear-gradient(rgba(246,249,252,.88), rgba(246,249,252,.88)), url('{signin_uri}');
      background-size: cover; background-position: center; background-attachment: fixed;
    }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1250px; }}
    .hero {{
      min-height: 470px; border-radius: 28px; overflow: hidden; padding: 54px 5%;
      display:flex; flex-direction:column; justify-content:center; color:#123047;
      background-image: linear-gradient(90deg, rgba(255,255,255,.91), rgba(255,255,255,.45)), url('{welcome_uri}');
      background-size: cover; background-position: center;
      box-shadow: 0 18px 50px rgba(20,45,70,.13);
    }}
    .hero h1 {{ font-size: clamp(2.2rem, 5vw, 4.2rem); line-height:1.08; margin:0 0 14px; font-weight:800; }}
    .hero p {{ font-size:1.08rem; max-width:640px; }}
    .pill {{ display:inline-block; background:#fff0d8; color:#945300; border-radius:30px; padding:8px 14px; font-weight:600; width:max-content; }}
    .panel {{
      background:rgba(255,255,255,.96); border:1px solid rgba(255,255,255,.8);
      border-radius:22px; padding:25px; margin-bottom:16px;
      box-shadow:0 12px 36px rgba(24,48,72,.10);
    }}
    .feature-card {{
      min-height: 205px; height: 100%; padding: 20px 22px;
      box-sizing: border-box; overflow-wrap: anywhere;
    }}
    .feature-card h3 {{ font-size: 1.28rem; line-height: 1.25; margin: 0 0 12px; }}
    .feature-card p {{ font-size: .96rem; line-height: 1.65; margin-bottom: 0; }}
    [data-testid="stHorizontalBlock"] {{ align-items: stretch; gap: 1rem; }}
    [data-testid="stColumn"] {{ min-width: 0; }}
    .section-title {{ font-size:1.55rem; color:#16354a; font-weight:700; }}
    .small-muted {{ color:#607487; }}
    div.stButton > button {{ border-radius:12px; min-height:2.8rem; font-weight:600; }}
    div[data-testid="stForm"] {{ background:rgba(255,255,255,.96); padding:22px; border-radius:18px; border:1px solid #e7edf3; }}
    .stTabs [data-baseweb="tab-list"] {{ gap:8px; }}
    .stTabs [data-baseweb="tab"] {{ border-radius:10px; padding:9px 16px; }}
    </style>
    """, unsafe_allow_html=True)

inject_css()

if not DATABASE_URL:
    st.markdown('<div class="panel"><h2>Connect your Neon database</h2><p>Add your Neon PostgreSQL connection string as <code>DATABASE_URL</code> in a local <code>.env</code> file or Streamlit secrets. See README.md for setup.</p></div>', unsafe_allow_html=True)
    st.stop()

engine = db_engine()
try:
    init_db(engine)
except Exception as e:
    st.error("Could not initialize the database. Check DATABASE_URL and that your Neon database is reachable.")
    st.caption(f"Technical detail: {e}")
    st.stop()

def create_staff(role, email, password, name=None, site=None):
    # Teachers may register with any valid email address. Admins and site
    # supervisors remain restricted to authorized Vidullanka email domains.
    if role in ("admin", "supervisor") and not staff_email_valid(email):
        domains = ", ".join("@" + d for d in STAFF_EMAIL_DOMAINS)
        raise ValueError(f"Use an authorized Vidullanka email address ({domains}). Set ALLOWED_STAFF_EMAIL_DOMAINS if your company uses another domain.")
    if "@" not in email.strip() or "." not in email.strip().rsplit("@", 1)[-1]:
        raise ValueError("Enter a valid email address.")
    execute("""
      INSERT INTO users (role, email, username, password_hash, full_name, site)
      VALUES (:role, :email, :username, :password_hash, :full_name, :site)
    """, {
        "role": role, "email": email.strip().lower(),
        "username": email.strip().lower(), "password_hash": hash_password(password),
        "full_name": (name or "").strip() or None, "site": site
    })

def create_student(name, father, age, site, username, password):
    execute("""
      INSERT INTO users (role, username, password_hash, full_name, father_name, age_category, site)
      VALUES ('student', :username, :password_hash, :name, :father, :age, :site)
    """, {
        "username": username.strip(), "password_hash": hash_password(password),
        "name": name.strip(), "father": father.strip(), "age": age, "site": site
    })

def authenticate(identifier, password):
    row = query_one("""
      SELECT * FROM users
      WHERE lower(coalesce(username,'')) = lower(:identifier)
         OR lower(coalesce(email,'')) = lower(:identifier)
      LIMIT 1
    """, {"identifier": identifier.strip()})
    if row and verify_password(password, row["password_hash"]):
        return dict(row)
    return None

def average_marks(artwork_id):
    row = query_one("SELECT AVG(marks) AS avg_marks FROM artwork_marks WHERE artwork_id=:id", {"id": artwork_id})
    return float(row["avg_marks"]) if row and row["avg_marks"] is not None else None

def show_winners():
    winners = query_all("""
      SELECT w.age_category, w.place, u.full_name, u.father_name, u.site,
             COALESCE(AVG(m.marks), 0) AS avg_marks
      FROM winners w JOIN users u ON u.id=w.student_id
      LEFT JOIN artworks a ON a.student_id=u.id
      LEFT JOIN artwork_marks m ON m.artwork_id=a.id
      GROUP BY w.id, w.age_category, w.place, u.full_name, u.father_name, u.site
      ORDER BY w.age_category, w.place
    """)
    if not winners:
        st.info("Winners will appear here after teachers publish the results.")
        return
    categories = list(dict.fromkeys(x["age_category"] for x in winners))
    for category in categories:
        st.subheader(f"🏆 {category}")
        cols = st.columns(3)
        subset = [w for w in winners if w["age_category"] == category]
        for i, w in enumerate(subset):
            with cols[int(w["place"]) - 1]:
                st.markdown('<div class="panel">', unsafe_allow_html=True)
                st.markdown(["🥇 **1st Place**", "🥈 **2nd Place**", "🥉 **3rd Place**"][int(w["place"])-1])
                st.write(w["full_name"])
                st.caption(f"Site: {w['site']} · Average marks: {float(w['avg_marks']):.1f}/100")
                st.markdown('</div>', unsafe_allow_html=True)

# Navigation and welcome
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "Welcome"

with st.sidebar:
    st.markdown("## 🎨 Art Competition")
    if st.session_state.user:
        st.success(f"Signed in as {st.session_state.user['role'].title()}")
        st.caption(st.session_state.user.get("full_name") or st.session_state.user.get("username") or st.session_state.user.get("email"))
        if st.button("Sign out", use_container_width=True):
            st.session_state.user = None
            st.session_state.page = "Welcome"
            st.rerun()
    else:
        choice = st.radio("Navigate", ["Welcome", "Sign in", "Create account", "Winners"], label_visibility="collapsed")
        st.session_state.page = choice

user = st.session_state.user

if not user:
    if st.session_state.page == "Welcome":
        st.markdown("""
        <div class="hero">
          <span class="pill">✨ Creativity from every site</span>
          <h1>Art Competition<br>2026</h1>
          <p>Celebrating young artists, imagination and the stories behind every artwork. Explore the competition, sign in, or create an account to take part.</p>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="panel feature-card"><h3>🖌️ Student artists</h3><p>Register with your site and age category, then submit your artwork through your site supervisor.</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="panel feature-card"><h3>📍 Site supervisors</h3><p>Access only your assigned site and upload student artwork as PDF files.</p></div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="panel feature-card"><h3>🏆 Teachers</h3><p>Review entries from all sites, mark each artwork and publish three winners per age category.</p></div>', unsafe_allow_html=True)

    elif st.session_state.page == "Sign in":
        st.markdown('<div class="panel"><h2>Welcome back 👋</h2><p class="small-muted">Sign in to continue to the Art Competition Platform.</p></div>', unsafe_allow_html=True)
        st.write("")
        col1, col2 = st.columns([1, 1], gap="large")
        with col1:
            with st.form("signin_form"):
                identifier = st.text_input("Username or Vidullanka email")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
                if submit:
                    found = authenticate(identifier, password)
                    if found:
                        st.session_state.user = found
                        st.session_state.page = "Dashboard"
                        st.rerun()
                    else:
                        st.error("Invalid username/email or password.")
        with col2:
            st.markdown('<div class="panel"><h3>One platform, four roles</h3><p>Students · Site supervisors · Teachers · Admin</p><p class="small-muted">Staff accounts must use an authorized Vidullanka email address. Supervisors are restricted to their assigned site.</p></div>', unsafe_allow_html=True)

    elif st.session_state.page == "Create account":
        st.markdown('<div class="panel"><h2>Create your account</h2><p class="small-muted">Choose the account type that matches your role.</p></div>', unsafe_allow_html=True)
        role_tab_student, role_tab_supervisor, role_tab_teacher, role_tab_admin = st.tabs(["🎨 Student", "📍 Site supervisor", "👩‍🏫 Teacher", "🛡️ Admin"])
        with role_tab_student:
            with st.form("student_register"):
                name = st.text_input("Student's full name")
                father = st.text_input("Father's name")
                age = st.selectbox("Age category", AGE_CATEGORIES)
                site = st.selectbox("Site", SITES)
                username = st.text_input("Create username")
                pw = st.text_input("Create password", type="password")
                pw2 = st.text_input("Confirm password", type="password")
                ok = st.form_submit_button("Create student account", type="primary", use_container_width=True)
                if ok:
                    if not all([name.strip(), father.strip(), username.strip(), pw]):
                        st.error("Complete all fields.")
                    elif len(pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif pw != pw2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            create_student(name, father, age, site, username, pw)
                            st.success("Student account created. You can now sign in.")
                        except IntegrityError:
                            st.error("That username is already taken. Please choose another.")
                        except Exception as e:
                            st.error(f"Could not create account: {e}")
        with role_tab_supervisor:
            st.info("A site supervisor can view student records and upload PDFs only for the site assigned to their account.")
            with st.form("supervisor_register"):
                name = st.text_input("Supervisor's name")
                email = st.text_input("Vidullanka email", key="sup_email")
                site = st.selectbox("Assigned site (you can access only this site)", SITES, key="sup_site")
                pw = st.text_input("Create password", type="password", key="sup_pw")
                pw2 = st.text_input("Confirm password", type="password", key="sup_pw2")
                ok = st.form_submit_button("Create supervisor account", type="primary", use_container_width=True)
                if ok:
                    if not email.strip() or not pw or not name.strip():
                        st.error("Complete all fields.")
                    elif len(pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif pw != pw2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            create_staff("supervisor", email, pw, name, site)
                            st.success("Supervisor account created. Sign in using your Vidullanka email.")
                        except IntegrityError:
                            st.error("An account already exists for this email.")
                        except ValueError as e:
                            st.error(str(e))
        with role_tab_teacher:
            with st.form("teacher_register"):
                name = st.text_input("Teacher's name")
                email = st.text_input("Email", key="teacher_email", placeholder="Enter your email address")
                pw = st.text_input("Create password", type="password", key="teacher_pw")
                pw2 = st.text_input("Confirm password", type="password", key="teacher_pw2")
                ok = st.form_submit_button("Create teacher account", type="primary", use_container_width=True)
                if ok:
                    if not email.strip() or not pw or not name.strip():
                        st.error("Complete all fields.")
                    elif len(pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif pw != pw2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            create_staff("teacher", email, pw, name)
                            st.success("Teacher account created. Sign in using your email address.")
                        except IntegrityError:
                            st.error("An account already exists for this email.")
                        except ValueError as e:
                            st.error(str(e))
        with role_tab_admin:
            st.warning("Admin accounts have platform-wide access. Only authorized Vidullanka staff should create one.")
            with st.form("admin_register"):
                name = st.text_input("Admin's name")
                email = st.text_input("Vidullanka email", key="admin_email")
                pw = st.text_input("Create password", type="password", key="admin_pw")
                pw2 = st.text_input("Confirm password", type="password", key="admin_pw2")
                ok = st.form_submit_button("Create admin account", type="primary", use_container_width=True)
                if ok:
                    if not email.strip() or not pw or not name.strip():
                        st.error("Complete all fields.")
                    elif len(pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif pw != pw2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            create_staff("admin", email, pw, name)
                            st.success("Admin account created. Sign in using your Vidullanka email.")
                        except IntegrityError:
                            st.error("An account already exists for this email.")
                        except ValueError as e:
                            st.error(str(e))
    elif st.session_state.page == "Winners":
        st.title("🏆 Competition winners")
        show_winners()

else:
    role = user["role"]
    st.title(f"Hello, {user.get('full_name') or user.get('username') or user.get('email')} 👋")
    st.caption(f"{role.title()} dashboard")
    if role == "student":
        st.markdown('<div class="panel"><h3>Your competition profile</h3></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Age category", user.get("age_category") or "—")
        c2.metric("Site", user.get("site") or "—")
        c3.metric("Artwork status", "Submitted" if query_one("SELECT id FROM artworks WHERE student_id=:id", {"id": user["id"]}) else "Not submitted")
        st.info("Your site supervisor uploads your artwork PDF. Contact your supervisor if you need to correct your details.")
        st.subheader("Published winners")
        show_winners()

    elif role == "supervisor":
        st.markdown(f'<div class="panel"><h3>📍 Assigned site: {user.get("site")}</h3><p>You can only access students registered under this site.</p></div>', unsafe_allow_html=True)
        students = query_all("""
          SELECT u.id, u.full_name, u.father_name, u.age_category, u.site,
                 a.id AS artwork_id, a.file_name, a.uploaded_at
          FROM users u LEFT JOIN artworks a ON a.student_id=u.id
          WHERE u.role='student' AND u.site=:site
          ORDER BY u.age_category, u.full_name
        """, {"site": user["site"]})
        if not students:
            st.info("No students have registered for your site yet.")
        else:
            for s in students:
                with st.expander(f"{s['full_name']} · {s['age_category']} · {'PDF uploaded' if s['artwork_id'] else 'Awaiting artwork'}"):
                    st.write(f"**Father's name:** {s['father_name']}")
                    st.write(f"**Site:** {s['site']}")
                    if s["artwork_id"]:
                        art = query_one("SELECT file_name, pdf_data FROM artworks WHERE id=:id", {"id": s["artwork_id"]})
                        st.download_button("Download current artwork PDF", data=bytes(art["pdf_data"]), file_name=art["file_name"], mime="application/pdf", key=f"download_{s['id']}")
                    with st.form(f"upload_{s['id']}"):
                        uploaded = st.file_uploader("Upload student's artwork (PDF only)", type=["pdf"], key=f"pdf_{s['id']}")
                        submit = st.form_submit_button("Upload / replace artwork", type="primary")
                        if submit:
                            if not uploaded:
                                st.error("Choose a PDF file first.")
                            elif not uploaded.getvalue().startswith(b"%PDF"):
                                st.error("The uploaded file does not appear to be a valid PDF.")
                            elif len(uploaded.getvalue()) > 15 * 1024 * 1024:
                                st.error("PDF must be 15 MB or smaller.")
                            else:
                                try:
                                    execute("""
                                      INSERT INTO artworks (student_id, uploaded_by, file_name, mime_type, pdf_data)
                                      VALUES (:student_id, :uploaded_by, :file_name, 'application/pdf', :pdf_data)
                                      ON CONFLICT (student_id) DO UPDATE SET
                                        uploaded_by=EXCLUDED.uploaded_by,
                                        file_name=EXCLUDED.file_name,
                                        mime_type=EXCLUDED.mime_type,
                                        pdf_data=EXCLUDED.pdf_data,
                                        uploaded_at=CURRENT_TIMESTAMP
                                    """, {"student_id": s["id"], "uploaded_by": user["id"], "file_name": uploaded.name, "pdf_data": uploaded.getvalue()})
                                    st.success("Artwork uploaded.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Upload failed: {e}")

    elif role == "teacher":
        st.markdown('<div class="panel"><h3>👩‍🏫 Review artwork from all sites</h3><p>Open an age category, review each submitted PDF, award marks out of 100 and add feedback.</p></div>', unsafe_allow_html=True)
        category = st.selectbox("Select age category", AGE_CATEGORIES)
        artworks = query_all("""
          SELECT a.id AS artwork_id, a.file_name, a.pdf_data, a.uploaded_at,
                 u.id AS student_id, u.full_name, u.father_name, u.site, u.age_category
          FROM artworks a JOIN users u ON u.id=a.student_id
          WHERE u.age_category=:category
          ORDER BY u.site, u.full_name
        """, {"category": category})
        if not artworks:
            st.info("No artwork PDFs have been uploaded for this age category yet.")
        else:
            for a in artworks:
                with st.expander(f"{a['full_name']} · {a['site']} · {a['file_name']}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**Student:** {a['full_name']}")
                        st.write(f"**Father's name:** {a['father_name']}")
                        st.write(f"**Site:** {a['site']}")
                        st.download_button("Open / download artwork PDF", data=bytes(a["pdf_data"]), file_name=a["file_name"], mime="application/pdf", key=f"teacher_pdf_{a['artwork_id']}")
                    existing = query_one("SELECT marks, comments FROM artwork_marks WHERE artwork_id=:aid AND teacher_id=:tid", {"aid": a["artwork_id"], "tid": user["id"]})
                    with c2:
                        with st.form(f"mark_{a['artwork_id']}"):
                            marks = st.number_input("Marks (0–100)", min_value=0.0, max_value=100.0, value=float(existing["marks"]) if existing else 0.0, step=1.0)
                            comments = st.text_area("Feedback", value=existing["comments"] or "" if existing else "")
                            submit = st.form_submit_button("Save marks", type="primary")
                            if submit:
                                execute("""
                                  INSERT INTO artwork_marks (artwork_id, teacher_id, marks, comments)
                                  VALUES (:aid, :tid, :marks, :comments)
                                  ON CONFLICT (artwork_id, teacher_id) DO UPDATE SET
                                    marks=EXCLUDED.marks, comments=EXCLUDED.comments, marked_at=CURRENT_TIMESTAMP
                                """, {"aid": a["artwork_id"], "tid": user["id"], "marks": marks, "comments": comments})
                                st.success("Marks saved.")
                                st.rerun()
                    avg = average_marks(a["artwork_id"])
                    st.caption(f"Average teacher score: {avg:.1f}/100" if avg is not None else "No marks recorded yet.")
        st.divider()
        st.subheader("🏆 Select and publish the top three winners")
        st.caption("Choose one student for each place. The three choices must be different and must belong to the selected age category.")
        candidates = query_all("""
          SELECT u.id, u.full_name, u.father_name, u.site, AVG(m.marks) AS avg_marks
          FROM users u JOIN artworks a ON a.student_id=u.id
          JOIN artwork_marks m ON m.artwork_id=a.id
          WHERE u.role='student' AND u.age_category=:category
          GROUP BY u.id, u.full_name, u.father_name, u.site
          ORDER BY AVG(m.marks) DESC, u.full_name
        """, {"category": category})
        if not candidates:
            st.info("Students need uploaded artwork and at least one teacher mark before they can be selected as winners.")
        else:
            candidate_options = {f"{c['full_name']} — {c['site']} — {float(c['avg_marks']):.1f}/100": c["id"] for c in candidates}
            with st.form("winner_form"):
                place1 = st.selectbox("🥇 First place", list(candidate_options), key="winner1")
                place2 = st.selectbox("🥈 Second place", list(candidate_options), key="winner2", index=min(1, len(candidate_options)-1))
                place3 = st.selectbox("🥉 Third place", list(candidate_options), key="winner3", index=min(2, len(candidate_options)-1))
                publish = st.form_submit_button("Publish winners", type="primary", use_container_width=True)
                if publish:
                    selected = [candidate_options[place1], candidate_options[place2], candidate_options[place3]]
                    if len(set(selected)) != 3:
                        st.error("Choose three different students for first, second and third place.")
                    else:
                        try:
                            with db_engine().begin() as conn:
                                conn.execute(text("DELETE FROM winners WHERE age_category=:cat"), {"cat": category})
                                for place, student_id in enumerate(selected, 1):
                                    conn.execute(text("""
                                      INSERT INTO winners (age_category, place, student_id, selected_by)
                                      VALUES (:cat, :place, :student_id, :teacher)
                                    """), {"cat": category, "place": place, "student_id": student_id, "teacher": user["id"]})
                            st.success(f"Winners published for {category}.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not publish winners: {e}")
        st.divider()
        st.subheader("Current published winners")
        show_winners()

    elif role == "admin":
        st.markdown('<div class="panel"><h3>🛡️ Administration</h3><p>View account totals and manage competition access.</p></div>', unsafe_allow_html=True)
        stats = query_all("SELECT role, COUNT(*) AS total FROM users GROUP BY role ORDER BY role")
        cols = st.columns(4)
        totals = {x["role"]: x["total"] for x in stats}
        for col, r, label in zip(cols, ["student", "supervisor", "teacher", "admin"], ["Students", "Supervisors", "Teachers", "Admins"]):
            col.metric(label, totals.get(r, 0))
        st.subheader("Registered accounts")
        account_rows = query_all("""
          SELECT id, role, full_name, username, email, age_category, site, created_at
          FROM users ORDER BY role, full_name
        """)
        if account_rows:
            st.dataframe([dict(r) for r in account_rows], use_container_width=True, hide_index=True)
        st.subheader("Artwork and marking overview")
        st.metric("Artwork PDFs uploaded", query_one("SELECT COUNT(*) AS n FROM artworks")["n"])
        st.metric("Published winner places", query_one("SELECT COUNT(*) AS n FROM winners")["n"])
        st.subheader("Published winners")
        show_winners()
