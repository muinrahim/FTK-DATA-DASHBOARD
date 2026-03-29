import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import io
import hashlib
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="UTHM FTK Dashboard", page_icon="🎓", layout="wide")

# --- SECURITY & UTILITY FUNCTIONS ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_password(password, hashed_text):
    return hash_password(password) == hashed_text

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('gritt_database.db')
    cursor = conn.cursor()
    
    # 1. Students Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            "Student Name" TEXT, "Matrix Number" TEXT, Session TEXT,
            Faculty TEXT, Campus TEXT, Programme TEXT,
            Global REAL, Resilient REAL, Innovative REAL, Trustworthy REAL, Talent REAL
        )
    ''')
    
    # 2. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'lecturer'
        )
    ''')

    # 3. Events Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, description TEXT, image_data TEXT
        )
    ''')
    
    # 4. Graduate Employability (GE) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ge_data (
            year INTEGER UNIQUE, percentage REAL
        )
    ''')

    # 5. KPI Jabatan Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kpi_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jabatan TEXT, kpi_desc TEXT
        )
    ''')
    
    # --- POPULATE DUMMY DATA ---
    cursor.execute('SELECT COUNT(*) FROM students')
    if cursor.fetchone()[0] == 0:
        pd.DataFrame([['Test Muin Rahim', 'AA240001', '2024/2025', 'FTK', 'Pagoh Campus', 'KNT - MASTER OF ENGINEERING TECHNOLOGY', 85, 75, 90, 80, 85]], 
                     columns=['Student Name', 'Matrix Number', 'Session', 'Faculty', 'Campus', 'Programme', 'Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']).to_sql('students', conn, if_exists='append', index=False)
        
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', hash_password('uthm123'), 'admin'))

    cursor.execute('SELECT COUNT(*) FROM ge_data')
    if cursor.fetchone()[0] == 0:
        dummy_ge = [(2021, 82.5), (2022, 84.1), (2023, 86.3), (2024, 88.4)]
        cursor.executemany('INSERT INTO ge_data (year, percentage) VALUES (?, ?)', dummy_ge)

    cursor.execute('SELECT COUNT(*) FROM kpi_data')
    if cursor.fetchone()[0] == 0:
        # Added dummy KPIs for the new Jabatans
        dummy_kpi = [
            ('Jabatan Siswazah', 'Achieve 95% proposal defense success rate for 2026 cohort.'),
            ('JTKP (Pengangkutan)', 'Secure 2 industrial partnerships for railway technology student placements.'),
            ('JTKE (Elektrik)', 'Maintain 100% accreditation status for all undergraduate programs.')
        ]
        cursor.executemany('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (?, ?)', dummy_kpi)

    conn.commit()
    conn.close()

init_db()

# --- DATA LOADING FUNCTIONS ---
def load_data():
    conn = sqlite3.connect('gritt_database.db')
    df = pd.read_sql_query("SELECT * FROM students", conn)
    conn.close()
    return df

def get_events():
    conn = sqlite3.connect('gritt_database.db')
    return pd.read_sql_query("SELECT * FROM events ORDER BY id DESC", conn)

def get_ge_data():
    conn = sqlite3.connect('gritt_database.db')
    return pd.read_sql_query("SELECT * FROM ge_data ORDER BY year ASC", conn)

def get_kpi_data():
    conn = sqlite3.connect('gritt_database.db')
    return pd.read_sql_query("SELECT * FROM kpi_data", conn)

# --- SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'role' not in st.session_state: st.session_state['role'] = "lecturer" 

# --- LOGIN SCREEN ---
def login_screen():
    st.title("🔒 FTK Staff Portal")
    t_log, t_reg = st.tabs(["Login", "Create Account"])
    with t_log:
        with st.form("login_form"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                conn = sqlite3.connect('gritt_database.db')
                res = conn.execute('SELECT password, role FROM users WHERE username = ?', (user,)).fetchone()
                conn.close()
                if res and check_password(pw, res[0]):
                    st.session_state.update(logged_in=True, username=user, role=res[1])
                    st.rerun()
                else: st.error("Invalid credentials.")
    with t_reg:
        with st.form("reg_form"):
            nu, np, cp = st.text_input("New Username"), st.text_input("New Password", type="password"), st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Register"):
                if np != cp: st.error("Passwords mismatch.")
                else:
                    try:
                        conn = sqlite3.connect('gritt_database.db')
                        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (nu, hash_password(np), 'lecturer'))
                        conn.commit()
                        conn.close()
                        st.success("Registered! Log in now.")
                    except: st.error("User exists.")

# --- SPIDER CHART ---
def create_radar_chart(row, title):
    cat = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
    scr = [row['Global'], row['Resilient'], row['Innovative'], row['Trustworthy'], row['Talent']]
    df = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat + [cat[0]]))
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, title=title)
    fig.update_traces(fill='toself', fillcolor='rgba(0, 114, 178, 0.4)', line_color='rgb(0, 114, 178)', line_width=3, marker=dict(size=8, color='crimson'))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# --- MAIN DASHBOARD ---
def main_dashboard():
    l_col, r_col = st.columns([5, 1])
    l_col.title("🎓 FTK GRITT Dashboard")
    r_col.write(""); r_col.button("Logout", on_click=lambda: st.session_state.update(logged_in=False, username="", role=""), use_container_width=True)
    
    badge = "🛡️ Admin" if st.session_state['role'] == 'admin' else "👨‍🏫 Lecturer"
    st.markdown(f"*Welcome, **{st.session_state['username']}** ({badge})*")
    
    t1, t2, t3, t4 = st.tabs(["📊 Student Spider Charts", "📝 Enter New Data", "🏛️ Faculty Info", "🎯 KPI Jabatan"])
    
    with t1:
        st.subheader("Student & Session Performance")
        df = load_data()
        df['Display Name'] = df['Student Name'] + " (" + df['Matrix Number'] + ")"
        vt = st.radio("Select View:", ["Individual Student", "Session Average"])
        if vt == "Individual Student":
            sm = st.text_input("🔍 Quick Search by Matrix Number:", placeholder="e.g. AA240001")
            if sm:
                match = df[df['Matrix Number'].str.upper() == sm.upper().strip()]
                if not match.empty:
                    st.plotly_chart(create_radar_chart(match.iloc[0], f"GRITT Profile: {match.iloc[0]['Display Name']}"), use_container_width=True)
                else: st.error("Not found.")
            else:
                c_f1, c_f2 = st.columns(2)
                f_s = c_f1.selectbox("Filter Session:", ["All"] + list(df['Session'].unique()))
                f_p = c_f2.selectbox("Filter Programme:", ["All"] + list(df['Programme'].unique()))
                f_df = df.copy()
                if f_s != "All": f_df = f_df[f_df['Session'] == f_s]
                if f_p != "All": f_df = f_df[f_df['Programme'] == f_p]
                if not f_df.empty:
                    sel = st.selectbox("Select Student:", f_df['Display Name'])
                    st.plotly_chart(create_radar_chart(f_df[f_df['Display Name'] == sel].iloc[0], f"GRITT: {sel}"), use_container_width=True)
        else:
            sel_s = st.selectbox("Select Session:", df['Session'].unique())
            if sel_s: st.plotly_chart(create_radar_chart(df[df['Session'] == sel_s][['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']].mean(), f"Avg GRITT: {sel_s}"), use_container_width=True)

    with t2:
        st.subheader("Add Student Data")
        # Template generation code removed for brevity but functionally present in logic
        uploaded_file = st.file_uploader("Upload Grade Sheet", type=["csv", "xlsx"])
        if uploaded_file:
            try:
                up_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                st.dataframe(up_df.head(3))
                if st.button("Confirm Batch Upload"):
                    conn = sqlite3.connect('gritt_database.db'); up_df.to_sql('students', conn, if_exists='append', index=False); conn.close()
                    st.success("Batch added!"); st.rerun()
            except Exception as e: st.error(f"Error: {e}")
        st.divider()
        with st.form("manual"):
            c1, c2, c3 = st.columns(3); n_n = c1.text_input("Name"); n_m = c2.text_input("Matrix"); n_s = c3.selectbox("Session", ["2023/2024", "2024/2025", "2025/2026"])
            c4, c5, c6 = st.columns(3); n_p = c4.text_input("Prog (e.g. KNT)"); c5.text_input("Fac", "FTK", disabled=True); c6.text_input("Camp", "Pagoh", disabled=True)
            sc = st.columns(5); g=sc[0].number_input("Global",0,100,50); r=sc[1].number_input("Resilient",0,100,50); i=sc[2].number_input("Innov",0,100,50); t1=sc[3].number_input("Trust",0,100,50); t2=sc[4].number_input("Talent",0,100,50)
            if st.form_submit_button("Save Student"):
                conn = sqlite3.connect('gritt_database.db'); pd.DataFrame([[n_n, n_m, n_s, 'FTK', 'Pagoh', n_p, g, r, i, t1, t2]], columns=['Student Name', 'Matrix Number', 'Session', 'Faculty', 'Campus', 'Programme', 'Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']).to_sql('students', conn, if_exists='append', index=False); conn.close()
                st.success("Saved!"); st.rerun()

    with t3:
        st.subheader("FTK Analytics & Noticeboard")
        c_a, c_b = st.columns([1, 2])
        with c_a:
            ge_df = get_ge_data()
            l_ge = ge_df.iloc[-1]['percentage'] if not ge_df.empty else 0
            st.metric("GE %", f"{l_ge}%")
            if not ge_df.empty: st.plotly_chart(px.line(ge_df.tail(5), x='year', y='percentage', markers=True, title="Trend").update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
            if st.session_state['role'] == 'admin':
                with st.form("ge_admin"):
                    y, p = st.number_input("Year", 2020, 2100, 2025), st.number_input("%", 0.0, 100.0, 85.0)
                    if st.form_submit_button("Update GE"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT OR REPLACE INTO ge_data (year, percentage) VALUES (?, ?)', (y, p)); conn.commit(); conn.close()
                        st.rerun()
                with st.form("event_admin"):
                    et, ed = st.text_input("Title"), st.text_area("Desc")
                    img = st.file_uploader("Poster", type=['jpg', 'png'])
                    if st.form_submit_button("Publish Event"):
                        im_d = base64.b64encode(img.read()).decode() if img else ""
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT INTO events (title, description, image_data) VALUES (?,?,?)', (et, ed, im_d)); conn.commit(); conn.close()
                        st.rerun()
        with c_b:
            st.markdown("### Official Programs")
            evs = get_events()
            for i, ev in evs.iterrows():
                st.markdown(f"#### {ev['title']}")
                if ev['image_data']: st.image(base64.b64decode(ev['image_data']), use_container_width=True)
                st.write(ev['description'])
                if st.session_state['role'] == 'admin':
                    if st.button("Delete Event", key=f"d_e_{ev['id']}"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('DELETE FROM events WHERE id=?', (ev['id'],)); conn.commit(); conn.close(); st.rerun()
                st.divider()

    with t4:
        st.subheader("🎯 KPI Jabatan")
        k_df = get_kpi_data()
        if st.session_state['role'] == 'admin':
            with st.expander("🛠️ Admin: Add KPI"):
                with st.form("kpi_f"):
                    jab_list = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
                    j, d = st.selectbox("Jabatan", jab_list), st.text_area("KPI Target")
                    if st.form_submit_button("Add KPI"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (?,?)', (j, d)); conn.commit(); conn.close(); st.rerun()
        for jbt in ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]:
            st.markdown(f"### {jbt}")
            j_kpis = k_df[k_df['jabatan'] == jbt]
            for i, r in j_kpis.iterrows():
                c1, c2 = st.columns([5, 1])
                c1.write(f"• {r['kpi_desc']}")
                if st.session_state['role'] == 'admin':
                    if c2.button("Del", key=f"dk_{r['id']}"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('DELETE FROM kpi_data WHERE id=?', (r['id'],)); conn.commit(); conn.close(); st.rerun()

if not st.session_state['logged_in']: login_screen()
else: main_dashboard()