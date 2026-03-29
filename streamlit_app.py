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

# --- 3. DATABASE CONNECTION ---
def get_connection():
    # Ensure your secrets.toml has: connection_string = "postgresql://..."
    return psycopg2.connect(st.secrets["connection_string"])

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Postgres table creation
    cur.execute('''CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        "Student Name" TEXT, "Matrix Number" TEXT, Session TEXT, 
        Faculty TEXT, Campus TEXT, Programme TEXT, 
        Global REAL, Resilient REAL, Innovative REAL, Trustworthy REAL, Talent REAL)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'lecturer')''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY, title TEXT, description TEXT, image_data TEXT)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS ge_data (
        year INTEGER UNIQUE, percentage REAL)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS kpi_data (
        id SERIAL PRIMARY KEY, jabatan TEXT, kpi_desc TEXT)''')
    
    # Create Default Admin
    cur.execute('SELECT COUNT(*) FROM users')
    if cur.fetchone()[0] == 0:
        admin_pass = hashlib.sha256(str.encode('uthm123')).hexdigest()
        cur.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', ('admin', admin_pass, 'admin'))
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- 4. DATA LOADING ---
def load_data():
    conn = get_connection()
    # We use 'id' now because we created a Serial Primary Key above
    df = pd.read_sql_query('SELECT * FROM students ORDER BY id DESC', conn)
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

# --- 6. MAIN DASHBOARD ---
def main_dashboard():
    l_col, r_col = st.columns([5, 1])
    l_col.title("🎓 FTK GRITT Dashboard (Supabase)")
    
    if r_col.button("Logout"):
        st.session_state.update(logged_in=False, username="", role="lecturer")
        st.rerun()
    
    role_name = "🛡️ Admin" if st.session_state['role'] == 'admin' else "👨‍🏫 Lecturer"
    st.markdown(f"*User: **{st.session_state['username']}** ({role_name})*")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Charts", "📝 Data Entry", "🏛️ Faculty Info", "🎯 KPI"])
    
    with tab1:
        st.subheader("Student Performance")
        df = load_data()
        if not df.empty:
            df['Display'] = df['Student Name'] + " (" + df['Matrix Number'] + ")"
            sm = st.text_input("🔍 Search Matrix Number:")
            
            selected_student = None
            if sm:
                match = df[df['Matrix Number'].str.upper() == sm.upper().strip()]
                if not match.empty: selected_student = match.iloc[0]
                else: st.error("No student found.")
            else:
                sel_name = st.selectbox("Select Student:", df['Display'])
                selected_student = df[df['Display'] == sel_name].iloc[0]
            
            if selected_student is not None:
                cat = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
                scr = [selected_student[c] for c in cat]
                fig_df = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat + [cat[0]]))
                fig = px.line_polar(fig_df, r='r', theta='theta', line_close=True)
                fig.update_traces(fill='toself')
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data in cloud database yet.")

    with tab2:
        st.subheader("Add Data to Supabase")
        with st.form("manual"):
            c1, c2, c3 = st.columns(3)
            n = c1.text_input("Name"); m = c2.text_input("Matrix"); s = c3.selectbox("Session", ["2024/2025", "2025/2026"])
            p = st.text_input("Programme")
            sc = st.columns(5)
            g=sc[0].number_input("Global",0,100,50); r=sc[1].number_input("Resilient",0,100,50); i=sc[2].number_input("Innov",0,100,50); t1=sc[3].number_input("Trust",0,100,50); t2=sc[4].number_input("Talent",0,100,50)
            
            if st.form_submit_button("Save to Cloud"):
                conn = get_connection(); cur = conn.cursor()
                # Specify columns for Postgres insert
                cur.execute('''INSERT INTO students 
                    ("Student Name", "Matrix Number", Session, Faculty, Campus, Programme, Global, Resilient, Innovative, Trustworthy, Talent) 
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', 
                    (n, m, s, 'FTK', 'Pagoh', p, g, r, i, t1, t2))
                conn.commit(); conn.close(); st.success("Stored Permanently!"); st.rerun()

        if st.session_state['role'] == 'admin':
            st.divider()
            st.markdown("### 🗑️ Admin: Delete Records")
            df_del = load_data()
            if not df_del.empty:
                st.dataframe(df_del[['id', 'Student Name', 'Matrix Number']], use_container_width=True)
                target_id = st.number_input("Enter ID to delete:", min_value=1, step=1)
                if st.button("Delete from Supabase", type="primary"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute('DELETE FROM students WHERE id = %s', (target_id,))
                    conn.commit(); conn.close(); st.success("Deleted!"); st.rerun()

    # (Tabs 3 and 4 remain logically the same but ensure they use get_connection)
    with tab3:
        st.write("Faculty Info Section") # Add your GE logic here
    
    with tab4:
        st.write("KPI Section") # Add your KPI logic here

# --- LOGIN SCREEN ---
def login_screen():
    st.title("🔒 FTK Staff Portal (Cloud)")
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