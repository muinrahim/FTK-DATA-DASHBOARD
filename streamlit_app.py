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
    return psycopg2.connect(st.secrets["connection_string"], connect_timeout=10)

def init_db():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute('CREATE TABLE IF NOT EXISTS students (id SERIAL PRIMARY KEY, "Student Name" TEXT, "Matrix Number" TEXT, Session TEXT, Faculty TEXT, Campus TEXT, Programme TEXT, Global REAL, Resilient REAL, Innovative REAL, Trustworthy REAL, Talent REAL)')
        cur.execute('CREATE TABLE IF NOT EXISTS users (username TEXT UNIQUE, password TEXT, role TEXT DEFAULT \'lecturer\')')
        cur.execute('CREATE TABLE IF NOT EXISTS events (id SERIAL PRIMARY KEY, title TEXT, description TEXT, image_data TEXT)')
        cur.execute('CREATE TABLE IF NOT EXISTS ge_data (year INTEGER UNIQUE, percentage REAL)')
        cur.execute('CREATE TABLE IF NOT EXISTS kpi_data (id SERIAL PRIMARY KEY, jabatan TEXT, kpi_desc TEXT)')
        
        cur.execute('SELECT COUNT(*) FROM users')
        if cur.fetchone()[0] == 0:
            admin_pass = hashlib.sha256(str.encode('uthm123')).hexdigest()
            cur.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', ('admin', admin_pass, 'admin'))
        
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        st.error(f"DB Error: {e}")

init_db()

# --- 4. DATA LOADING ---
def load_query(query, params=None):
    try:
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except: return pd.DataFrame()

# --- 5. UTILITIES ---
def check_password(password, hashed_text):
    return hashlib.sha256(str.encode(password)).hexdigest() == hashed_text

def create_radar_chart(row, title):
    cat = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
    scr = [row[c] for c in cat]
    df_fig = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat + [cat[0]]))
    fig = px.line_polar(df_fig, r='r', theta='theta', line_close=True, title=title)
    fig.update_traces(fill='toself', fillcolor='rgba(0, 114, 178, 0.4)')
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
    return fig

# --- 6. MAIN DASHBOARD ---
def main_dashboard():
    l, r = st.columns([5, 1])
    l.title("🎓 FTK GRITT Dashboard (Supabase)")
    if r.button("Logout"):
        st.session_state.update(logged_in=False)
        st.rerun()
    
    is_admin = (st.session_state['role'] == 'admin')
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Charts", "📝 Data Entry", "🏛️ Faculty Info", "🎯 KPI"])
    
    with tab1:
        st.subheader("Student Performance")
        df = load_query('SELECT * FROM students')
        if not df.empty:
            df['Display'] = df['Student Name'] + " (" + df['Matrix Number'] + ")"
            sm = st.text_input("🔍 Search Matrix Number:")
            if sm:
                match = df[df['Matrix Number'].str.upper() == sm.upper().strip()]
                if not match.empty: st.plotly_chart(create_radar_chart(match.iloc[0], match.iloc[0]['Display']), use_container_width=True)
                else: st.error("Not found.")
            else:
                sel = st.selectbox("Select Student:", df['Display'])
                st.plotly_chart(create_radar_chart(df[df['Display'] == sel].iloc[0], sel), use_container_width=True)
        else: st.info("Database is empty. Add a student in 'Data Entry' first!")

    with tab2:
        # --- ADDING DATA ---
        st.header("📥 Data Entry")
        col_st, col_ev = st.columns(2)
        
        with col_st:
            with st.form("add_student"):
                st.subheader("Add Student")
                n, m, s = st.text_input("Name"), st.text_input("Matrix"), st.selectbox("Session", ["2024/2025", "2025/2026"])
                p = st.text_input("Programme")
                sc = st.columns(5)
                g=sc[0].number_input("G",0,100,50); res=sc[1].number_input("R",0,100,50); i=sc[2].number_input("I",0,100,50); t1=sc[3].number_input("T",0,100,50); t2=sc[4].number_input("Tal",0,100,50)
                if st.form_submit_button("Save Student"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute('INSERT INTO students ("Student Name", "Matrix Number", Session, Faculty, Campus, Programme, Global, Resilient, Innovative, Trustworthy, Talent) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', (n,m,s,'FTK','Pagoh',p,g,res,i,t1,t2))
                    conn.commit(); conn.close(); st.success("Saved!"); st.rerun()

        with col_ev:
            if is_admin:
                with st.form("add_event"):
                    st.subheader("Add Event")
                    et = st.text_input("Title"); ed = st.text_area("Desc")
                    ef = st.file_uploader("Image", type=['png', 'jpg', 'jpeg'])
                    if st.form_submit_button("Post Event"):
                        img_str = base64.b64encode(ef.read()).decode() if ef else ""
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('INSERT INTO events (title, description, image_data) VALUES (%s,%s,%s)', (et, ed, img_str))
                        conn.commit(); conn.close(); st.success("Posted!"); st.rerun()

        if is_admin:
            st.divider()
            st.header("🗑️ Admin Deletion Center")
            
            # --- DELETE STUDENTS ---
            with st.expander("Delete Students"):
                df_del = load_query('SELECT id, "Student Name", "Matrix Number" FROM students')
                if not df_del.empty:
                    st.dataframe(df_del, use_container_width=True)
                    sid = st.number_input("Enter Student ID to Delete", step=1, min_value=0)
                    if st.button("Confirm Delete Student", type="primary"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('DELETE FROM students WHERE id = %s', (sid,))
                        conn.commit(); conn.close(); st.rerun()

            # --- DELETE EVENTS ---
            with st.expander("Delete Events"):
                ev_del = load_query('SELECT id, title FROM events')
                if not ev_del.empty:
                    st.table(ev_del)
                    eid = st.number_input("Enter Event ID to Delete", step=1, min_value=0)
                    if st.button("Confirm Delete Event", type="primary"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('DELETE FROM events WHERE id = %s', (eid,))
                        conn.commit(); conn.close(); st.rerun()
            
            # --- GE & KPI MANAGEMENT ---
            c_ge, c_kp = st.columns(2)
            with c_ge:
                with st.form("admin_ge"):
                    st.subheader("Update GE %")
                    gy, gp = st.number_input("Year", 2024), st.number_input("Value", 0.0, 100.0, 95.0)
                    if st.form_submit_button("Save GE"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('INSERT INTO ge_data (year, percentage) VALUES (%s,%s) ON CONFLICT (year) DO UPDATE SET percentage = EXCLUDED.percentage', (gy, gp))
                        conn.commit(); conn.close(); st.rerun()
            
            with c_kp:
                jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
                with st.form("admin_kpi"):
                    st.subheader("Add KPI")
                    jb, kd = st.selectbox("Dept", jabs), st.text_area("Target")
                    if st.form_submit_button("Add KPI"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (%s,%s)', (jb, kd))
                        conn.commit(); conn.close(); st.rerun()

    with tab3:
        st.subheader("Faculty Insights")
        ge_df = load_query('SELECT * FROM ge_data ORDER BY year ASC')
        if not ge_df.empty: st.plotly_chart(px.line(ge_df, x='year', y='percentage', markers=True), use_container_width=True)
        
        st.divider()
        ev_df = load_query('SELECT * FROM events ORDER BY id DESC')
        for _, ev in ev_df.iterrows():
            st.markdown(f"### {ev['title']}")
            if ev['image_data']: st.image(base64.b64decode(ev['image_data']), use_container_width=True)
            st.write(ev['description']); st.divider()

    with tab4:
        st.subheader("🎯 Strategic KPI")
        kpi_df = load_query('SELECT * FROM kpi_data')
        jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
        for jb in jabs:
            st.markdown(f"#### {jb}")
            for _, r in kpi_df[kpi_df['jabatan'] == jb].iterrows(): st.write(f"• {r['kpi_desc']}")

def login_screen():
    st.title("🔒 FTK Staff Portal")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_connection(); cur = conn.cursor()
        cur.execute('SELECT password, role FROM users WHERE username = %s', (u,))
        res = cur.fetchone(); conn.close()
        if res and check_password(p, res[0]):
            st.session_state.update(logged_in=True, username=u, role=res[1]); st.rerun()
        else: st.error("Access Denied")

if not st.session_state['logged_in']: login_screen()
else: main_dashboard()