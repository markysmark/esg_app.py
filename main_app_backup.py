import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from fpdf import FPDF
import json
import os
from theme import apply_theme, brand_palette # Ensure theme.py exists 

# --- 1. DATABASE & CONFIG  ---
Base = declarative_base()
engine = create_engine('sqlite:///jpc_esg_intelligence.db')
Session = sessionmaker(bind=engine)
session = Session()

class ESGEntry(Base):
    __tablename__ = 'esg_master'
    id = Column(Integer, primary_key=True)
    client = Column(String) # 
    agent = Column(String); building = Column(String) # [cite: 2]
    waste_tonnes = Column(Float, default=0.0)
    employee_count = Column(Integer, default=0)
    hours_worked = Column(Float, default=0.0)
    chem_litres = Column(Float, default=0.0)
    eco_chem_pct = Column(Float, default=0.0)
    energy_kwh = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)

# --- 1C. DUMMY DATA SUPPORT ---
DUMMY_FILE = "dummy_toggle.json"
# admin password may be overridden by environment (useful on hosted platforms)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # simple default; change in production

def is_dummy_enabled():
    """Return True if the dummy data toggle is currently enabled."""
    if os.path.exists(DUMMY_FILE):
        try:
            with open(DUMMY_FILE, 'r') as f:
                return json.load(f).get('enabled', False)
        except Exception:
            return False
    return False


def set_dummy_enabled(val: bool):
    """Write the toggle state to disk."""
    with open(DUMMY_FILE, 'w') as f:
        json.dump({'enabled': val}, f)


def load_dummy_entries(client, agent, count=5):
    """Inject a small set of realistic-looking ESGEntry rows for testing.

    This helper is intentionally idempotent: running it multiple times simply adds
    more rows so the behaviour is obvious when the toggle is active.  After
    populating data we automatically disable the toggle to avoid accidental
    reuse; re‑enabling requires the admin password.
    """
    for i in range(count):
        e = ESGEntry(
            client=client,
            agent=agent,
            building=f"Dummy Building {i+1}",
            waste_tonnes=round(1 + i * 0.5, 1),
            energy_kwh=round(1000 + i * 200),
            chem_litres=round(10 + i * 2),
            eco_chem_pct=80.0,
            employee_count=50 + i * 5,
            hours_worked=2000 + i * 100,
            timestamp=datetime.utcnow()
        )
        session.add(e)
    session.commit()
    log_action('', 'system', f"Loaded {count} dummy entries for {agent}", status="dummy")
    # disable toggle automatically once used
    set_dummy_enabled(False)

# --- reporting models ---
class ReportRun(Base):
    __tablename__ = 'report_runs'
    id = Column(Integer, primary_key=True)
    report_type = Column(String)                # monthly/quarterly/on-demand
    scope_entity = Column(String)              # building/agent/portfolio
    filters = Column(Text)                      # JSON-encoded filter definitions
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    scoring_version = Column(String)
    file_reference = Column(String)             # path or blob ref
    snapshot_ids = Column(Text)                 # JSON list of snapshot ids
    created_at = Column(DateTime, default=datetime.utcnow)

# additional stub models for later expansion
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

class ObligationStatus(Base):
    __tablename__ = 'obligation_statuses'
    id = Column(Integer, primary_key=True)
    building = Column(String)
    obligation = Column(String)
    status = Column(String)  # Complete / In Progress / Missing Evidence / Overdue
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

# --- 1B. CLIENTS & AGENTS MANAGEMENT ---
CLIENTS_FILE = "clients_agents.json"

def load_clients_data():
    """Load clients and agents from JSON file"""
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, 'r') as f:
            return json.load(f)
    else:
        # Default data with top five UK managing agents included, plus sample buildings
        default_data = {
            "UK Top Agents": {"Agents": ["CBRE", "Savills", "JLL", "Knight Frank", "Cushman & Wakefield"],
                                "Buildings": ["One Churchill Place","Centre Point","30 St Mary Axe","Cheapside House","The Shard"]},
            "British Land": {"Agents": ["CBRE", "Savills"], "Buildings": ["The Leadenhall Building", "Broadgate Tower"]},
            "Landsec": {"Agents": ["Knight Frank"], "Buildings": ["20 Fenchurch Street", "One New Change"]},
            "Mitsubishi Estate": {"Agents": ["JLL"], "Buildings": ["8 Bishopsgate"]}
        }
        save_clients_data(default_data)
        return default_data

def save_clients_data(data):
    """Save clients and agents to JSON file"""
    with open(CLIENTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Initialize session state for clients/agents
if 'clients_data' not in st.session_state:
    st.session_state.clients_data = load_clients_data()

# --- reporting helpers (moved up so sidebar can call them) ---
def grade_data_quality(client, agent=None, building=None):
    """Compute a simple data quality score for the given scope.

    - **current_data_pct**: percentage of expected metrics present in the
      latest entry for the scope.
    - **obligations_with_evidence_pct**: a proxy based on the number of
      evidence documents available (assumes 5 documents == 100%).
    - **avg_confidence**: decreases with age of the most recent entry, from 1.0
      for data <30 days old to 0.0 for data >365 days old.
    - **grade**: letter grade based on thresholds for the other metrics.
    """
    # narrow entries according to scope
    q = session.query(ESGEntry)
    if building:
        q = q.filter(ESGEntry.building == building)
    elif agent:
        q = q.filter(ESGEntry.agent == agent)
    elif client:
        q = q.filter(ESGEntry.client == client)
    entries = q.all()

    expected_fields = [
        'waste_tonnes', 'energy_kwh', 'chem_litres',
        'eco_chem_pct', 'employee_count', 'hours_worked'
    ]

    if entries:
        latest = max(entries, key=lambda e: e.timestamp or datetime.min)
        filled = sum(1 for f in expected_fields
                     if getattr(latest, f, None) not in (None, 0, "", 0.0))
        current_data_pct = int((filled / len(expected_fields)) * 100)
        # confidence based on age
        days = (datetime.utcnow() - latest.timestamp).days if latest.timestamp else 365
        if days <= 30:
            avg_confidence = 1.0
        else:
            avg_confidence = max(0.0, 1.0 - (days / 365.0))
    else:
        current_data_pct = 0
        avg_confidence = 0.0

    # evidence count for obligations score
    evidence_count = 0
    if building:
        evidence_count = session.query(EvidenceRegister).filter(
            EvidenceRegister.building == building
        ).count()
    elif agent:
        blds = [e.building for e in entries if e.building]
        evidence_count = session.query(EvidenceRegister).filter(
            EvidenceRegister.building.in_(blds)
        ).count() if blds else 0
    elif client:
        evidence_count = session.query(EvidenceRegister).join(
            ESGEntry, ESGEntry.building == EvidenceRegister.building
        ).filter(ESGEntry.client == client).count()

    obligations_with_evidence_pct = min(100, evidence_count * 20)

    # derive grade
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


def create_report_run(report_type, scope_entity, filters, start, end, scoring_ver, snapshots):
    new = ReportRun(
        report_type=report_type,
        scope_entity=scope_entity,
        filters=json.dumps(filters),
        period_start=start,
        period_end=end,
        scoring_version=scoring_ver,
        snapshot_ids=json.dumps(snapshots or [])
    )
    session.add(new)
    session.commit()
    return new


def log_action(building, owner, action, due_date=None, status=None):
    """Record an action/audit event in the database.

    The `building` field may be left blank for portfolio-level events.
    """
    al = ActionLog(
        building=building or '',
        owner=owner,
        action=action,
        due_date=due_date,
        status=status or ''
    )
    session.add(al)
    session.commit()
    return al


def compute_esg_scores(entry: ESGEntry):
    """More nuanced ESG scoring based on individual components and evidence.

    Environmental score is the average of a waste score and an energy score,
    each normalised to 0–100; a small bonus is added for the eco-chemical
    percentage.  Social score is derived from hours worked per employee with a
    bonus for larger headcounts.  Governance is built from the eco percentage
    plus a small reward for uploaded evidence documents.  The final ESG score
    is a weighted average (E:50%, S:30%, G:20%).
    """
    if not entry:
        return 0.0, 0.0, 0.0, 0.0

    # environmental sub-scores
    waste = float(entry.waste_tonnes or 0.0)
    energy = float(entry.energy_kwh or 0.0)
    # waste: 0 tonnes -> 100, 20+ tonnes -> 0
    waste_score = max(0.0, 100.0 - (waste / 20.0) * 100.0)
    # energy: 0 kWh -> 100, 20k+ kWh -> 0
    energy_score = max(0.0, 100.0 - (energy / 20000.0) * 100.0)
    chem_bonus = min(10.0, float(entry.eco_chem_pct or 0.0) * 0.1)
    e = (waste_score + energy_score) / 2.0 + chem_bonus

    # social score
    emp = max(1.0, float(entry.employee_count or 0))
    hrs = float(entry.hours_worked or 0.0)
    hrs_per_emp = hrs / emp
    # desired ~40 hours per week => 2080 per year; use 40 as scale
    s = min(100.0, (hrs_per_emp / 40.0) * 100.0 + min(emp, 100.0) / 100.0 * 10.0)

    # governance score includes evidence count
    eco_pct = float(entry.eco_chem_pct or 0.0)
    base = 50.0 + eco_pct * 0.3
    evidence_count = session.query(EvidenceRegister).filter(
        EvidenceRegister.building == entry.building
    ).count() if entry.building else 0
    g = base + min(20.0, evidence_count * 2.0)

    def clamp(v):
        return max(0.0, min(100.0, round(v, 1)))

    e = clamp(e)
    s = clamp(s)
    g = clamp(g)
    overall = round((e * 0.50) + (s * 0.30) + (g * 0.20), 1)
    return e, s, g, overall


def create_score_snapshot(client, agent=None, building=None, period_start=None, period_end=None, period_label=None):
    """Create a snapshot using entries within the given period (if provided).

    If `period_start` and `period_end` are provided they will be used to filter
    ESGEntry records; otherwise the latest available entry is used.
    """
    q = session.query(ESGEntry)
    if building:
        q = q.filter(ESGEntry.building == building)
    elif agent:
        q = q.filter(ESGEntry.agent == agent)
    elif client:
        q = q.filter(ESGEntry.client == client)

    # apply period filtering when dates provided
    if period_start is not None and period_end is not None:
        # ensure we compare datetimes
        start_dt = datetime.combine(period_start, datetime.min.time()) if hasattr(period_start, 'year') else period_start
        end_dt = datetime.combine(period_end, datetime.max.time()) if hasattr(period_end, 'year') else period_end
        q = q.filter(ESGEntry.timestamp >= start_dt, ESGEntry.timestamp <= end_dt)

    latest = q.order_by(ESGEntry.timestamp.desc()).first()

    if not latest:
        # no data: create a low-confidence empty snapshot
        snap = ScoreSnapshot(client=client or '', agent=agent or '', building=building or '', esg_score=0.0,
                             e_score=0.0, s_score=0.0, g_score=0.0, period=period_label or '')
    else:
        e, s, g, esg = compute_esg_scores(latest)
        snap = ScoreSnapshot(client=latest.client or client or '', agent=latest.agent or agent or '', building=latest.building or building or '',
                             esg_score=esg, e_score=e, s_score=s, g_score=g, period=period_label or '')
    session.add(snap)
    session.commit()
    return snap


def generate_report_files(report_run_id):
    """Assemble HTML and PDF for a given ReportRun and save files, return paths."""
    rr = session.query(ReportRun).get(report_run_id)
    if not rr:
        raise ValueError("ReportRun not found")
    filters = json.loads(rr.filters or '{}')
    client = filters.get('client')
    agent = filters.get('agent')
    building = filters.get('building')

    # create a snapshot for the report
    snap = create_score_snapshot(client=client, agent=agent, building=building, period_start=rr.period_start, period_end=rr.period_end, period_label=f"{rr.period_start} to {rr.period_end}")

    # Data quality
    dq = grade_data_quality(client, agent, building)

    # Build HTML
    html = []
    html.append(f"<h1>Report: {rr.report_type} - {rr.scope_entity}</h1>")
    html.append(f"<h2>Scope: {client} / {agent} / {building}</h2>")
    html.append("<h3>Executive Summary</h3>")
    html.append(f"<p>Overall ESG score: <strong>{snap.esg_score}</strong> (E:{snap.e_score} S:{snap.s_score} G:{snap.g_score})</p>")
    html.append("<h3>Scorecards</h3>")
    html.append("<ul>")
    html.append(f"<li>E: {snap.e_score}</li>")
    html.append(f"<li>S: {snap.s_score}</li>")
    html.append(f"<li>G: {snap.g_score}</li>")
    html.append("</ul>")

    html.append("<h3>Compliance & Obligations (sample)</h3>")
    obs = session.query(ObligationStatus).filter(ObligationStatus.building == building).all() if building else []
    if obs:
        html.append('<table border="1"><tr><th>Obligation</th><th>Status</th><th>Due</th></tr>')
        for o in obs:
            html.append(f"<tr><td>{o.obligation}</td><td>{o.status}</td><td>{o.due_date}</td></tr>")
        html.append('</table>')
    else:
        html.append('<p>No obligation records for this scope.</p>')

    html.append('<h3>People & Wellbeing</h3>')
    html.append(f"<p>Wellbeing index (proxy): {snap.s_score}</p>")

    html.append('<h3>Actions</h3>')
    acts = session.query(ActionLog).filter(ActionLog.building == building).all() if building else []
    if acts:
        html.append('<ul>')
        for a in acts:
            html.append(f"<li>{a.status} - {a.action} (owner: {a.owner}, due: {a.due_date})</li>")
        html.append('</ul>')
    else:
        html.append('<p>No open actions for this period.</p>')

    html.append('<h3>Data Quality</h3>')
    html.append(f"<p>Grade: {dq['grade']}; Current data %: {dq['current_data_pct']}%" +
                f"; Evidence coverage: {dq['obligations_with_evidence_pct']}%" +
                f"; Confidence: {dq['avg_confidence']}</p>")

    # write HTML file
    os.makedirs('reports', exist_ok=True)
    html_path = os.path.join('reports', f'report_{rr.id}.html')
    with open(html_path, 'w') as f:
        f.write('\n'.join(html))

    # create a simple PDF
    pdf_path = os.path.join('reports', f'report_{rr.id}.pdf')
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"Report: {rr.report_type} - {rr.scope_entity}", ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.ln(4)
    pdf.multi_cell(0, 6, f"Scope: {client} / {agent} / {building}")
    pdf.ln(2)
    pdf.multi_cell(0, 6, f"Executive summary: Overall ESG score {snap.esg_score} (E:{snap.e_score} S:{snap.s_score} G:{snap.g_score})")
    pdf.ln(4)
    pdf.multi_cell(0, 6, f"Data quality: Grade {dq['grade']}, current data % {dq['current_data_pct']}, "
                           f"evidence coverage {dq['obligations_with_evidence_pct']}%, "
                           f"confidence {dq['avg_confidence']}\n")
    pdf.output(pdf_path)

    # update report run
    rr.file_reference = pdf_path
    session.add(rr)
    session.commit()
    return html_path, pdf_path

# --- 2. APP UI SETUP [cite: 2] ---
st.set_page_config(page_title="JPC Portfolio Intelligence", layout="wide")
apply_theme()

# Scrolling Banner [cite: 2, 3]
initiatives = [
    "🚀 UK SRS standards finalized Feb 2026", 
    "⚠️ EPC Reform H2 2026: Non-compliant assets face restricted leasing",
    "🧪 Probiotic cleaning: Driving 40% improvement in IAQ Social scores"
]
st.markdown(f'<div style="background:{brand_palette["brand_primary"]};color:{brand_palette["brand_accent"]};padding:10px;overflow:hidden;white-space:nowrap;"><marquee scrollamount="5">{" &nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp; ".join(initiatives)}</marquee></div>', unsafe_allow_html=True)

# --- 3. SIDEBAR NAVIGATION & MODULAR SETTINGS [cite: 3] ---
with st.sidebar:
    st.image("https://jpcbysamsic.uk/wp-content/uploads/2021/05/jpc-logo-gold.png", width=140)
    
    # Choose mode in sidebar (selection vs management)
    sidebar_mode = st.radio("Mode", ["Selection", "Manage"], index=0)
    
    if sidebar_mode == "Selection":
        st.header("⚙️ Oversight Settings")
        active_mods = st.multiselect("Enable Strategic Modules", 
                                     ["Waste Tracking", "Chemical Purity", "Energy/EPC", "Carbon & ROI", "Social Value"],
                                     default=["Waste Tracking", "Social Value"]) # [cite: 4]
        
        st.divider()
        # client selection with inline add
        client_list = list(st.session_state.clients_data.keys())
        client_sel = st.selectbox("Client", client_list)
        col1, col2 = st.columns([3,1])
        new_client = col1.text_input("New client", key="new_client_inline")
        if col2.button("+", key="add_client_inline"):
            if new_client:
                if new_client not in st.session_state.clients_data:
                    st.session_state.clients_data[new_client] = {"Agents": [], "Buildings": []}
                    save_clients_data(st.session_state.clients_data)
                    st.success(f"Client '{new_client}' added.")
                    st.experimental_rerun()
                else:
                    st.error("Client already exists.")
            else:
                st.warning("Enter a name first.")

        # agent selection with inline add
        agent_list = st.session_state.clients_data[client_sel].get("Agents", [])
        agent_sel = st.selectbox("Managing Agent", agent_list if agent_list else ["<no agents>"], key="agent_select")
        if agent_sel == "<no agents>":
            agent_sel = ""
        # free‑text override for agent name
        agent_manual = st.text_input("Agent (free text)", key="agent_manual")
        col1, col2 = st.columns([3,1])
        new_agent = col1.text_input("New agent", key="new_agent_inline")
        if col2.button("+", key="add_agent_inline"):
            if new_agent:
                if new_agent not in agent_list:
                    st.session_state.clients_data[client_sel]["Agents"].append(new_agent)
                    save_clients_data(st.session_state.clients_data)
                    st.success(f"Agent '{new_agent}' added to {client_sel}.")
                    st.experimental_rerun()
                else:
                    st.error("Agent already exists for this client.")
            else:
                st.warning("Enter a name first.")

        # select building asset before data entry
        building_list = st.session_state.clients_data[client_sel].get("Buildings", [])
        building_sel = st.selectbox("Building Asset", ["-- Portfolio Summary --"] + (building_list if building_list else []))
        col1, col2 = st.columns([3,1])
        new_building = col1.text_input("New building", key="new_building_inline")

        # --- data entry form in sidebar expander ---
        with st.expander("📝 Save Data"):
            if building_sel != "-- Portfolio Summary --":
                with st.form("pulse_entry", clear_on_submit=True):
                    st.subheader("📝 Monthly Pulse")
                    w = st.number_input("Waste (Tonnes)", 0.0, key="w_input")
                    staff = st.number_input("Staff Count", 0, key="staff_input")
                    hrs = st.number_input("Total Hours", 0.0, key="hrs_input")
                    c = st.number_input("Chemicals (L)", 0.0, key="chem_input")
                    e_pct = st.number_input("Eco Chemicals %", 0.0, key="eco_input")
                    nrg = st.number_input("Energy (kWh)", 0.0, key="nrg_input")
                    if st.form_submit_button("💾 Save & Sync Dashboard"):
                        chosen_agent = agent_manual.strip() or agent_sel
                        # if manual agent provided, add to client list for persistence
                        if agent_manual and agent_manual.strip():
                            if agent_manual not in st.session_state.clients_data[client_sel]["Agents"]:
                                st.session_state.clients_data[client_sel]["Agents"].append(agent_manual)
                                save_clients_data(st.session_state.clients_data)
                        new_entry = ESGEntry(client=client_sel,
                                             agent=chosen_agent,
                                             building=building_sel,
                                             waste_tonnes=w,
                                             employee_count=staff,
                                             hours_worked=hrs,
                                             chem_litres=c,
                                             eco_chem_pct=e_pct,
                                             energy_kwh=nrg)
                        session.add(new_entry)
                        session.commit()
                        st.success("Synchronized Successfully.")
                        st.experimental_rerun()
            else:
                st.info("Select a building asset before saving data.")
        if col2.button("+", key="add_building_inline"):
            if new_building:
                if new_building not in st.session_state.clients_data[client_sel]["Buildings"]:
                    st.session_state.clients_data[client_sel]["Buildings"].append(new_building)
                    save_clients_data(st.session_state.clients_data)
                    st.success(f"Building '{new_building}' added to {client_sel}.")
                    st.experimental_rerun()
                else:
                    st.error("Building already exists for this client.")
            else:
                st.warning("Enter a name first.")
        # --- reporting controls (selection mode) ---
        st.divider()
        st.header("📄 Generate Report")
        rpt_type = st.selectbox("Report Type", ["Monthly", "Quarterly", "On-demand"], index=0)
        scope_choice = st.selectbox("Scope", ["Building", "Agent", "Portfolio"])
        period_start = st.date_input("Period start", key="rstart")
        period_end = st.date_input("Period end", key="rend")
        if st.button("Generate Report"):
            rr = create_report_run(
                report_type=rpt_type,
                scope_entity=scope_choice,
                filters={"client": client_sel, "agent": agent_sel, "building": building_sel},
                start=period_start,
                end=period_end,
                scoring_ver="1.0",
                snapshots=[]
            )
            st.info("Generating report... this may take a few seconds")
            try:
                html_path, pdf_path = generate_report_files(rr.id)
                st.success(f"Report generated: {pdf_path}")
                with open(pdf_path, 'rb') as f:
                    st.download_button("Download PDF", f.read(), file_name=os.path.basename(pdf_path))
                st.markdown(f"[Open HTML report]({html_path})")
            except Exception as e:
                st.error(f"Report generation failed: {e}")
    else:
        st.header("➕ Add & Manage")
        management_option = st.radio("What would you like to do?", 
                                     ["Add New Client", "Add Agent to Client", "Add Building to Agent"])
        
        if management_option == "Add New Client":
            st.subheader("➕ New Client")
            new_client_name = st.text_input("Client Name", placeholder="e.g., Workspace Group")
            if st.button("✅ Create Client"):
                if new_client_name and new_client_name not in st.session_state.clients_data:
                    st.session_state.clients_data[new_client_name] = {"Agents": [], "Buildings": []}
                    save_clients_data(st.session_state.clients_data)
                    log_action('', 'system', f"Client '{new_client_name}' created")
                    st.success(f"✅ Client '{new_client_name}' created!")
                    st.rerun()
                elif new_client_name in st.session_state.clients_data:
                    st.error("❌ Client already exists")
                else:
                    st.warning("⚠️ Please enter a client name")
        
        elif management_option == "Add Agent to Client":
            st.subheader("➕ Add Managing Agent")
            target_client = st.selectbox("Select Client", list(st.session_state.clients_data.keys()), key="agent_client_sel")
            new_agent_name = st.text_input("Agent Name", placeholder="e.g., Savills")
            if st.button("✅ Add Agent"):
                if new_agent_name and new_agent_name not in st.session_state.clients_data[target_client]["Agents"]:
                    st.session_state.clients_data[target_client]["Agents"].append(new_agent_name)
                    save_clients_data(st.session_state.clients_data)
                    log_action('', 'system', f"Agent '{new_agent_name}' added to client '{target_client}'")
                    st.success(f"✅ Agent '{new_agent_name}' added to {target_client}!")
                    st.rerun()
                elif new_agent_name in st.session_state.clients_data[target_client]["Agents"]:
                    st.error("❌ Agent already exists for this client")
                else:
                    st.warning("⚠️ Please enter an agent name")
        
        elif management_option == "Add Building to Agent":
            st.subheader("➕ Add Building Asset")
            building_client = st.selectbox("Select Client", list(st.session_state.clients_data.keys()), key="building_client_sel")
            building_agent = st.selectbox("Select Agent", st.session_state.clients_data[building_client]["Agents"], key="building_agent_sel")
            new_building_name = st.text_input("Building Name", placeholder="e.g., The Shard")
            if st.button("✅ Add Building"):
                if new_building_name and new_building_name not in st.session_state.clients_data[building_client]["Buildings"]:
                    st.session_state.clients_data[building_client]["Buildings"].append(new_building_name)
                    save_clients_data(st.session_state.clients_data)
                    log_action(new_building_name, 'system', f"Building '{new_building_name}' added to client '{building_client}'")
                    st.success(f"✅ Building '{new_building_name}' added!")
                    st.rerun()
                elif new_building_name in st.session_state.clients_data[building_client]["Buildings"]:
                    st.error("❌ Building already exists")
                else:
                    st.warning("⚠️ Please enter a building name")
        
        # Display current structure
        st.divider()
        st.subheader("📊 Current Structure")
        for client, data in st.session_state.clients_data.items():
            with st.expander(f"📋 {client}"):
                st.write(f"**Agents:** {', '.join(data['Agents']) if data['Agents'] else 'None'}")
                st.write(f"**Buildings:** {', '.join(data['Buildings']) if data['Buildings'] else 'None'}")

        # --- Dummy data toggle section ---
        st.divider()
        st.subheader("🐑 Dummy Data")
        enabled = is_dummy_enabled()
        st.write("Status:", "✅ Enabled" if enabled else "❌ Disabled")
        if enabled:
            if st.button("📥 Load Sample Dummy Entries (CBRE)"):
                load_dummy_entries(client='UK Top Agents', agent='CBRE')
                st.success("Dummy data loaded for CBRE.")
                st.experimental_rerun()
            if st.button("🚫 Disable Dummy Data"):
                set_dummy_enabled(False)
                st.success("Dummy data disabled. Admin required to enable.")
                st.experimental_rerun()
        else:
            pw = st.text_input("Admin password to enable", type="password")
            if st.button("Enable Dummy Data"):
                if pw == ADMIN_PASSWORD:
                    set_dummy_enabled(True)
                    st.success("Dummy data can now be loaded.")
                    st.experimental_rerun()
                else:
                    st.error("Incorrect password")

# only render dashboard if in Selection mode
if sidebar_mode == "Selection":
    # NOTE: data entry form is now located in sidebar under 'Save Data' expander
    
    # report generation UI (duplicate sidebar control for convenience)
    st.divider()
    st.header("📄 Generate Report")
    rpt_type = st.selectbox("Report Type", ["Monthly","Quarterly","On-demand"], index=0)
    scope_choice = st.selectbox("Scope", ["Building","Agent","Portfolio"])
    period_start = st.date_input("Period start", key="rstart")
    period_end = st.date_input("Period end", key="rend")
    if st.button("Generate Report"):
        rr = create_report_run(
            report_type=rpt_type,
            scope_entity=scope_choice,
            filters={"client": client_sel, "agent": agent_sel, "building": building_sel},
            start=period_start,
            end=period_end,
            scoring_ver="1.0",
            snapshots=[]
        )
        st.info("Generating report... this may take a few seconds")
        try:
            html_path, pdf_path = generate_report_files(rr.id)
            st.success(f"Report generated: {pdf_path}")
            with open(pdf_path, 'rb') as f:
                st.download_button("Download PDF", f.read(), file_name=os.path.basename(pdf_path))
            st.markdown(f"[Open HTML report]({html_path})")
        except Exception as e:
            st.error(f"Report generation failed: {e}")
# --- 4. DASHBOARD VIEWS [cite: 9] ---
# render main area only when selection mode active
if sidebar_mode == "Selection":
    # report generation UI (duplicate sidebar control for convenience)
    st.divider()
    st.header("📄 Generate Report")
    rpt_type = st.selectbox("Report Type", ["Monthly","Quarterly","On-demand"], index=0)
    scope_choice = st.selectbox("Scope", ["Building","Agent","Portfolio"])
    period_start = st.date_input("Period start", key="rstart")
    period_end = st.date_input("Period end", key="rend")
    if st.button("Generate Report"):
        rr = create_report_run(
            report_type=rpt_type,
            scope_entity=scope_choice,
            filters={"client": client_sel, "agent": agent_sel, "building": building_sel},
            start=period_start,
            end=period_end,
            scoring_ver="1.0",
            snapshots=[]
        )
        st.info("Generating report... this may take a few seconds")
        try:
            html_path, pdf_path = generate_report_files(rr.id)
            st.success(f"Report generated: {pdf_path}")
            with open(pdf_path, 'rb') as f:
                st.download_button("Download PDF", f.read(), file_name=os.path.basename(pdf_path))
            st.markdown(f"[Open HTML report]({html_path})")
        except Exception as e:
            st.error(f"Report generation failed: {e}")

    db_data = pd.read_sql(session.query(ESGEntry).filter(ESGEntry.client == client_sel).statement, engine)

    # export panel for filtered data
    st.divider()
    st.subheader("📤 Export Raw Data")
    if not db_data.empty:
        if building_sel and building_sel != "-- Portfolio Summary --":
            filt_df = db_data[db_data['building'] == building_sel]
        elif agent_sel:
            filt_df = db_data[db_data['agent'] == agent_sel]
        else:
            filt_df = db_data
        csv = filt_df.to_csv(index=False)
        st.download_button("Download CSV", csv, file_name="export.csv")
        import io
        xlsx = io.BytesIO()
        filt_df.to_excel(xlsx, index=False, engine='xlsxwriter')
        st.download_button("Download Excel", xlsx.getvalue(), file_name="export.xlsx")
    else:
        st.info("No data available to export yet.")

    if building_sel == "-- Portfolio Summary --":
        st.title(f"📈 {client_sel}: Portfolio Strategy")
        if not db_data.empty:
            st.subheader("Strategic Agent Performance (Eco-Purity x Waste)")
            fig = px.scatter(db_data, x="eco_chem_pct", y="waste_tonnes", size="employee_count", 
                             color="agent", hover_name="building", color_discrete_sequence=[brand_palette['brand_accent'], "#5C6B7A"])
            st.plotly_chart(fig, width='stretch') # [cite: 10]
        else: st.info("Select an asset or input data to begin.")

    else:
        st.title(f"🛡️ {building_sel} Intelligence")
        site_data = db_data[db_data['building'] == building_sel]
        
        tab1, tab2, tab3, tab4 = st.tabs(["🏗️ Asset Deep-Dive", "⚖️ Materiality Matrix", "💰 ROI & Carbon", "📚 Document Library"])
        
        with tab1:
            if not site_data.empty:
                latest = site_data.iloc[-1]
                # data quality metric
                dq = grade_data_quality(client_sel, agent_sel, building_sel)
                st.metric("Data Quality", dq['grade'], delta=f"{dq['current_data_pct']}% complete")

                c1, c2, c3, c4 = st.columns(4) # [cite: 11]
                if "Waste Tracking" in active_mods: c1.metric("Oct 2026 Fine Risk", "£150,000", delta="Critical")
                if "Carbon & ROI" in active_mods: c2.metric("Carbon Liability", f"£{latest['employee_count'] * 154:,.0f}")
                if "Chemical Purity" in active_mods: c3.metric("Eco-Shift", f"{latest['eco_chem_pct']}%")
                if "Social Value" in active_mods: c4.metric("Social Score", f"{latest['hours_worked']/100:,.0f}")
                
                st.divider() # [cite: 12]
                st.subheader("📋 Board Summary")
                st.info(f"Asset performance shows a high Social Value score due to {latest['hours_worked']:,} hours of verified local labor. Focus for Q3 2026: Reducing waste output to avoid £150k regulatory fines.") # [cite: 13]
            else: st.warning("Please submit a 'Monthly Pulse' entry in the sidebar.")
        
        with tab4:
            st.subheader("Audit-Ready Document Library")
            if building_sel == "-- Portfolio Summary --":
                st.info("Select a building to upload or view evidence.")
            else:
                uploaded = st.file_uploader("Upload Evidence (ISO, Waste Notes, Certs)", key=f"evidence_uploader_{building_sel}")
                if uploaded is not None:
                    # persist file
                    os.makedirs('evidence', exist_ok=True)
                    safe_name = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{uploaded.name}"
                    path = os.path.join('evidence', safe_name)
                    with open(path, 'wb') as out:
                        out.write(uploaded.getbuffer())
                    # record in EvidenceRegister
                    er = EvidenceRegister(building=building_sel, item_type=uploaded.type or uploaded.name.split('.')[-1], reference=path)
                    session.add(er)
                    session.commit()
                    st.success(f"Evidence '{uploaded.name}' uploaded and recorded.")

                # list evidence for this building
                evs = session.query(EvidenceRegister).filter(EvidenceRegister.building == building_sel).order_by(EvidenceRegister.uploaded_at.desc()).all()
                if evs:
                    rows = []
                    for e in evs:
                        rows.append({"Document": os.path.basename(e.reference), "Uploaded At": e.uploaded_at, "Reference": e.reference})
                    st.table(pd.DataFrame(rows))
                else:
                    st.info("No evidence uploaded for this asset yet.")
        
        # new audit tab
        with st.expander("📝 Audit Trail"):
            if building_sel == "-- Portfolio Summary --":
                st.info("Select an asset to view its audit log.")
            else:
                logs = session.query(ActionLog).filter(ActionLog.building == building_sel).order_by(ActionLog.id.desc()).all()
                if logs:
                    df_logs = pd.DataFrame([{
                        "Action": l.action,
                        "Owner": l.owner,
                        "Status": l.status,
                        "Due": l.due_date,
                        "Logged": l.id
                    } for l in logs])
                    st.table(df_logs)
                    csv_logs = df_logs.to_csv(index=False)
                    st.download_button("Export Audit Log CSV", csv_logs, file_name="audit_log.csv")
                else:
                    st.info("No audit events recorded for this building.")
else:
    st.info("Switch to Selection mode to interact with clients, agents, and buildings.")