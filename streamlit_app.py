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
    
    # Initial Admin & Dummy Data
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

# --- LOGIN ---
def login_screen():
    st.title("🔒 FTK Staff Portal")
    t1, t2 = st.tabs(["Login", "Register"])
    with t1:
        with st.form("l"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                conn = sqlite3.connect('gritt_database.db')
                res = conn.execute('SELECT password, role FROM users WHERE username=?', (u,)).fetchone()
                conn.close()
                if res and check_password(p, res[0]):
                    st.session_state.update(logged_in=True, username=u, role=res[1])
                    st.rerun()
                else: st.error("Invalid")
    with t2:
        with st.form("r"):
            nu, np, cp = st.text_input("New User"), st.text_input("New Pass", type="password"), st.text_input("Confirm", type="password")
            if st.form_submit_button("Register"):
                if np == cp:
                    try:
                        conn = sqlite3.connect('gritt_database.db')
                        conn.execute('INSERT INTO users (username, password) VALUES (?,?)', (nu, hash_password(np)))
                        conn.commit(); conn.close()
                        st.success("Done!")
                    except: st.error("Exists")
                else: st.error("Mismatch")

# --- CHART ---
def create_radar_chart(row, title):
    cat = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
    scr = [row['Global'], row['Resilient'], row['Innovative'], row['Trustworthy'], row['Talent']]
    df = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat + [cat[0]]))
    fig = px.line_polar(df, r='r', theta='theta', line_close=True, title=title)
    fig.update_traces(fill='toself', fillcolor='rgba(0, 114, 178, 0.4)', line_color='rgb(0, 114, 178)', line_width=3)
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# --- MAIN APP ---
def main_dashboard():
    l, r = st.columns([5, 1])
    l.title("🎓 FTK GRITT Dashboard")
    r.button("Logout", on_click=lambda: st.session_state.update(logged_in=False))
    
    role_name = "🛡️ Admin" if st.session_state['role'] == 'admin' else "👨‍🏫 Lecturer"
    st.markdown(f"*User: **{st.session_state['username']}** ({role_name})*")
    
    t1, t2, t3, t4 = st.tabs(["📊 Charts", "📝 Data Entry", "🏛️ Faculty", "🎯 KPI"])
    
    # TAB 1: CHARTS
    with t1:
        df = load_data()
        df['Display'] = df['Student Name'] + " (" + df['Matrix Number'] + ")"
        sm = st.text_input("🔍 Search Matrix:")
        if sm:
            match = df[df['Matrix Number'].str.upper() == sm.upper().strip()]
            if not match.empty: st.plotly_chart(create_radar_chart(match.iloc[0], f"Profile: {match.iloc[0]['Display']}"), use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            fs = c1.selectbox("Session", ["All"] + list(df['Session'].unique()))
            fp = c2.selectbox("Program", ["All"] + list(df['Programme'].unique()))
            f_df = df.copy()
            if fs != "All": f_df = f_df[f_df['Session'] == fs]
            if fp != "All": f_df = f_df[f_df['Programme'] == fp]
            if not f_df.empty:
                sel = st.selectbox("Student", f_df['Display'])
                st.plotly_chart(create_radar_chart(f_df[f_df['Display'] == sel].iloc[0], sel), use_container_width=True)

    # TAB 2: DATA ENTRY (FIXED)
    with t2:
        st.subheader("Add Student Data")
        st.download_button("📥 Download Excel Template", data=generate_template_excel(), file_name="Template.xlsx")
        
        up = st.file_uploader("Upload Excel/CSV", type=["csv", "xlsx"])
        if up:
            try:
                udf = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
                st.dataframe(udf.head(3))
                if st.button("Confirm Upload"):
                    conn = sqlite3.connect('gritt_database.db'); udf.to_sql('students', conn, if_exists='append', index=False); conn.close()
                    st.success("Batch Added!"); st.rerun()
            except Exception as e: st.error(e)
            
        st.divider()
        with st.form("m"):
            st.markdown("### Manual Entry")
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name"); mat = c2.text_input("Matrix"); sess = c3.selectbox("Session", ["2024/2025", "2025/2026"])
            prog = st.text_input("Program (e.g. KNT)")
            sc = st.columns(5)
            g=sc[0].number_input("G",0,100,50); r=sc[1].number_input("R",0,100,50); i=sc[2].number_input("I",0,100,50); t1=sc[3].number_input("T1",0,100,50); t2=sc[4].number_input("T2",0,100,50)
            if st.form_submit_button("Save Student"):
                conn = sqlite3.connect('gritt_database.db')
                conn.execute('INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?,?,?)', (name, mat, sess, 'FTK', 'Pagoh', prog, g, r, i, t1, t2))
                conn.commit(); conn.close(); st.success("Saved!"); st.rerun()

        # --- ADMIN DELETE SECTION ---
        if st.session_state['role'] == 'admin':
            st.divider()
            st.markdown("### 🗑️ Admin: Delete Duplicates")
            df_del = load_data()
            st.dataframe(df_del[['rowid', 'Student Name', 'Matrix Number', 'Session', 'Programme']], use_container_width=True)
            rid = st.number_input("Enter RowID to Delete", min_value=1, step=1)
            if st.button("❌ Delete Permanently", type="primary"):
                conn = sqlite3.connect('gritt_database.db')
                conn.execute('DELETE FROM students WHERE rowid=?', (rid,))
                conn.commit(); conn.close(); st.success("Deleted!"); st.rerun()

    # TAB 3: FACULTY INFO
    with t3:
        ca, cb = st.columns([1, 2])
        with ca:
            g_df = get_ge_data()
            if not g_df.empty:
                st.metric("GE %", f"{g_df.iloc[-1]['percentage']}%")
                st.plotly_chart(px.line(g_df, x='year', y='percentage', markers=True), use_container_width=True)
                if st.session_state['role'] == 'admin':
                    with st.form("ge"):
                        y = st.number_input("Year", 2020, 2100, 2025); p = st.number_input("%", 0.0, 100.0, 85.0)
                        if st.form_submit_button("Update GE"):
                            conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT OR REPLACE INTO ge_data VALUES (?,?)', (y, p)); conn.commit(); conn.close(); st.rerun()
        with cb:
            evs = get_events()
            for _, ev in evs.iterrows():
                st.markdown(f"#### {ev['title']}")
                if ev['image_data']: st.image(base64.b64decode(ev['image_data']), use_container_width=True)
                st.write(ev['description'])
                if st.session_state['role'] == 'admin':
                    if st.button("Del", key=f"e_{ev['id']}"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('DELETE FROM events WHERE id=?', (ev['id'],)); conn.commit(); conn.close(); st.rerun()
                st.divider()

    # TAB 4: KPI
    with t4:
        k_df = get_kpi_data()
        jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
        if st.session_state['role'] == 'admin':
            with st.expander("Add KPI"):
                with st.form("k"):
                    j = st.selectbox("Jabatan", jabs); d = st.text_area("Target")
                    if st.form_submit_button("Add"):
                        conn = sqlite3.connect('gritt_database.db'); conn.execute('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (?,?)', (j, d)); conn.commit(); conn.close(); st.rerun()
        for jb in jabs:
            st.markdown(f"### {jb}")
            for _, r in k_df[k_df['jabatan'] == jb].iterrows():
                c1, c2 = st.columns([5, 1])
                c1.write(f"• {r['kpi_desc']}")
                if st.session_state['role'] == 'admin' and c2.button("Del", key=f"k_{r['id']}"):
                    conn = sqlite3.connect('gritt_database.db'); conn.execute('DELETE FROM kpi_data WHERE id=?', (r['id'],)); conn.commit(); conn.close(); st.rerun()

if not st.session_state['logged_in']: login_screen()
else: main_dashboard()