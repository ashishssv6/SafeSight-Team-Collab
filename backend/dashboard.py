import os
import sys
import sqlite3
import hashlib
import pandas as pd
import streamlit as st
from PIL import Image
from datetime import datetime, date

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from pdf_report_generator import generate_pdf_dossier
except Exception:
    generate_pdf_dossier = None

st.set_page_config(
    page_title="SafeSight AI | Tactical SOC",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"  # Forces the sidebar to stay open
)

DB_PATH = "safesight.db"
SNAPSHOT_DIR = "alerts_snapshots"
VIDEO_DIR = "alerts_videos"
REPORTS_DIR = "reports"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# ------------------------------------------------------------------
# Advanced High-Contrast Cyber Defense Theme
# ------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');
    
    /* 1. HIDE ONLY DEPLOY & MENU BUTTONS (KEEP SIDEBAR TOGGLE VISIBLE) */
    .stDeployButton {
        display: none !important;
        visibility: hidden !important;
    }
    #MainMenu {
        visibility: hidden !important;
        display: none !important;
    }
    footer {
        visibility: hidden !important;
        display: none !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        color: #38BDF8 !important;
    }

    /* 2. ROOT THEME & FULL SCREEN UTILIZATION */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .stApp {
        background: #06080F;
        color: #E2E8F0;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 98% !important;
    }
    
    /* 3. SIDEBAR STYLING */
    section[data-testid="stSidebar"] {
        background-color: #0A0F1D !important;
        border-right: 1px solid rgba(56, 189, 248, 0.15) !important;
    }
    
    /* 4. SLEEK TOP COMMAND BAR */
    .soc-nav {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.45) 100%);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-radius: 12px;
        padding: 12px 20px;
        margin-bottom: 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        backdrop-filter: blur(12px);
    }
    .soc-brand {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .soc-title-text {
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        background: linear-gradient(90deg, #38BDF8, #818CF8, #C084FC);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .soc-subtitle-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* 5. LIVE PULSE BADGE */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 5px 12px;
        border-radius: 20px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        font-weight: 700;
        color: #34D399;
    }
    .pulse-dot {
        width: 7px;
        height: 7px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10B981;
        animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1.1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    
    /* 6. KPI METRICS CARDS */
    .kpi-box {
        background: #0B1120;
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 10px;
        padding: 12px 16px;
        position: relative;
        overflow: hidden;
    }
    .kpi-box::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 3px;
    }
    .kpi-cyan::after { background: #38BDF8; }
    .kpi-red::after { background: #EF4444; }
    .kpi-amber::after { background: #F59E0B; }
    .kpi-emerald::after { background: #10B981; }
    .kpi-purple::after { background: #A855F7; }
    
    .kpi-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        text-transform: uppercase;
        color: #64748B;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .kpi-num {
        font-size: 1.6rem;
        font-weight: 800;
        color: #F8FAFC;
        margin-top: 2px;
    }
    
    /* 7. SEVERITY STATUS BADGES */
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.68rem;
        font-weight: 700;
    }
    .badge-critical { background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-high { background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .badge-caution { background: rgba(6, 182, 212, 0.2); color: #38BDF8; border: 1px solid rgba(6, 182, 212, 0.4); }
    .badge-normal { background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4); }
</style>
""", unsafe_allow_html=True)

def fetch_security_logs():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                event_type TEXT NOT NULL,
                track_id INTEGER,
                threat_score INTEGER NOT NULL,
                threat_level TEXT NOT NULL,
                details TEXT,
                snapshot_path TEXT,
                video_path TEXT
            )
        """)
        conn.commit()
        cursor.execute("PRAGMA table_info(security_events)")
        cols = [col[1] for col in cursor.fetchall()]
        if "video_path" not in cols:
            cursor.execute("ALTER TABLE security_events ADD COLUMN video_path TEXT")
            conn.commit()
        df = pd.read_sql_query("SELECT * FROM security_events ORDER BY id DESC", conn)
        conn.close()
        if "video_path" not in df.columns:
            df["video_path"] = None
        return df
    except Exception:
        return pd.DataFrame()

def verify_user(username, password):
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    cursor.execute("SELECT username, role, full_name FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {"username": user[0], "role": user[1], "full_name": user[2]}
    return None

def add_new_user(username, password, role, full_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    try:
        cursor.execute("INSERT INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
                       (username, pwd_hash, role, full_name))
        conn.commit()
        return True, f"Account '{username}' created successfully!"
    except sqlite3.IntegrityError:
        return False, f"Username '{username}' already exists."
    finally:
        conn.close()

def delete_user(username):
    if username == "admin":
        return False, "Cannot delete master admin."
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True, f"User '{username}' removed."

def get_all_users():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT username, role, full_name, created_at FROM users", conn)
    conn.close()
    return df

# Authentication
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user"] = None

if not st.session_state["authenticated"]:
    st.markdown("<div style='margin-top:60px;'></div>", unsafe_allow_html=True)
    _, login_col, _ = st.columns([1, 1.2, 1])
    with login_col:
        st.markdown("""
            <div style="text-align:center; margin-bottom:20px;">
                <span style="font-size:3rem;">🛡️</span>
                <h2 style="color:#F8FAFC; margin:0; font-weight:800;">SafeSight SOC Portal</h2>
                <p style="color:#64748B; font-size:0.85rem;">Autonomous Edge AI Surveillance Operations</p>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            user_in = st.text_input("Security Identifier")
            pass_in = st.text_input("Access Key", type="password")
            if st.form_submit_button("Authenticate Access", use_container_width=True):
                u_info = verify_user(user_in.strip(), pass_in.strip())
                if u_info:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = u_info
                    st.rerun()
                else:
                    st.error("Authentication failed: Invalid credentials.")
    st.stop()

current_user = st.session_state["user"]
is_admin = current_user["role"] == "admin"

# Sidebar
with st.sidebar:
    st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
            <span style="font-size:1.8rem;">🛡️</span>
            <div>
                <h3 style="margin:0; font-size:1.05rem; color:#F8FAFC;">{current_user['full_name']}</h3>
                <span style="background:rgba(56,189,248,0.15); color:#38BDF8; border:1px solid rgba(56,189,248,0.3); padding:2px 8px; border-radius:4px; font-size:0.72rem; font-family:'JetBrains Mono';">{current_user['role'].upper()} CLEARANCE</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user"] = None
        st.rerun()

    st.divider()
    st.markdown("##### 📅 Timeline & Calendar Filter")
    filter_mode = st.radio("Timeline Scope:", ["Show All Records", "Filter by Specific Date"])
    
    selected_date = None
    if filter_mode == "Filter by Specific Date":
        selected_date = st.date_input("Select Incident Day:", value=datetime.now().date())

    st.markdown("##### 🎛️ Telemetry Filtering")
    severity_filter = st.multiselect(
        "Incident Severity",
        ["CRITICAL", "HIGH", "CAUTION", "NORMAL"],
        default=["CRITICAL", "HIGH", "CAUTION", "NORMAL"]
    )

    if is_admin:
        st.divider()
        st.markdown("##### 🔒 Master Maintenance")
        with st.expander("⚡ Purge Incident Logs"):
            confirm = st.text_input("Type 'CONFIRM'", type="password")
            if st.button("🚨 Purge Database", use_container_width=True) and confirm == "CONFIRM":
                conn = sqlite3.connect(DB_PATH)
                conn.cursor().execute("DELETE FROM security_events")
                conn.commit()
                conn.close()
                st.toast("Security logs purged by Administrator.", icon="🗑️")
                st.rerun()

@st.fragment(run_every="2s")
def render_soc_interface():
    df = fetch_security_logs()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.markdown(f"""
        <div class="soc-nav">
            <div class="soc-brand">
                <span style="font-size:1.6rem;">🛡️</span>
                <div>
                    <div class="soc-title-text">SAFESIGHT AI SURVEILLANCE MATRIX</div>
                    <div class="soc-subtitle-text">SOC NODE: ALPHA-1 | OPERATOR: {current_user['username'].upper()}</div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:14px;">
                <div class="status-pill">
                    <div class="pulse-dot"></div>
                    SENTRY ACTIVE
                </div>
                <div style="font-family:'JetBrains Mono'; font-size:0.75rem; color:#64748B;">🕒 {now_str}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if is_admin:
        tab_live, tab_export, tab_users = st.tabs([
            "🔴 Incident Forensic Studio",
            "📥 Audit Proofs & PDF Dossier",
            "⚙️ Admin Subsystems & Users"
        ])
    else:
        tab_live = st.container()

    # TAB 1: STUDIO
    with tab_live:
        if df.empty:
            st.markdown("""
                <div style="text-align:center; padding:60px 20px; background:#0B1120; border-radius:12px; border:1px dashed #1E293B; margin-top:10px;">
                    <span style="font-size:2.5rem;">📡</span>
                    <h4 style="margin-top:12px; color:#F8FAFC;">SURVEILLANCE SENSORS SCANNING</h4>
                    <p style="color:#64748B; font-size:0.85rem; font-family:'JetBrains Mono';">No security anomalies recorded yet.</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            df['date_only'] = pd.to_datetime(df['timestamp']).dt.date
            working_df = df[df['date_only'] == selected_date] if selected_date is not None else df
            filtered_df = working_df[working_df["threat_level"].isin(severity_filter)] if severity_filter else working_df

            k1, k2, k3, k4, k5 = st.columns(5)
            k1.markdown(f'<div class="kpi-box kpi-cyan"><div class="kpi-label">TOTAL LOGS</div><div class="kpi-num">{len(filtered_df)}</div></div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="kpi-box kpi-red"><div class="kpi-label">CRITICAL THREATS</div><div class="kpi-num" style="color:#F87171;">{len(filtered_df[filtered_df["threat_level"]=="CRITICAL"])}</div></div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="kpi-box kpi-amber"><div class="kpi-label">HIGH SEVERITY</div><div class="kpi-num" style="color:#FBBF24;">{len(filtered_df[filtered_df["threat_level"]=="HIGH"])}</div></div>', unsafe_allow_html=True)
            k4.markdown(f'<div class="kpi-box kpi-emerald"><div class="kpi-label">ZONE BREACHES</div><div class="kpi-num" style="color:#34D399;">{len(filtered_df[filtered_df["event_type"].str.contains("Intrusion", na=False)])}</div></div>', unsafe_allow_html=True)
            k5.markdown(f'<div class="kpi-box kpi-purple"><div class="kpi-label">TAMPER EVENTS</div><div class="kpi-num" style="color:#C084FC;">{len(filtered_df[filtered_df["event_type"].str.contains("Tampering", na=False)])}</div></div>', unsafe_allow_html=True)

            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

            if not filtered_df.empty:
                options = []
                opt_map = {}
                for idx, r in filtered_df.iterrows():
                    label = f"#{r['id']} | {r['timestamp']} | [{r['threat_level']}] {r['event_type']} (Score: {r['threat_score']})"
                    options.append(label)
                    opt_map[label] = r

                selected_opt = st.selectbox(
                    f"📌 Select Incident from History ({len(options)} total events):",
                    options,
                    index=0
                )
                active_record = opt_map[selected_opt]

                insp_l, insp_r = st.columns([1.3, 1])

                with insp_l:
                    st.markdown("##### 📹 5-Second Forensic Video Playback")
                    v_path = str(active_record["video_path"]) if pd.notna(active_record["video_path"]) else ""
                    if v_path and os.path.exists(v_path) and os.path.getsize(v_path) > 1000:
                        with open(v_path, 'rb') as vf:
                            video_bytes = vf.read()
                        st.video(video_bytes, format="video/mp4")
                        st.download_button(
                            label=f"⬇️ Download Event #{active_record['id']} MP4 Video Clip",
                            data=video_bytes,
                            file_name=os.path.basename(v_path),
                            mime="video/mp4",
                            use_container_width=True
                        )
                    else:
                        st.info("⚠️ Video buffer clip was not recorded for this event.")

                with insp_r:
                    st.markdown("##### 📸 Photographic Evidence Snapshot")
                    s_path = str(active_record["snapshot_path"]) if pd.notna(active_record["snapshot_path"]) else ""
                    if s_path and os.path.exists(s_path):
                        img = Image.open(s_path)
                        st.image(img, use_container_width=True)
                        with open(s_path, "rb") as sf:
                            st.download_button(
                                label=f"⬇️ Download Event #{active_record['id']} JPEG Snapshot",
                                data=sf.read(),
                                file_name=os.path.basename(s_path),
                                mime="image/jpeg",
                                use_container_width=True
                            )
                        st.markdown(f"""
                            <div style="margin-top:6px;">
                                <span class="badge badge-{active_record['threat_level'].lower()}">{active_record['threat_level']}</span>
                                <span style="font-family:'JetBrains Mono'; font-size:0.75rem; color:#94A3B8; margin-left:8px;">🕒 {active_record['timestamp']}</span>
                                <div style="font-size:0.8rem; color:#E2E8F0; margin-top:4px;"><b>Telemetry:</b> {active_record['details']}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.caption("No snapshot recorded for this entry.")
            else:
                st.info("No security incidents match the current timeline or severity filters.")

            st.divider()
            st.markdown(f"#### 📋 Complete Incident Audit Stream ({len(filtered_df)} Records)")
            cols_to_show = ["id", "timestamp", "threat_level", "threat_score", "event_type", "track_id", "details"]
            st.dataframe(
                filtered_df[cols_to_show].rename(
                    columns={
                        "id": "Log ID",
                        "timestamp": "Timestamp",
                        "threat_level": "Severity",
                        "threat_score": "Score",
                        "event_type": "Incident Type",
                        "track_id": "Target ID",
                        "details": "Telemetry Details"
                    }
                ),
                use_container_width=True,
                hide_index=True
            )

    # TAB 2: EXPORT
    if is_admin:
        with tab_export:
            st.markdown("#### 📥 Official Forensic Evidentiary Proofs")
            st.write("Generate and download legal proof dossiers containing cryptographic signatures, photo logs, and incident telemetry:")
            
            c_pdf, c_csv = st.columns(2)
            with c_pdf:
                st.markdown("##### 📄 Courtroom Forensic PDF Dossier")
                st.caption("Compiles recent security breach photos, timestamps, telemetry details, and a SHA-256 digital signature into a PDF.")
                if generate_pdf_dossier is not None:
                    if st.button("⚡ Generate Legal PDF Dossier", use_container_width=True):
                        pdf_file = generate_pdf_dossier()
                        if pdf_file and os.path.exists(pdf_file):
                            with open(pdf_file, "rb") as f:
                                st.download_button(
                                    label="⬇️ Click Here to Download Generated PDF Dossier",
                                    data=f.read(),
                                    file_name=os.path.basename(pdf_file),
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            st.success(f"Dossier ready: {os.path.basename(pdf_file)}")
                        else:
                            st.warning("No security incidents available to generate report.")
                else:
                    st.error("ReportLab library missing. Run: pip install reportlab")

            with c_csv:
                st.markdown("##### 📊 Raw Audit Evidence Ledger (CSV)")
                st.caption("Export all raw database records, object tracking IDs, normalized velocity records, and threat scores.")
                if not df.empty:
                    st.download_button(
                        label="⬇️ Download Complete Raw CSV Audit Logs",
                        data=df.to_csv(index=False).encode('utf-8'),
                        file_name=f"SafeSight_Full_Audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.info("No security logs available for export yet.")

    # TAB 3: USERS
    if is_admin:
        with tab_users:
            st.markdown("#### ⚙️ Edge AI Subsystem Configuration")
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, val TEXT NOT NULL)")
            cur.execute("SELECT val FROM system_config WHERE key = 'face_detection_enabled'")
            row = cur.fetchone()
            current_face_state = (row[0] == "1") if row else True
            conn.close()

            c_toggle1, c_toggle2 = st.columns([1.2, 2])
            with c_toggle1:
                toggle_val = st.toggle("Enable Facial Recognition Scanner", value=current_face_state)
                if toggle_val != current_face_state:
                    conn = sqlite3.connect(DB_PATH)
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO system_config (key, val) VALUES ('face_detection_enabled', ?)
                        ON CONFLICT(key) DO UPDATE SET val=excluded.val
                    """, ("1" if toggle_val else "0",))
                    conn.commit()
                    conn.close()
                    st.toast(f"Face Scanner {'ENABLED' if toggle_val else 'DISABLED'} by Admin", icon="⚙️")
                    st.rerun()

            with c_toggle2:
                if toggle_val:
                    st.success("🟢 Facial Recognition Active: Scans for VIP clearance and Blacklist targets.")
                else:
                    st.warning("🟡 Facial Recognition Disabled: Suppresses face boxes and optimizes FPS.")

            st.divider()
            st.markdown("#### 👥 Personnel Accounts")
            u1, u2 = st.columns([1.3, 1])
            with u1:
                st.write("##### Active Security Personnel")
                st.dataframe(get_all_users(), use_container_width=True, hide_index=True)
                st.write("##### 🗑️ Remove User")
                del_u = st.text_input("Username to remove")
                if st.button("Delete User", use_container_width=True) and del_u:
                    ok, msg = delete_user(del_u.strip())
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with u2:
                st.write("##### ➕ Provision New User")
                with st.form("new_user_form"):
                    nu = st.text_input("Username *")
                    nn = st.text_input("Full Name *")
                    np = st.text_input("Password *", type="password")
                    nr = st.selectbox("Role", ["operator", "admin"])
                    if st.form_submit_button("Create Account", use_container_width=True):
                        if nu and np and nn:
                            ok, msg = add_new_user(nu.strip(), np.strip(), nr, nn.strip())
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

render_soc_interface()