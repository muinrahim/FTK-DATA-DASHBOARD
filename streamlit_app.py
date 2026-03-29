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
    cursor.execute('''CREATE TABLE IF NOT EXISTS students ("Student Name" TEXT, "Matrix Number" TEXT, Session TEXT, Faculty TEXT, Campus TEXT, Programme TEXT, Global REAL, Resilient REAL, Innovative REAL, Trustworthy REAL, Talent REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'lecturer')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, image_data TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS ge_data (year INTEGER UNIQUE, percentage REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS kpi_data (id INTEGER PRIMARY KEY AUTOINCREMENT, jabatan TEXT, kpi_desc TEXT)''')
    
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', hash_password('uthm123'), 'admin'))
    if conn.execute('SELECT COUNT(*) FROM ge_data').fetchone()[0] == 0:
        conn.executemany('INSERT INTO ge_data (year, percentage) VALUES (?, ?)', [(2021, 82.5), (2022, 84.1), (2023, 86.3), (2024, 88.4)])
    
    conn.commit()
    conn.close()

init_db()

# --- DATA LOADING ---
def load_data():
    conn = sqlite3.connect('gritt_database.db')
    df = pd.read_sql_query("SELECT rowid, * FROM students", conn)
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

# --- EXCEL TEMPLATE GENERATOR ---
@st.cache_data
def generate_template_excel():
    template_df = pd.DataFrame(columns=['Student Name', 'Matrix Number', 'Session', 'Faculty', 'Campus', 'Programme', 'Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent'])
    template_df.loc[0] = ['Ali Bin Abu', 'AA240001', '2024/2025', 'FTK', 'Pagoh Campus', 'KNT', 80, 75, 90, 85, 80]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# --- LOGIN SCREEN ---
def login_screen():
    st.title("🔒 FTK Staff Portal")
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        with st.form("login_form_key"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                conn = sqlite3.connect('gritt_database.db')
                res = conn.execute('SELECT password, role FROM users WHERE username=?', (u,)).fetchone()
                conn.close()
                if res and check_password(p, res[0]):
                    st.session_state.update(logged_in=True, username=u, role=res[1])
                    st.rerun()
                else: st.error("Invalid credentials.")
    with t2:
        with st.form("reg_form_key"):
            nu, np, cp = st.text_input("New User"), st.text_input("New Pass", type="password"), st.text_input("Confirm", type="password")
            if st.form_submit_button("Register Account"):
                if np == cp:
                    try:
                        conn = sqlite3.connect('gritt_database.db')
                        conn.execute('INSERT INTO users (username, password) VALUES (?,?)', (nu, hash_password(np)))
                        conn.commit(); conn.close()
                        st.success("Registration Successful!")
                    except: st.error("Username already exists.")
                else: st.error("Passwords do not match.")

# --- CHART GENERATOR ---
def create_radar_chart(row, title):
    cat = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
    scr = [row['Global'], row['Resilient'], row['Innovative'], row['Trustworthy'], row['Talent']]
    df = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat + [cat[0]]))
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, title=title)
    fig.update_traces(fill='toself', fillcolor='rgba(0, 114, 178, 0.4)', line_color='rgb(0, 114, 178)', line_width=3)
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# --- MAIN DASHBOARD ---
def main_dashboard():
    l_col, r_col = st.columns([5, 1])
    l_col.title("🎓 FTK GRITT Dashboard")
    r_col.write(""); r_col.button("Logout", on_click=lambda: st.session_state.update(logged_in=False, username="", role=""), use_container_width=True)
    
    role_name = "🛡️ Admin" if st.session_state['role'] == 'admin' else "👨‍🏫 Lecturer"
    st.markdown(f"*User: **{st.session_state['username']}** ({role_name})*")
    
    t1, t2, t3, t4 = st.tabs(["📊 Charts", "📝 Data Entry", "🏛️ Faculty Info", "🎯 KPI Jabatan"])
    
    # TAB 1: CHARTS
    with t1:
        df = load_data()
        df['Display'] = df['Student Name'] + " (" + df['Matrix Number'] + ")"
        sm = st.text_input("🔍 Quick Search by Matrix Number:")
        if sm:
            match = df[df['Matrix Number'].str.upper() == sm.upper().strip()]
            if not match.empty: st.plotly_chart(create_radar_chart(match.iloc[0], f"Profile: {match.iloc[0]['Display']}"), use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            fs = c1.selectbox("Filter Session:", ["All"] + list(df['Session'].unique()))
            fp = c2.selectbox("Filter Programme:", ["All"] + list(df['Programme'].unique()))
            f_df = df.copy()
            if fs != "All": f_df = f_df[f_df['Session'] == fs]
            if fp != "All": f_df = f_df[f_df['Programme'] == fp]
            if not f_df.empty:
                sel = st.selectbox("Select Student:", f_df['Display'])
                st.plotly_chart(create_radar_chart(f_df[f_df['Display'] == sel].iloc[0], sel), use_container_width=True)

    # TAB 2: DATA ENTRY
    with t2:
        st.subheader("Add Student Data")
        st.download_button("📥 Download Excel Template", data=generate_template_excel(), file_name="FTK_Template.xlsx")
        
        up = st.file_uploader("Upload Batch File (Excel/CSV)", type=["csv", "xlsx"])
        if up:
            try:
                udf = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
                st.dataframe(udf.head(3))
                if st.button("Confirm Batch Upload"):
                    conn = sqlite3.connect('gritt_database.db'); udf.to_sql('students', conn, if_exists='append', index=False); conn.close()
                    st.success("Batch uploaded!"); st.rerun()
            except Exception as e: st.error(e)
            
        st.divider()
        with st.form("manual_entry_form"):
            st.markdown("### Manual Student Entry")
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name"); mat = c2.text_input("Matrix Number"); sess = c3.selectbox("Session", ["2024/2025", "2025/2026"])
            prog = st.text_input("Programme (e.g. KNT)")
            sc = st.columns(5)
            g=sc[0].number_input("Global",0,100,50); r=sc[1].number_input("Resilient",0,100,50); i=sc[2].number_input("Innov",0,100,50); t1=sc[3].number_input("Trust",0,100,50); t2=sc[4].number_input("Talent",0,100,50)
            if st.form_submit_button("Save Student"):
                conn = sqlite3.connect('gritt_database.db')
                conn.execute('INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?)', (name, mat, sess, 'FTK', 'Pagoh', prog, g, r, i, t1, t2))
                conn.commit(); conn.close(); st.success("Student Saved!"); st.rerun()

        # --- ADMIN DELETE SECTION ---
        if st.session_state['role'] == 'admin':
            st.divider()
            st.markdown("### 🗑️ Admin: Manage Database & Delete Duplicates")
            df_manage = load_data()
            st.dataframe(df_manage[['rowid', 'Student Name', 'Matrix Number', 'Session', 'Programme']], use_container_width=True)
            rid = st.number_input("Enter RowID to Delete Permanently:", min_value=1, step=1)
            if st.button("❌ Execute Delete", type="primary"):
                conn = sqlite3.connect('gritt_database.db')
                conn.execute('DELETE FROM students WHERE rowid=?', (rid,))
                conn.commit(); conn.close(); st.success(f"Row {rid} deleted!"); st.rerun()

    # TAB 3: FACULTY INFO
    with t3:
        ca, cb = st.columns([1, 2])
        with ca:
            g_df = get_ge_data()
            if not g_df.empty:
                st.metric("Latest GE %", f"{g_df.iloc[-1]['percentage']}%")
                st.plotly_chart(px.line(g_df, x='year', y='percentage', markers=True, title="GE Trend").update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'), use_container_width=True)
                if st.session_state['role'] == 'admin':
                    with st.form("ge_form"):
                        y = st.number_input("Year", 2020, 2100, 2025); p = st.number_input("GE Percentage (%)", 0.0, 100.0, 85.0)
                        if st.form_submit_button("Update GE Data"):
                            conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT OR REPLACE INTO ge_data VALUES (?,?)', (y, p)); conn.commit(); conn.close(); st.rerun()
        with cb:
            st.markdown("### 📅 Official Programs")
            evs = get_events()
            for _, ev in evs.iterrows():
                st.markdown(f"#### {ev['title']}")
                if ev['image_data']: st.image(base64.b64decode(ev['image_data']), use_container_width=True)
                st.write(ev['description'])
                if st.session_state['role'] == 'admin':
                    if st.button("Delete Event", key=f"event_{ev['id']}"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('DELETE FROM events WHERE id=?', (ev['id'],)); conn.commit(); conn.close(); st.rerun()
                st.divider()

    # TAB 4: KPI
    with t4:
        st.subheader("🎯 KPI Jabatan Targets")
        k_df = get_kpi_data()
        jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
        if st.session_state['role'] == 'admin':
            with st.expander("🛠️ Admin: Add New KPI"):
                with st.form("kpi_add_form"):
                    j = st.selectbox("Select Jabatan", jabs); d = st.text_area("Target Description")
                    if st.form_submit_button("Add KPI"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (?,?)', (j, d)); conn.commit(); conn.close(); st.rerun()
        for jb in jabs:
            st.markdown(f"### {jb}")
            jab_kpis = k_df[k_df['jabatan'] == jb]
            for _, r in jab_kpis.iterrows():
                c1, c2 = st.columns([5, 1])
                c1.write(f"• {r['kpi_desc']}")
                if st.session_state['role'] == 'admin' and c2.button("Del", key=f"kpi_{r['id']}"):
                    conn = sqlite3.connect('gritt_database.db'); conn.execute('DELETE FROM kpi_data WHERE id=?', (r['id'],)); conn.commit(); conn.close(); st.rerun()

if not st.session_state['logged_in']: login_screen()
else: main_dashboard()