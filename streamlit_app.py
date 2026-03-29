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
        cur.execute('''CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY, "Student Name" TEXT, "Matrix Number" TEXT, 
            session TEXT, faculty TEXT, campus TEXT, programme TEXT, 
            global REAL, resilient REAL, innovative REAL, trustworthy REAL, talent REAL)''')
        
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
        pass 

init_db()

# --- 4. DATA LOADING ---
def load_query(query, params=None):
    try:
        conn = get_connection()
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except:
        return pd.DataFrame() 

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
    cat_display = ['Global', 'Resilient', 'Innovative', 'Trustworthy', 'Talent']
    try:
        scr = [float(row.get(c, row.get(c.lower(), 50))) for c in cat_display]
        df_fig = pd.DataFrame(dict(r=scr + [scr[0]], theta=cat_display + [cat_display[0]]))
        fig = px.line_polar(df_fig, r='r', theta='theta', line_close=True, title=title)
        fig.update_traces(fill='toself', fillcolor='rgba(0, 114, 178, 0.4)')
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])))
        return fig
    except Exception as e:
        return None

# --- 6. MAIN DASHBOARD ---
def main_dashboard():
    l, r = st.columns([5, 1])
    l.title("🎓 FTK GRITT Dashboard (Supabase)")
    if r.button("Logout"):
        st.session_state.update(logged_in=False, username="", role="lecturer")
        st.rerun()
    
    # --- NEW: Visual Role Indicator ---
    is_admin = (st.session_state['role'] == 'admin')
    role_icon = "🛡️ Admin" if is_admin else "👨‍🏫 Lecturer"
    st.info(f"Welcome back, **{st.session_state['username']}**! You are logged in as: **{role_icon}**")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Charts", "📝 Data Entry", "🏛️ Faculty Info", "🎯 KPI"])
    
    with tab1:
        st.subheader("Student Performance")
        df = load_query('SELECT * FROM students')
        if not df.empty:
            name_col = 'Student Name' if 'Student Name' in df.columns else 'student name'
            matrix_col = 'Matrix Number' if 'Matrix Number' in df.columns else 'matrix number'
            
            df['Display'] = df[name_col] + " (" + df[matrix_col] + ")"
            sm = st.text_input("🔍 Search Matrix Number:")
            selected_student = None
            
            if sm:
                match = df[df[matrix_col].str.upper() == sm.upper().strip()]
                if not match.empty: selected_student = match.iloc[0]
                else: st.error("Not found.")
            else:
                sel_display = st.selectbox("Select Student:", df['Display'])
                selected_student = df[df['Display'] == sel_display].iloc[0]
            
            if selected_student is not None:
                chart = create_radar_chart(selected_student, selected_student['Display'])
                if chart: st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("Database is empty. Please add data in 'Data Entry' first.")

    with tab2:
        col_st, col_ev = st.columns(2)
        with col_st:
            with st.form("add_student"):
                st.subheader("Manual Student Entry")
                n, m, s = st.text_input("Name"), st.text_input("Matrix"), st.selectbox("Session", ["2024/2025", "2025/2026"])
                p = st.text_input("Programme")
                sc = st.columns(5)
                g=sc[0].number_input("Global",0,100,50); res=sc[1].number_input("Resilient",0,100,50); i=sc[2].number_input("Innovative",0,100,50); t1=sc[3].number_input("Trustworthy",0,100,50); t2=sc[4].number_input("Talent",0,100,50)
                if st.form_submit_button("Save Student"):
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute('''INSERT INTO students 
                        ("Student Name", "Matrix Number", session, faculty, campus, programme, global, resilient, innovative, trustworthy, talent) 
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', 
                        (n,m,s,'FTK','Pagoh',p,g,res,i,t1,t2))
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
            else:
                st.info("Only Admins can post faculty events.")

        st.divider()
        st.header("📁 Bulk Upload (Excel)")
        excel_data = generate_template_excel()
        st.download_button("📥 Download Excel Template", data=excel_data, file_name="student_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        uploaded_file = st.file_uploader("Upload filled Excel file", type=['xlsx'])
        if uploaded_file is not None:
            if st.button("🚀 Upload Data to Cloud", type="primary"):
                try:
                    df_upload = pd.read_excel(uploaded_file)
                    conn = get_connection(); cur = conn.cursor()
                    for _, row in df_upload.iterrows():
                        cur.execute('''INSERT INTO students 
                            ("Student Name", "Matrix Number", session, faculty, campus, programme, global, resilient, innovative, trustworthy, talent) 
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', 
                            (row['Student Name'], row['Matrix Number'], row['Session'], row['Faculty'], row['Campus'], row['Programme'], row['Global'], row['Resilient'], row['Innovative'], row['Trustworthy'], row['Talent']))
                    conn.commit(); conn.close()
                    st.success("Bulk Upload Successful!"); st.rerun()
                except Exception as e:
                    st.error(f"Error during upload. Details: {e}")

        # --- ADMIN ONLY ZONE ---
        if is_admin:
            st.divider()
            st.header("⚙️ Admin Settings & Controls")
            
            # NEW: User Account Creation
            with st.expander("👤 Create New User Account"):
                with st.form("create_user"):
                    new_u = st.text_input("New Username")
                    new_p = st.text_input("New Password", type="password")
                    new_r = st.selectbox("Role", ["lecturer", "admin"])
                    if st.form_submit_button("Create Account"):
                        if new_u and new_p:
                            hashed_p = hashlib.sha256(str.encode(new_p)).hexdigest()
                            try:
                                conn = get_connection(); cur = conn.cursor()
                                cur.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', (new_u, hashed_p, new_r))
                                conn.commit(); conn.close()
                                st.success(f"User '{new_u}' created successfully as {new_r}!")
                            except:
                                st.error("Username already exists or database error.")
                        else:
                            st.warning("Please fill in all fields.")

            c_ge, c_kp = st.columns(2)
            with c_ge:
                with st.form("admin_ge"):
                    st.subheader("Update GE %")
                    gy = st.number_input("Year", min_value=2000, max_value=2100, value=2024, step=1)
                    gp = st.number_input("Value %", min_value=0.0, max_value=100.0, value=90.0)
                    if st.form_submit_button("Save GE"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('INSERT INTO ge_data (year, percentage) VALUES (%s,%s) ON CONFLICT (year) DO UPDATE SET percentage = EXCLUDED.percentage', (gy, gp))
                        conn.commit(); conn.close(); st.success("GE Saved!"); st.rerun()
            
            with c_kp:
                jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
                with st.form("admin_kpi"):
                    st.subheader("Add KPI")
                    jb = st.selectbox("Dept", jabs)
                    kd = st.text_area("Target")
                    if st.form_submit_button("Add KPI"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('INSERT INTO kpi_data (jabatan, kpi_desc) VALUES (%s,%s)', (jb, kd))
                        conn.commit(); conn.close(); st.success("KPI Added!"); st.rerun()

            st.write("---")
            st.subheader("🗑️ Admin Deletion Center")
            del_t1, del_t2, del_t3, del_t4 = st.tabs(["👨‍🎓 Students", "📅 Events", "🎯 KPIs", "📈 GE Data"])
            
            with del_t1:
                df_view = load_query('SELECT id, "Student Name", "Matrix Number" FROM students')
                if not df_view.empty:
                    name_col = 'Student Name' if 'Student Name' in df_view.columns else 'student name'
                    matrix_col = 'Matrix Number' if 'Matrix Number' in df_view.columns else 'matrix number'
                    
                    # --- NEW: Search Bar for Deletion ---
                    search_del = st.text_input("🔍 Search Name or Matrix to Delete:", key="search_del_input")
                    
                    # Filter the table based on search
                    if search_del:
                        mask = df_view[name_col].str.contains(search_del, case=False, na=False) | \
                               df_view[matrix_col].str.contains(search_del, case=False, na=False)
                        df_display = df_view[mask]
                    else:
                        df_display = df_view
                    
                    # Show the filtered table
                    st.dataframe(df_display[['id', name_col, matrix_col]], use_container_width=True)
                    
                    # Delete Execution
                    if not df_display.empty:
                        target_id = st.number_input("Enter Student ID to Delete", step=1, min_value=0, key="del_stu")
                        if st.button("Delete Student", type="primary"):
                            conn = get_connection(); cur = conn.cursor()
                            cur.execute('DELETE FROM students WHERE id = %s', (target_id,))
                            conn.commit(); conn.close(); st.success("Student Deleted!"); st.rerun()
                    else:
                        st.warning("No students match your search.")
                else: 
                    st.info("No students to delete.")

            with del_t2:
                ev_view = load_query('SELECT id, title FROM events')
                if not ev_view.empty:
                    st.dataframe(ev_view, use_container_width=True)
                    e_id = st.number_input("Event ID to Delete", step=1, min_value=0, key="del_ev")
                    if st.button("Delete Event", type="primary"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('DELETE FROM events WHERE id = %s', (e_id,))
                        conn.commit(); conn.close(); st.rerun()
                else: st.info("No events to delete.")
                        
            with del_t3:
                kpi_view = load_query('SELECT id, jabatan, kpi_desc FROM kpi_data')
                if not kpi_view.empty:
                    st.dataframe(kpi_view, use_container_width=True)
                    k_id = st.number_input("KPI ID to Delete", step=1, min_value=0, key="del_kpi")
                    if st.button("Delete KPI", type="primary"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('DELETE FROM kpi_data WHERE id = %s', (k_id,))
                        conn.commit(); conn.close(); st.rerun()
                else: st.info("No KPIs to delete.")
                        
            with del_t4:
                ge_view = load_query('SELECT year, percentage FROM ge_data')
                if not ge_view.empty:
                    st.dataframe(ge_view, use_container_width=True)
                    g_yr = st.number_input("GE Year to Delete", step=1, min_value=2000, key="del_ge")
                    if st.button("Delete GE Data", type="primary"):
                        conn = get_connection(); cur = conn.cursor()
                        cur.execute('DELETE FROM ge_data WHERE year = %s', (g_yr,))
                        conn.commit(); conn.close(); st.rerun()
                else: st.info("No GE data to delete.")

    with tab3:
        st.subheader("Faculty Insights")
        ge_df = load_query('SELECT * FROM ge_data ORDER BY year ASC')
        if not ge_df.empty: 
            ge_df['Year'] = ge_df['year'].astype(str)
            fig_ge = px.line(ge_df, x='Year', y='percentage', title="GE Trend", markers=True)
            fig_ge.update_yaxes(title_text="Percentage (%)")
            st.plotly_chart(fig_ge, use_container_width=True)
        
        st.divider()
        ev_df = load_query('SELECT * FROM events ORDER BY id DESC')
        if not ev_df.empty:
            for _, ev in ev_df.iterrows():
                st.markdown(f"### {ev.get('title', 'Event')}")
                img_data = ev.get('image_data')
                if img_data: st.image(base64.b64decode(img_data), use_container_width=True)
                st.write(ev.get('description', '')); st.divider()
        else:
            st.info("No events posted yet.")

    with tab4:
        st.subheader("🎯 Strategic KPI")
        kpi_df = load_query('SELECT * FROM kpi_data')
        jabs = ["JTKE (Elektrik)", "JTKK (Kimia)", "JTKM (Mekanikal)", "JTKA (Awam)", "JTKP (Pengangkutan)", "Jabatan Siswazah"]
        for jb in jabs:
            st.markdown(f"#### {jb}")
            if not kpi_df.empty:
                jab_col = 'jabatan' if 'jabatan' in kpi_df.columns else 'Jabatan'
                desc_col = 'kpi_desc' if 'kpi_desc' in kpi_df.columns else 'KPI_desc'
                
                rows = kpi_df[kpi_df[jab_col] == jb]
                for _, r in rows.iterrows(): 
                    st.write(f"• {r[desc_col]}")
            if kpi_df.empty or rows.empty:
                st.write("*No KPIs added yet.*")

def login_screen():
    st.title("🔒 FTK Staff Portal")
    u, p = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_connection(); cur = conn.cursor()
        password_col = "password"
        role_col = "role"
        username_col = "username"
        cur.execute(f'SELECT {password_col}, {role_col} FROM users WHERE {username_col} = %s', (u,))
        res = cur.fetchone(); conn.close()
        if res and check_password(p, res[0]):
            st.session_state.update(logged_in=True, username=u, role=res[1]); st.rerun()
        else: st.error("Access Denied or Incorrect Password")

if not st.session_state['logged_in']: login_screen()
else: main_dashboard()