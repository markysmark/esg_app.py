"""
ESG Intelligence Platform - Main Application
Comprehensive ESG data management, analysis, and reporting system
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import json
import os
from theme import apply_theme, brand_palette

# ==================== DATABASE SETUP ====================
Base = declarative_base()
engine = create_engine('sqlite:///jpc_esg_intelligence.db')
Session = sessionmaker(bind=engine)
session = Session()


# Database Models
class ESGEntry(Base):
    __tablename__ = 'esg_master'
    id = Column(Integer, primary_key=True)
    client = Column(String)
    agent = Column(String)
    building = Column(String)
    waste_tonnes = Column(Float, default=0.0)
    employee_count = Column(Integer, default=0)
    hours_worked = Column(Float, default=0.0)
    chem_litres = Column(Float, default=0.0)
    eco_chem_pct = Column(Float, default=0.0)
    energy_kwh = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)


class ScoreSnapshot(Base):
    __tablename__ = 'score_snapshots'
    id = Column(Integer, primary_key=True)
    client = Column(String)
    agent = Column(String)
    building = Column(String)
    esg_score = Column(Float)
    e_score = Column(Float)
    s_score = Column(Float)
    g_score = Column(Float)
    period = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportRun(Base):
    __tablename__ = 'report_runs'
    id = Column(Integer, primary_key=True)
    report_type = Column(String)
    scope_entity = Column(String)
    filters = Column(Text)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    scoring_version = Column(String)
    file_reference = Column(String)
    snapshot_ids = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ObligationStatus(Base):
    __tablename__ = 'obligation_statuses'
    id = Column(Integer, primary_key=True)
    building = Column(String)
    obligation = Column(String)
    status = Column(String)
    due_date = Column(DateTime)
    severity = Column(String)


class ActionLog(Base):
    __tablename__ = 'action_log'
    id = Column(Integer, primary_key=True)
    building = Column(String)
    owner = Column(String)
    action = Column(String)
    due_date = Column(DateTime)
    status = Column(String)


class EvidenceRegister(Base):
    __tablename__ = 'evidence_register'
    id = Column(Integer, primary_key=True)
    building = Column(String)
    item_type = Column(String)
    reference = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)

# ==================== CLIENTS & AGENTS ====================
CLIENTS_FILE = "clients_agents.json"


def load_clients_data():
    """Load clients and agents from JSON file"""
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, 'r') as f:
            return json.load(f)
    else:
        default_data = {
            "UK Top Agents": {
                "Agents": ["CBRE", "Savills", "JLL", "Knight Frank", "Cushman & Wakefield"],
                "Buildings": ["One Churchill Place", "Centre Point", "30 St Mary Axe", "Cheapside House", "The Shard"]
            },
            "British Land": {
                "Agents": ["CBRE", "Savills"],
                "Buildings": ["The Leadenhall Building", "Broadgate Tower"]
            },
            "Landsec": {
                "Agents": ["Knight Frank"],
                "Buildings": ["20 Fenchurch Street", "One New Change"]
            },
            "Mitsubishi Estate": {
                "Agents": ["JLL"],
                "Buildings": ["8 Bishopsgate"]
            }
        }
        save_clients_data(default_data)
        return default_data


def save_clients_data(data):
    """Save clients and agents to JSON file"""
    with open(CLIENTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# Initialize session state
if 'clients_data' not in st.session_state:
    st.session_state.clients_data = load_clients_data()

if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Dashboard'

# ==================== CORE FUNCTIONS ====================

def compute_esg_scores(entry: ESGEntry):
    """Calculate E/S/G scores from entry data"""
    if not entry:
        return 0.0, 0.0, 0.0, 0.0

    # Environmental
    waste = float(entry.waste_tonnes or 0.0)
    energy = float(entry.energy_kwh or 0.0)
    waste_score = max(0.0, 100.0 - (waste / 20.0) * 100.0)
    energy_score = max(0.0, 100.0 - (energy / 20000.0) * 100.0)
    chem_bonus = min(10.0, float(entry.eco_chem_pct or 0.0) * 0.1)
    e = (waste_score + energy_score) / 2.0 + chem_bonus

    # Social
    emp = max(1.0, float(entry.employee_count or 0))
    hrs = float(entry.hours_worked or 0.0)
    hrs_per_emp = hrs / emp
    s = min(100.0, (hrs_per_emp / 40.0) * 100.0 + min(emp, 100.0) / 100.0 * 10.0)

    # Governance
    eco_pct = float(entry.eco_chem_pct or 0.0)
    base = 50.0 + eco_pct * 0.3
    evidence_count = session.query(EvidenceRegister).filter(
        EvidenceRegister.building == entry.building
    ).count() if entry.building else 0
    g = base + min(20.0, evidence_count * 2.0)

    def clamp(v):
        return max(0.0, min(100.0, round(v, 1)))

    e, s, g = clamp(e), clamp(s), clamp(g)
    overall = round((e * 0.50) + (s * 0.30) + (g * 0.20), 1)
    return e, s, g, overall


def grade_data_quality(client, agent=None, building=None):
    """Grade data quality for given scope"""
    q = session.query(ESGEntry)
    if building:
        q = q.filter(ESGEntry.building == building)
    elif agent:
        q = q.filter(ESGEntry.agent == agent)
    elif client:
        q = q.filter(ESGEntry.client == client)
    
    entries = q.all()
    expected_fields = ['waste_tonnes', 'energy_kwh', 'chem_litres', 'eco_chem_pct', 'employee_count', 'hours_worked']

    if entries:
        latest = max(entries, key=lambda e: e.timestamp or datetime.min)
        filled = sum(1 for f in expected_fields if getattr(latest, f, None) not in (None, 0, "", 0.0))
        current_data_pct = int((filled / len(expected_fields)) * 100)
        days = (datetime.utcnow() - latest.timestamp).days if latest.timestamp else 365
        avg_confidence = 1.0 if days <= 30 else max(0.0, 1.0 - (days / 365.0))
    else:
        current_data_pct = 0
        avg_confidence = 0.0

    evidence_count = session.query(EvidenceRegister).filter(EvidenceRegister.building == building).count() if building else 0
    obligations_with_evidence_pct = min(100, evidence_count * 20)

    if current_data_pct >= 90 and obligations_with_evidence_pct >= 80 and avg_confidence >= 0.8:
        grade = "A"
    elif current_data_pct >= 75 and obligations_with_evidence_pct >= 50 and avg_confidence >= 0.5:
        grade = "B"
    elif current_data_pct >= 50:
        grade = "C"
    else:
        grade = "F"

    return {
        "grade": grade,
        "current_data_pct": current_data_pct,
        "obligations_with_evidence_pct": obligations_with_evidence_pct,
        "avg_confidence": round(avg_confidence, 2)
    }


def log_action(building, owner, action, due_date=None, status=None):
    """Log an action in the database"""
    al = ActionLog(building=building or '', owner=owner, action=action, due_date=due_date, status=status or '')
    session.add(al)
    session.commit()
    return al


def load_savills_demo_data():
    """Load realistic demo data for Savills' managed buildings"""
    demo_buildings = [
        {
            'client': 'British Land',
            'agent': 'Savills',
            'building': 'The Leadenhall Building',
            'waste_tonnes': 12.5,
            'energy_kwh': 52000,
            'chem_litres': 145,
            'eco_chem_pct': 82,
            'employee_count': 480,
            'hours_worked': 99840
        },
        {
            'client': 'British Land',
            'agent': 'Savills',
            'building': 'Broadgate Tower',
            'waste_tonnes': 18.2,
            'energy_kwh': 68500,
            'chem_litres': 210,
            'eco_chem_pct': 75,
            'employee_count': 620,
            'hours_worked': 128960
        },
        {
            'client': 'UK Top Agents',
            'agent': 'Savills',
            'building': 'Centre Point',
            'waste_tonnes': 9.8,
            'energy_kwh': 41200,
            'chem_litres': 98,
            'eco_chem_pct': 88,
            'employee_count': 350,
            'hours_worked': 72800
        },
        {
            'client': 'UK Top Agents',
            'agent': 'Savills',
            'building': 'St Pauls House',
            'waste_tonnes': 15.3,
            'energy_kwh': 58700,
            'chem_litres': 175,
            'eco_chem_pct': 79,
            'employee_count': 520,
            'hours_worked': 107440
        }
    ]
    
    for data in demo_buildings:
        # Check if building already exists
        existing = session.query(ESGEntry).filter(
            ESGEntry.building == data['building'],
            ESGEntry.agent == 'Savills'
        ).first()
        
        if not existing:
            entry = ESGEntry(
                client=data['client'],
                agent=data['agent'],
                building=data['building'],
                waste_tonnes=data['waste_tonnes'],
                energy_kwh=data['energy_kwh'],
                chem_litres=data['chem_litres'],
                eco_chem_pct=data['eco_chem_pct'],
                employee_count=data['employee_count'],
                hours_worked=data['hours_worked'],
                timestamp=datetime.utcnow()
            )
            session.add(entry)
    
    session.commit()
    log_action('', 'system', 'Savills demo data loaded', status='demo')


def clear_savills_demo_data():
    """Clear all demo data for Savills (admin only)"""
    deleted_count = session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').delete()
    session.commit()
    log_action('', 'admin', f'Cleared {deleted_count} Savills demo data records', status='admin')
    return deleted_count


def load_test_client_data():
    """Load comprehensive test data for Test Client with diverse buildings"""
    test_buildings = [
        {
            'client': 'Test Client',
            'agent': 'CBRE',
            'building': 'Tech Hub Downtown',
            'waste_tonnes': 14.2,
            'energy_kwh': 55000,
            'chem_litres': 120,
            'eco_chem_pct': 85,
            'employee_count': 450,
            'hours_worked': 93600
        },
        {
            'client': 'Test Client',
            'agent': 'CBRE',
            'building': 'Innovation Plaza',
            'waste_tonnes': 10.5,
            'energy_kwh': 38000,
            'chem_litres': 80,
            'eco_chem_pct': 92,
            'employee_count': 320,
            'hours_worked': 66560
        },
        {
            'client': 'Test Client',
            'agent': 'JLL',
            'building': 'Green Heights Tower',
            'waste_tonnes': 8.3,
            'energy_kwh': 32000,
            'chem_litres': 65,
            'eco_chem_pct': 95,
            'employee_count': 280,
            'hours_worked': 58240
        },
        {
            'client': 'Test Client',
            'agent': 'JLL',
            'building': 'Commerce Center East',
            'waste_tonnes': 22.0,
            'energy_kwh': 78000,
            'chem_litres': 250,
            'eco_chem_pct': 65,
            'employee_count': 680,
            'hours_worked': 141120
        },
        {
            'client': 'Test Client',
            'agent': 'Knight Frank',
            'building': 'Sustainable Park West',
            'waste_tonnes': 11.7,
            'energy_kwh': 42000,
            'chem_litres': 95,
            'eco_chem_pct': 88,
            'employee_count': 380,
            'hours_worked': 78960
        },
        {
            'client': 'Test Client',
            'agent': 'Knight Frank',
            'building': 'Executive Plaza South',
            'waste_tonnes': 19.5,
            'energy_kwh': 72000,
            'chem_litres': 210,
            'eco_chem_pct': 72,
            'employee_count': 620,
            'hours_worked': 128960
        },
        {
            'client': 'Test Client',
            'agent': 'Savills',
            'building': 'Urban Living Complex',
            'waste_tonnes': 13.8,
            'energy_kwh': 48000,
            'chem_litres': 130,
            'eco_chem_pct': 80,
            'employee_count': 400,
            'hours_worked': 83200
        },
        {
            'client': 'Test Client',
            'agent': 'Savills',
            'building': 'Corporate Crown',
            'waste_tonnes': 16.4,
            'energy_kwh': 62000,
            'chem_litres': 180,
            'eco_chem_pct': 78,
            'employee_count': 550,
            'hours_worked': 114400
        }
    ]
    
    for data in test_buildings:
        # Check if building already exists
        existing = session.query(ESGEntry).filter(
            ESGEntry.building == data['building'],
            ESGEntry.client == 'Test Client'
        ).first()
        
        if not existing:
            entry = ESGEntry(
                client=data['client'],
                agent=data['agent'],
                building=data['building'],
                waste_tonnes=data['waste_tonnes'],
                energy_kwh=data['energy_kwh'],
                chem_litres=data['chem_litres'],
                eco_chem_pct=data['eco_chem_pct'],
                employee_count=data['employee_count'],
                hours_worked=data['hours_worked'],
                timestamp=datetime.utcnow()
            )
            session.add(entry)
    
    session.commit()
    log_action('', 'system', 'Test Client demo data loaded', status='demo')


def clear_test_client_data():
    """Clear all demo data for Test Client (admin only)"""
    deleted_count = session.query(ESGEntry).filter(ESGEntry.client == 'Test Client').delete()
    session.commit()
    log_action('', 'admin', f'Cleared {deleted_count} Test Client demo data records', status='admin')
    return deleted_count


# ==================== PAGE FUNCTIONS ====================

def page_home():
    """Home/Dashboard page"""
    st.title("🌍 ESG Intelligence Platform")
    st.markdown("Corporate Environmental, Social & Governance data management and analysis")
    
    st.divider()
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    
    all_entries = session.query(ESGEntry).all()
    unique_buildings = len(set(e.building for e in all_entries if e.building))
    unique_clients = len(set(e.client for e in all_entries if e.client))
    unique_agents = len(set(e.agent for e in all_entries if e.agent))
    
    with col1:
        st.metric("📊 Buildings", unique_buildings)
    with col2:
        st.metric("🏢 Clients", unique_clients)
    with col3:
        st.metric("👥 Managing Agents", unique_agents)
    with col4:
        st.metric("📈 Total Records", len(all_entries))
    
    st.divider()
    
    # Welcome section
    st.markdown("""
    ### Welcome to ESG Intelligence
    
    This platform enables you to:
    - **📥 Upload** bulk ESG data for multiple properties
    - **📊 Analyze** environmental, social, and governance performance
    - **📄 Generate** comprehensive compliance reports
    - **📈 Track** performance trends over time
    - **📤 Export** data in multiple formats
    
    ---
    
    ### Getting Started
    
    **1. Upload Data** → Use the Data Upload page to import your ESG metrics  
    **2. View Dashboard** → See your portfolio performance at a glance  
    **3. Manage Sites** → Add clients, agents, and buildings  
    **4. Generate Reports** → Create detailed ESG reports  
    **5. Export Data** → Download your data in CSV, Excel, or PDF format  
    """)
    
    st.divider()
    
    # Latest updates
    st.subheader("📰 Latest Updates")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("✅ New Feature: Bulk CSV/Excel Import - Import multiple building records at once")
    
    with col2:
        st.info("📊 Dashboard Enhancement: Real-time portfolio analytics with risk assessment")
    
    # Quick action buttons
    st.divider()
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📤 Upload Data", width="stretch"):
            st.session_state.current_page = 'Data Upload'
            st.rerun()
    
    with col2:
        if st.button("📊 View Dashboard", width="stretch"):
            st.session_state.current_page = 'Dashboard'
            st.rerun()
    
    with col3:
        if st.button("📄 Generate Report", width="stretch"):
            st.session_state.current_page = 'Reports'
            st.rerun()
    
    with col4:
        if st.button("⚙️ Manage Data", width="stretch"):
            st.session_state.current_page = 'Management'
            st.rerun()


def page_upload_data():
    """Data upload page"""
    from data_upload import render_upload_interface
    render_upload_interface()


def page_dashboard():
    """Analytics dashboard page"""
    from dashboard import render_dashboard
    render_dashboard(brand_palette=brand_palette)


def page_reports():
    """Reporting and export page"""
    from export_report import render_export_interface
    render_export_interface()


def page_management():
    """Data management page"""
    st.header("⚙️ Data Management")
    st.markdown("Manage clients, agents, buildings, and view raw data.")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Structure", "📊 Raw Data", "🗂️ Add Items", "📁 Evidence", "📦 Demo Data"])
    
    with tab1:
        st.subheader("Portfolio Structure")
        
        for client, data in st.session_state.clients_data.items():
            with st.expander(f"🏢 {client}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Agents ({len(data['Agents'])})**")
                    for agent in data['Agents']:
                        st.text(f"  • {agent}")
                
                with col2:
                    st.write(f"**Buildings ({len(data['Buildings'])})**")
                    for building in data['Buildings']:
                        st.text(f"  • {building}")
    
    with tab2:
        st.subheader("Raw ESG Data")
        
        client_sel = st.selectbox("Filter by Client", ["All"] + list(st.session_state.clients_data.keys()), key="mgmt_client")
        
        q = session.query(ESGEntry)
        if client_sel != "All":
            q = q.filter(ESGEntry.client == client_sel)
        
        entries = q.order_by(ESGEntry.timestamp.desc()).all()
        
        if entries:
            data = []
            for e in entries:
                score_e, score_s, score_g, score_esg = compute_esg_scores(e)
                data.append({
                    'Date': e.timestamp.strftime('%Y-%m-%d %H:%M'),
                    'Client': e.client,
                    'Agent': e.agent,
                    'Building': e.building,
                    'E-Score': score_e,
                    'S-Score': score_s,
                    'G-Score': score_g,
                    'ESG': score_esg,
                    'Waste (T)': e.waste_tonnes,
                    'Energy (kWh)': e.energy_kwh,
                    'Staff': e.employee_count
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, width="stretch", height=400)
            
            # Download option
            csv = df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, "esg_data.csv", "text/csv")
        else:
            st.info("No ESG data available yet. Upload data first.")
    
    with tab3:
        st.subheader("Add New Items")
        
        action = st.radio("What to add?", ["Client", "Agent", "Building"])
        
        if action == "Client":
            client_name = st.text_input("Client Name")
            if st.button("Add Client"):
                if client_name and client_name not in st.session_state.clients_data:
                    st.session_state.clients_data[client_name] = {"Agents": [], "Buildings": []}
                    save_clients_data(st.session_state.clients_data)
                    st.success(f"✅ Client '{client_name}' added!")
                    st.rerun()
                else:
                    st.error("Client already exists or name is empty")
        
        elif action == "Agent":
            target_client = st.selectbox("Select Client", list(st.session_state.clients_data.keys()))
            agent_name = st.text_input("Agent Name")
            if st.button("Add Agent"):
                if agent_name and agent_name not in st.session_state.clients_data[target_client]["Agents"]:
                    st.session_state.clients_data[target_client]["Agents"].append(agent_name)
                    save_clients_data(st.session_state.clients_data)
                    st.success(f"✅ Agent '{agent_name}' added!")
                    st.rerun()
                else:
                    st.error("Agent already exists or name is empty")
        
        elif action == "Building":
            target_client = st.selectbox("Select Client", list(st.session_state.clients_data.keys()), key="bld_client")
            building_name = st.text_input("Building Name")
            if st.button("Add Building"):
                if building_name and building_name not in st.session_state.clients_data[target_client]["Buildings"]:
                    st.session_state.clients_data[target_client]["Buildings"].append(building_name)
                    save_clients_data(st.session_state.clients_data)
                    st.success(f"✅ Building '{building_name}' added!")
                    st.rerun()
                else:
                    st.error("Building already exists or name is empty")
    
    with tab4:
        st.subheader("Evidence Documents")
        
        building_sel = st.selectbox("Select Building", ["All"] + [b for client_data in st.session_state.clients_data.values() for b in client_data["Buildings"]])
        
        q = session.query(EvidenceRegister)
        if building_sel != "All":
            q = q.filter(EvidenceRegister.building == building_sel)
        
        evidence = q.order_by(EvidenceRegister.uploaded_at.desc()).all()
        
        if evidence:
            df_evidence = pd.DataFrame([{
                'Building': e.building,
                'Document': os.path.basename(e.reference),
                'Type': e.item_type,
                'Uploaded': e.uploaded_at.strftime('%Y-%m-%d %H:%M')
            } for e in evidence])
            
            st.dataframe(df_evidence, width="stretch")
        else:
            st.info("No evidence documents uploaded yet.")
    
    with tab5:
        st.subheader("📦 Demo Data Management")
        st.markdown("Load realistic demo data to test the platform features and visualizations.")
        
        # Check if demo data exists
        savills_count = session.query(ESGEntry).filter(ESGEntry.agent == 'Savills').count()
        test_count = session.query(ESGEntry).filter(ESGEntry.client == 'Test Client').count()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Savills Records", savills_count)
        
        with col2:
            st.metric("Test Client Records", test_count)
        
        with col3:
            if savills_count > 0:
                st.success("✅ Savills Active")
            else:
                st.info("Savills Inactive")
        
        with col4:
            if test_count > 0:
                st.success("✅ Test Client Active")
            else:
                st.info("Test Client Inactive")
        
        st.divider()
        
        tab5_1, tab5_2 = st.tabs(["🏢 Savills (UK Top Agents)", "🧪 Test Client (Diverse)"])
        
        with tab5_1:
            st.markdown("""
            **Savills manages 4 buildings with realistic ESG metrics:**
            - The Leadenhall Building (480 staff, 52,000 kWh)
            - Broadgate Tower (620 staff, 68,500 kWh)
            - Centre Point (350 staff, 41,200 kWh)
            - St Pauls House (520 staff, 58,700 kWh)
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Load Savills Demo Data", use_container_width=True, type="primary", key="load_savills"):
                    try:
                        load_savills_demo_data()
                        st.success("✅ Savills demo data loaded successfully!")
                        st.info("View the data in the Dashboard or Raw Data tab")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading demo data: {e}")
            
            with col2:
                if savills_count > 0:
                    password = st.text_input("Admin password to clear", type="password", key="admin_clear_savills")
                    if st.button("🗑️ Clear Savills Data", use_container_width=True, type="secondary", key="clear_savills"):
                        if password == os.environ.get("ADMIN_PASSWORD", "admin123"):
                            deleted = clear_savills_demo_data()
                            st.success(f"✅ Cleared {deleted} Savills records")
                            st.rerun()
                        else:
                            st.error("❌ Incorrect admin password")
                else:
                    st.info("No Savills data to clear")
        
        with tab5_2:
            st.markdown("""
            **Test Client has 8 buildings across multiple agents with diverse ESG performance:**
            - Tech Hub Downtown (CBRE) - Strong performer
            - Innovation Plaza (CBRE) - Excellent eco-chemistry
            - Green Heights Tower (JLL) - Best in class
            - Commerce Center East (JLL) - Larger facility
            - Sustainable Park West (Knight Frank) - Balanced metrics
            - Executive Plaza South (Knight Frank) - High employee count
            - Urban Living Complex (Savills) - Mixed metrics
            - Corporate Crown (Savills) - Average performer
            
            Perfect for testing dashboards and comparisons!
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Load Test Client Data", use_container_width=True, type="primary", key="load_test"):
                    try:
                        load_test_client_data()
                        st.success("✅ Test Client demo data loaded successfully!")
                        st.info("View the data in the Dashboard or Raw Data tab")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading demo data: {e}")
            
            with col2:
                if test_count > 0:
                    password = st.text_input("Admin password to clear", type="password", key="admin_clear_test")
                    if st.button("🗑️ Clear Test Client Data", use_container_width=True, type="secondary", key="clear_test"):
                        if password == os.environ.get("ADMIN_PASSWORD", "admin123"):
                            deleted = clear_test_client_data()
                            st.success(f"✅ Cleared {deleted} Test Client records")
                            st.rerun()
                        else:
                            st.error("❌ Incorrect admin password")
                else:
                    st.info("No Test Client data to clear")


# ==================== MAIN APP ====================

def main():
    """Main application"""
    # Page config
    apply_theme()
    
    # Top banner - Clean layout
    st.title("🌍 ESG Intelligence Platform")
    st.caption("Corporate ESG Data Management & Analytics")
    
    # Navigation
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("🏠 Home", width="stretch"):
            st.session_state.current_page = 'Home'
    
    with col2:
        if st.button("📤 Upload Data", width="stretch"):
            st.session_state.current_page = 'Data Upload'
    
    with col3:
        if st.button("📊 Dashboard", width="stretch"):
            st.session_state.current_page = 'Dashboard'
    
    with col4:
        if st.button("📄 Reports", width="stretch"):
            st.session_state.current_page = 'Reports'
    
    with col5:
        if st.button("⚙️ Management", width="stretch"):
            st.session_state.current_page = 'Management'
    
    st.divider()
    
    # Route to current page
    page = st.session_state.current_page
    
    if page == 'Home':
        page_home()
    elif page == 'Data Upload':
        page_upload_data()
    elif page == 'Dashboard':
        page_dashboard()
    elif page == 'Reports':
        page_reports()
    elif page == 'Management':
        page_management()


if __name__ == "__main__":
    main()
