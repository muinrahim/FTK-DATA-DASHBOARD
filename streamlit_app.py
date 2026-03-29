import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg2 
from psycopg2.extras import RealDictCursor
import io
import hashlib
import base64

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="UTHM FTK Dashboard", page_icon="🎓", layout="wide")

# --- 2. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'role' not in st.session_state: st.session_state['role'] = "lecturer"

# --- 3. DATABASE CONNECTION (SUPABASE) ---
def get_connection():
    # Pulls from .streamlit/secrets.toml locally or Cloud Secrets online
    conn_str = st.secrets["connection_string"]
    return psycopg2.connect(conn_str)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Create tables if they don't exist
    cur.execute('''CREATE TABLE IF NOT EXISTS students (
        "Student Name" TEXT, "Matrix Number" TEXT, Session TEXT, 
        Faculty TEXT, Campus TEXT, Programme TEXT, 
        Global REAL, Resilient REAL, Innovative REAL, Trustworthy REAL, Talent REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'lecturer')''')
    cur.execute('''CREATE TABLE IF NOT EXISTS events (id SERIAL PRIMARY KEY, title TEXT, description TEXT, image_data TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS ge_data (year INTEGER UNIQUE, percentage REAL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS kpi_data (id SERIAL PRIMARY KEY, jabatan TEXT, kpi_desc TEXT)''')
    
    # Check for Admin
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        admin_pass = hashlib.sha256(str.encode('uthm123')).hexdigest()
        cur.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', ('admin', admin_pass, 'admin'))
    
    conn.commit()
    cur.close()
    conn.close()

# Run init immediately
init_db()

# --- 4. DATA LOADING FUNCTIONS ---
def load_data():
    conn = get_connection()
    # Postgres uses 'ctid' as a unique row identifier
    df = pd.read_sql_query('SELECT ctid as id, * FROM students', conn)
    conn.close()
    return df

def get_events():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM events ORDER BY id DESC", conn)
    conn.close()
    return df

def get_ge_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM ge_data ORDER BY year ASC", conn)
    conn.close()
    return df

def get_kpi_data():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM kpi_data", conn)
    conn.close()
    return df

# --- 5. UTILITIES ---
def check_password(password, hashed_text):
    return hashlib.sha256(str.encode(password)).hexdigest() == hashed_text

@st.cache_data
def generate_template_excel():
    template_df = pd.DataFrame(columns=['Student Name', 'Matrix Number', 'Session', 'Faculty', 'Campus', 'Programme', 'Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent'])
    template_df.loc[0] = ['Ali Bin Abu', 'AA240001', '2024/2025', 'FTK', 'Pagoh Campus', 'KNT', 80, 75, 90, 85, 80]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False)
    return output.getvalue()

def create_radar_chart(row, title):
    cat = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
    # Use standard indexing for Series/DataFrame rows
    scr = [row['Global'], row['Resilient'], row['Innovative'], row['Trustworthy'], row['Talent']]
    df = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat + [cat[0]]))
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, title=title)
    fig.update_traces(fill='toself', fillcolor='rgba(0, 114, 178, 0.4)', line_color='rgb(0, 114, 178)', line_width=3)
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# --- 6. MAIN DASHBOARD ---
def main_dashboard():
    l_col, r_col = st.columns([5, 1])
    l_col.title("🎓 FTK GRITT Dashboard (Supabase Cloud)")
    r_col.button("Logout", on_click=lambda: st.session_state.update(logged_in=False))
    
    role_name = "🛡️ Admin" if st.session_state['role'] == 'admin' else "👨‍🏫 Lecturer"
    st.markdown(f"*User: **{st.session_state['username']}** ({role_name})*")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Charts", "📝 Data Entry", "🏛️ Faculty Info", "🎯 KPI"])
    
    with tab1:
        st.subheader("Student Performance")
        df = load_data()
        if not df.empty:
            df['Display'] = df['Student Name'] + " (" + df['Matrix Number'] + ")"
            sm = st.text_input("🔍 Search Matrix Number:")
            if sm:
                match = df[df['Matrix Number'].str.upper() == sm.upper().strip()]
                if not match.empty:
                    st.plotly_chart(create_radar_chart(match.iloc[0], f"Profile: {match.iloc[0]['Display']}"), use_container_width=True)
                else: st.error("No student found.")
            else:
                sel = st.selectbox("Select Student:", df['Display'])
                st.plotly_chart(create_radar_chart(df[df['Display'] == sel].iloc[0], sel), use_container_width=True)
        else:
            st.info("No data in cloud database yet.")

    with tab2:
        st.subheader("Add Data to Cloud")
        with st.form("manual"):
            c1, c2, c3 = st.columns(3)
            n = c1.text_input("Name"); m = c2.text_input("Matrix"); s = c3.selectbox("Session", ["2024/2025", "2025/2026"])
            p = st.text_input("Programme (e.g. KNT)")
            sc = st.columns(5)
            g=sc[0].number_input("Global",0,100,50); r=sc[1].number_input("Resilient",0,100,50); i=sc[2].number_input("Innov",0,100,50); t1=sc[3].number_input("Trust",0,100,50); t2=sc[4].number_input("Talent",0,100,50)
            if st.form_submit_button("Save to Supabase"):
                conn = get_connection(); cur = conn.cursor()
                cur.execute('INSERT INTO students VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (n,m,s,'FTK','Pagoh',p,g,r,i,t1,t2))
                conn.commit(); conn.close(); st.success("Stored Permanently!"); st.rerun()

        if st.session_state['role'] == 'admin':
            st.divider()
            st.markdown("### 🗑️ Admin: Cloud Deletion")
            df_manage = load_data()
            if not df_manage.empty:
                search_del = st.text_input("Search Name/Matrix to Delete:")
                if search_del:
                    df_manage = df_manage[df_manage['Student Name'].str.contains(search_del, case=False)]
                st.dataframe(df_manage[['id', 'Student Name', 'Matrix Number']], use_container_width=True)
                target_id = st.text_input("Enter ID (from left column) to delete:")
                if st.button("Delete from Cloud"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute('DELETE FROM students WHERE ctid = %s', (target_id,))
                    conn.commit(); conn.close(); st.success("Deleted!"); st.rerun()

    with tab3:
        ca, cb = st.columns([1, 2])
        with ca:
            g_df = get_ge_data()
            if not g_df.empty:
                st.metric("Latest GE %", f"{g_df.iloc[-1]['percentage']}%")
                st.plotly_chart(px.line(g_df, x='year', y='percentage', markers=True), use_container_width=True)
        with cb:
            evs = get_events()
            for _, ev in evs.iterrows():
                st.markdown(f"#### {ev['title']}")
                if ev['image_data']: st.image(base64.b64decode(ev['image_data']), use_container_width=True)
                st.divider()

    with tab4:
        st.subheader("🎯 KPI Jabatan")
        k_df = get_kpi_data()
        jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
        if st.session_state['role'] == 'admin':
            with st.form("kpi_add"):
                j = st.selectbox("Jabatan", jabs); d = st.text_area("Target")
                if st.form_submit_button("Add KPI"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (%s,%s)', (j, d))
                    conn.commit(); conn.close(); st.rerun()
        for jb in jabs:
            st.markdown(f"### {jb}")
            for _, r in k_df[k_df['jabatan'] == jb].iterrows():
                st.write(f"• {r['kpi_desc']}")

# --- 7. LOGIN SCREEN ---
def login_screen():
    st.title("🔒 FTK Staff Portal (Supabase Cloud)")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_connection(); cur = conn.cursor()
        cur.execute('SELECT password, role FROM users WHERE username = %s', (u,))
        res = cur.fetchone()
        conn.close()
        if res and check_password(p, res[0]):
            st.session_state.update(logged_in=True, username=u, role=res[1])
            st.rerun()
        else: st.error("Login failed.")

if not st.session_state['logged_in']:
    login_screen()
else:
    main_dashboard()