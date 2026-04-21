"""
ESG Intelligence Platform - Main Application
Comprehensive ESG data management, analysis, and reporting system
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import json
import os
import smtplib
import hashlib
import hmac
from email.message import EmailMessage
from theme import apply_theme, brand_palette, render_sidebar_logo
import threading
import time

def _utcnow() -> datetime:
    """Return the current UTC time as a naive datetime.

    Replaces the deprecated ``datetime.utcnow()`` while keeping the same
    naive-datetime contract expected by existing database columns and
    comparison logic throughout the application.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    timestamp = Column(DateTime, default=_utcnow)


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
    created_at = Column(DateTime, default=_utcnow)


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
    created_at = Column(DateTime, default=_utcnow)


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
    uploaded_at = Column(DateTime, default=_utcnow)


class EditHistory(Base):
    __tablename__ = 'edit_history'
    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer)
    editor = Column(String)
    changes = Column(Text)  # json
    approved_by = Column(String)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=_utcnow)


class ServiceLineConfig(Base):
    """Stores which service lines are active (in scope) for a given building."""
    __tablename__ = 'service_line_config'
    id = Column(Integer, primary_key=True)
    building = Column(String, index=True)
    service_line = Column(String)
    active = Column(Integer, default=1)  # 1 = active, 0 = inactive
    updated_at = Column(DateTime, default=_utcnow)


class CleaningKPI(Base):
    """Stores detailed cleaning ESG KPIs per building per period."""
    __tablename__ = 'cleaning_kpi'
    id = Column(Integer, primary_key=True)
    building = Column(String, index=True)
    period = Column(String)  # e.g. "2025-Q1"
    # Environmental
    chem_per_sqm = Column(Float, default=0.0)
    eco_chem_pct = Column(Float, default=0.0)
    water_per_site = Column(Float, default=0.0)
    waste_seg_accuracy = Column(Float, default=0.0)
    carbon_per_visit = Column(Float, default=0.0)
    microfibre_ratio = Column(Float, default=0.0)
    # Social
    staff_turnover_rate = Column(Float, default=0.0)
    training_hours = Column(Float, default=0.0)
    living_wage_pct = Column(Float, default=0.0)
    accident_freq_rate = Column(Float, default=0.0)
    absence_rate = Column(Float, default=0.0)
    client_satisfaction = Column(Float, default=0.0)
    # Governance
    audit_pass_rate = Column(Float, default=0.0)
    method_stmt_updates = Column(Float, default=0.0)
    sla_adherence = Column(Float, default=0.0)
    incident_report_hrs = Column(Float, default=0.0)
    subcontractor_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utcnow)


Base.metadata.create_all(engine)

# ==================== CLIENTS & AGENTS ====================
CLIENTS_FILE = "clients_agents.json"

# --- DUMMY DATA SUPPORT ---
DUMMY_FILE = "dummy_toggle.json"


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
    """Insert a batch of dummy ESGEntry rows for testing.

    After populating data the toggle is automatically cleared to avoid
    accidental repeated loads. The caller is responsible for any permissions
    or password checks (in the UI this is gated behind admin validation).
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
            timestamp=_utcnow()
        )
        session.add(e)
    session.commit()
    # record action using existing helper (log_action defined later in file)
    try:
        log_action('', 'system', f"Loaded {count} dummy entries for {agent}", status="dummy")
    except NameError:
        pass
    set_dummy_enabled(False)



def load_clients_data():
    """Load clients and agents from JSON file"""
    if os.path.exists(CLIENTS_FILE):
        with open(CLIENTS_FILE, 'r') as f:
            return json.load(f)
    else:
        # pre-populated clients data; users can add more clients via the UI
        default_data = {
            "Top Agents": {
                # This pseudo-client exists purely to list popular managing agents.
                # Users are free to add their own clients and then associate agents
                # with them using the "Add Items" tab.
                "Agents": [
                    "Savills – Global full-service property management, asset & investment managers.",
                    "CBRE – World’s largest commercial property services and management firm.",
                    "JLL – Major London and UK commercial management provider.",
                    "Knight Frank – Deep London commercial asset management and advisory network.",
                    "Cushman & Wakefield – Comprehensive property and facilities management in London.",
                    "Colliers – Data-led property management and advisory.",
                    "Avison Young – Property management plus leasing and investment services.",
                    "BNP Paribas Real Estate – European-scale management with UK/ London operations.",
                    "Lambert Smith Hampton – Leading commercial real estate manager across UK.",
                    "SHW – Manages commercial portfolios alongside residential.",
                    "Mellersh & Harding – London-centric commercial property management specialist.",
                    "TSP (The Service Providers) – Bespoke commercial asset & property management focused on tenant experience.",
                    "REM Limited – Asset & property management for premium London real estate (e.g., The Shard).",
                    "Telereal Trillium (TT Group) – Large UK property owner and manager with London portfolio.",
                    "Workspace Group – FTSE-listed commercial property manager focused on London SME space.",
                    "FirstPort – Major UK property services provider including commercial estate components (often mixed-use).",
                    "Crabtree Property Management – London property manager with residential & commercial interests.",
                    "RIB (Robert Irving Burns) – Commercial property management across central London.",
                    "Maunder Taylor – Specialist commercial manager across shops, offices, industrial.",
                    "Willmotts – Flexible commercial property management solutions.",
                    "Cluttons – UK commercial & residential property management and strategic asset advice.",
                    "Prime Property Management – London-oriented property management including commercial premises.",
                    "Anderson Wilde & Harris (AWH) – Property management specialists in London’s mixed-use sector.",
                    "Claridges Commercial – Firm with decades of commercial property management experience in London.",
                    "JCF Property Management – Long-standing London property manager including commercial.",
                    "Heritage Management Ltd – Member of industry institute with Greater London coverage.",
                    "Kennedy Mulcare Ltd – London firm listed with professional property institute directory.",
                    "Kingston Real Estate (Property Management) Ltd – Management firm listed in industry directory.",
                    "Gateway Property Management – Estate & property manager with operations serving London boroughs.",
                    "Cadmus Property – Bespoke property management services including mixed-use portfolios."
                ],
                "Buildings": []
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

if 'user' not in st.session_state:
    st.session_state.user = None
if 'user_role' not in st.session_state:
    st.session_state.user_role = None

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
        days = (_utcnow() - latest.timestamp).days if latest.timestamp else 365
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


# ----------------- ALERTS & AUTH HELPERS -----------------
ALERT_THRESHOLD = int(os.environ.get('ALERT_THRESHOLD', '50'))
STALE_DAYS = int(os.environ.get('DATA_STALE_DAYS', '90'))
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '25')) if os.environ.get('SMTP_PORT') else None
ALERT_RECIPIENT = os.environ.get('ALERT_RECIPIENT')


def _send_email(subject: str, body: str):
    if not SMTP_SERVER or not ALERT_RECIPIENT:
        return False
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = os.environ.get('ALERT_SENDER', 'noreply@example.com')
        msg['To'] = ALERT_RECIPIENT
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT or 25) as s:
            s.send_message(msg)
        return True
    except Exception:
        return False


def perform_quality_checks(send_email=True):
    """Compute quality issues and optionally send alerts. Returns dict of findings.

    This function is safe to call from a CLI/worker (doesn't require Streamlit UI).
    """
    findings = {'low_portfolio': None, 'stale_clients': []}
    try:
        p = grade_data_quality(None)
        pct = p.get('current_data_pct', 0)
        if pct < ALERT_THRESHOLD:
            findings['low_portfolio'] = pct
            if send_email:
                _send_email('ESG Platform: Low Data Quality', f'Portfolio completeness {pct}%')

        for client in load_clients_data().keys():
            q = session.query(ESGEntry).filter(ESGEntry.client == client).all()
            if not q:
                findings['stale_clients'].append((client, 'no data'))
                continue
            latest = max(q, key=lambda e: e.timestamp or datetime.min)
            days = (_utcnow() - (latest.timestamp or _utcnow())).days
            if days >= STALE_DAYS:
                findings['stale_clients'].append((client, days))
                if send_email:
                    _send_email('ESG Platform: Data Freshness Alert', f'{client}: {days} days since last data')
    except Exception:
        pass
    return findings


def check_quality_alerts():
    """UI wrapper: call the headless check and surface banners in Streamlit."""
    findings = perform_quality_checks(send_email=True)
    stale = findings.get('stale_clients', [])
    no_data = [c for c, d in stale if d == 'no data']
    stale_clients = [(c, d) for c, d in stale if d != 'no data']

    if no_data or stale_clients:
        parts = []
        if no_data:
            parts.append(f"{len(no_data)} clients have no data")
        if stale_clients:
            parts.append(f"{len(stale_clients)} clients with data older than {STALE_DAYS} days")
        summary = "; ".join(parts)
        st.info(f"Data freshness issues: {summary}")

        with st.expander("Show data freshness details", expanded=False):
            if no_data:
                st.write("Clients with no data:")
                for c in no_data:
                    st.write(f"- {c}")
            if stale_clients:
                st.write("Clients with stale data (days since last):")
                for c, d in stale_clients:
                    st.write(f"- {c}: {d} days")


# Simple user store / auth (opt-in, minimal)
USERS_FILE = os.environ.get('USERS_FILE', 'users.json')


def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f).get('users', {})
        except Exception:
            return {}
    return {}


def _verify_password(candidate: str, stored: str) -> bool:
    """Verify a candidate password against a stored credential string.

    Supported formats:
    - Plaintext (legacy): "secret"
    - SHA-256 digest: "sha256$<hex-digest>"
    """
    if not stored:
        return False
    if isinstance(stored, str) and stored.startswith("sha256$"):
        digest = hashlib.sha256((candidate or "").encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, stored.split("$", 1)[1])
    return hmac.compare_digest(candidate or "", str(stored))


def authenticate(username: str, password: str):
    users = load_users()
    admin_secret = os.environ.get('ADMIN_PASSWORD')
    # Admin login is only enabled when ADMIN_PASSWORD is explicitly configured.
    if username == 'admin' and admin_secret and _verify_password(password, admin_secret):
        return {'username': 'admin', 'role': 'admin'}
    if username in users:
        stored = users[username].get('password_hash') or users[username].get('password')
        if _verify_password(password, stored):
            return {'username': username, 'role': users[username].get('role', 'user')}
    return None


def is_authenticated() -> bool:
    return bool(st.session_state.get('user'))


def require_role(role: str):
    return st.session_state.get('user_role') == role


def require_admin_ui(message: str = "Admin only: sign in with an admin account.") -> bool:
    if require_role('admin'):
        return True
    st.error(message)
    return False


def require_auth_ui(message: str = "Sign in to continue.") -> bool:
    if is_authenticated():
        return True
    st.error(message)
    return False


def log_action(building, owner, action, due_date=None, status=None):
    """Log an action in the database"""
    al = ActionLog(building=building or '', owner=owner, action=action, due_date=due_date, status=status or '')
    session.add(al)
    session.commit()
    return al


def _ensure_clients_data_registered(entries: list) -> None:
    """Ensure every client, agent and building in *entries* appears in clients_agents.json.

    Each item in *entries* should be a dict with at least the keys ``client``,
    ``agent`` and ``building``.  Missing clients are created; missing agents and
    buildings are appended to the existing lists.  The file is only written when
    at least one change is required.
    """
    data = load_clients_data()
    changed = False
    for item in entries:
        client = item.get('client', '')
        agent = item.get('agent', '')
        building = item.get('building', '')
        if not client:
            continue
        if client not in data:
            data[client] = {'Agents': [], 'Buildings': []}
            changed = True
        if agent and agent not in data[client].get('Agents', []):
            data[client]['Agents'].append(agent)
            changed = True
        if building and building not in data[client].get('Buildings', []):
            data[client]['Buildings'].append(building)
            changed = True
    if changed:
        save_clients_data(data)


def _load_cleaning_kpi_demo_data(buildings: list, period: str = "2025-Q1") -> None:
    """Insert CleaningKPI demo records showing good cleaning performance for the given buildings.

    Values are set to exceed the 'green' RAG thresholds defined in service_lines.py so
    that the cleaning company is shown to have good performance in the dashboard RAG summary.
    Records are only inserted when no existing record exists for the same building/period.
    """
    good_performance_kpis = {
        # Environmental – all green
        "chem_per_sqm":        0.3,   # green: <= 0.5
        "eco_chem_pct":        88.0,  # green: >= 75
        "water_per_site":      35.0,  # green: <= 50
        "waste_seg_accuracy":  96.0,  # green: >= 95
        "carbon_per_visit":    3.0,   # green: <= 5
        "microfibre_ratio":    80.0,  # green: >= 75
        # Social – all green
        "staff_turnover_rate": 12.0,  # green: <= 20
        "training_hours":      36.0,  # green: >= 35
        "living_wage_pct":     100.0, # green: >= 100
        "accident_freq_rate":  0.2,   # green: <= 0.5
        "absence_rate":        3.5,   # green: <= 5
        "client_satisfaction": 8.5,   # green: >= 8
        # Governance – all green
        "audit_pass_rate":     93.0,  # green: >= 90
        "method_stmt_updates": 1.0,   # green: <= 2
        "sla_adherence":       97.0,  # green: >= 95
        "incident_report_hrs": 2.0,   # green: <= 4
        "subcontractor_score": 85.0,  # green: >= 80
    }

    for building in buildings:
        existing = (
            session.query(CleaningKPI)
            .filter(CleaningKPI.building == building, CleaningKPI.period == period)
            .first()
        )
        if not existing:
            kpi_row = CleaningKPI(
                building=building,
                period=period,
                **good_performance_kpis,
            )
            session.add(kpi_row)

    session.commit()


def load_savills_demo_data():
    """Load realistic demo data for Savills' managed buildings.

    Inserts 12 months of monthly historical records per building so that
    the dashboard Historical Trends chart has meaningful data to display.
    Each month's values trend slightly toward improvement over time to
    simulate a realistic ESG programme.
    """
    from dateutil.relativedelta import relativedelta

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

    # Number of months of history to generate (including the current month).
    # Must be >= 2 so that the improvement gradient calculation is well-defined.
    HISTORY_MONTHS = 12

    now = _utcnow()

    for data in demo_buildings:
        for month_offset in range(HISTORY_MONTHS - 1, -1, -1):
            record_date = now - relativedelta(months=month_offset)

            # Check if a record already exists for this building and month
            month_start = record_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_end = month_start + relativedelta(months=1)
            existing = session.query(ESGEntry).filter(
                ESGEntry.building == data['building'],
                ESGEntry.agent == 'Savills',
                ESGEntry.timestamp >= month_start,
                ESGEntry.timestamp < month_end
            ).first()

            if not existing:
                # Apply a small monthly improvement trend (older months are slightly worse).
                # month_offset 11 = 11 months ago (worst), 0 = current month (best).
                improvement = month_offset / (HISTORY_MONTHS - 1) if HISTORY_MONTHS > 1 else 0.0
                # Eco-chemical percentage floor: 50% reflects a realistic minimum programme baseline.
                ECO_CHEM_FLOOR = 50.0
                entry = ESGEntry(
                    client=data['client'],
                    agent=data['agent'],
                    building=data['building'],
                    waste_tonnes=round(data['waste_tonnes'] * (1 + improvement * 0.20), 2),
                    energy_kwh=round(data['energy_kwh'] * (1 + improvement * 0.15)),
                    chem_litres=round(data['chem_litres'] * (1 + improvement * 0.10), 1),
                    eco_chem_pct=round(max(ECO_CHEM_FLOOR, data['eco_chem_pct'] - improvement * 15), 1),
                    employee_count=data['employee_count'],
                    hours_worked=data['hours_worked'],
                    timestamp=record_date
                )
                session.add(entry)

    session.commit()

    # Seed CleaningKPI records for each Savills building showing good performance
    savills_buildings = [d['building'] for d in demo_buildings]
    _load_cleaning_kpi_demo_data(savills_buildings, period="2025-Q1")

    # Register all demo clients, agents and buildings in clients_agents.json so
    # they appear in every dropdown and selector immediately after loading.
    _ensure_clients_data_registered(demo_buildings)

    log_action('', 'system', 'Savills demo data loaded', status='demo')


def clear_savills_demo_data():
    """Clear all demo data for Savills (admin only)"""
    savills_buildings_q = (
        session.query(ESGEntry.building).filter(ESGEntry.agent == 'Savills')
    )
    session.query(CleaningKPI).filter(
        CleaningKPI.building.in_(savills_buildings_q)
    ).delete(synchronize_session=False)
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
                timestamp=_utcnow()
            )
            session.add(entry)
    
    session.commit()

    # Seed CleaningKPI records for each Test Client building showing good performance
    test_building_names = [d['building'] for d in test_buildings]
    _load_cleaning_kpi_demo_data(test_building_names, period="2025-Q1")

    # Register all demo clients, agents and buildings in clients_agents.json so
    # they appear in every dropdown and selector immediately after loading.
    _ensure_clients_data_registered(test_buildings)

    log_action('', 'system', 'Test Client demo data loaded', status='demo')


def clear_test_client_data():
    """Clear all demo data for Test Client (admin only)"""
    test_buildings_q = (
        session.query(ESGEntry.building).filter(ESGEntry.client == 'Test Client')
    )
    session.query(CleaningKPI).filter(
        CleaningKPI.building.in_(test_buildings_q)
    ).delete(synchronize_session=False)
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
    
    # compute overall data quality grade for portfolio
    quality = grade_data_quality(None)
    quality_grade = quality.get("grade", "F")
    quality_pct = quality.get("current_data_pct", 0)
    quality_conf = quality.get("avg_confidence", 0.0)
    
    with col1:
        st.metric("📊 Buildings", unique_buildings)
    with col2:
        st.metric("🏢 Clients", unique_clients)
    with col3:
        st.metric("👥 Managing Agents", unique_agents)
    with col4:
        st.metric("📈 Total Records", len(all_entries))
    # data quality metric
    st.metric("📋 Data Quality", quality_grade, delta=f"{quality_pct}% / conf {quality_conf}")

    st.divider()
    st.subheader("🔎 Quick Drilldowns")
    clients = list(st.session_state.clients_data.keys())
    if clients:
        cols = st.columns(3)
        for i, client in enumerate(clients):
            c = cols[i % 3]
            with c:
                if st.button(f"View {client}", key=f"drill_client_{i}"):
                    st.session_state.mgmt_client = client
                    st.session_state.current_page = 'Management'
                    st.rerun()
    else:
        st.info("No clients defined yet.")

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

    ### First-Run Checklist

    **1. Sign in** → Use the sidebar account panel  
    **2. Upload Data** → Import CSV/Excel ESG metrics  
    **3. Review Dashboard** → Confirm score and data quality trends  
    **4. Generate Report** → Create PDF/CSV/Excel outputs  
    **5. Manage Structure** → Add missing clients, agents, or buildings
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
        if st.button("📤 Upload Data", width="stretch", key="quick_upload"):
            st.session_state.current_page = 'Data Upload'
            st.rerun()
    
    with col2:
        if st.button("📊 View Dashboard", width="stretch", key="quick_dashboard"):
            st.session_state.current_page = 'Dashboard'
            st.rerun()
    
    with col3:
        if st.button("📄 Generate Report", width="stretch", key="quick_reports"):
            st.session_state.current_page = 'Reports'
            st.rerun()
    
    with col4:
        if st.button("⚙️ Manage Data", width="stretch", key="quick_management"):
            st.session_state.current_page = 'Management'
            st.rerun()


def page_help():
    """Display full user instructions.

    The content is drawn from the project README so that users can access
    installation and usage guidance without leaving the Streamlit interface.
    """
    quickstart = (
        "## Quickstart\n"
        "1. Sign in from the sidebar account panel.\n"
        "2. Open **Upload Data** and import a CSV/Excel file.\n"
        "3. Review **Dashboard** metrics.\n"
        "4. Use **Reports** to export PDF/CSV/Excel output.\n\n"
    )
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            readme = f.read()
    except Exception:
        readme = "Unable to load instructions."
    # Streamlit will emit warnings about missing ScriptRunContext when
    # invoked outside `streamlit run`; these are harmless during tests.
    st.markdown(f"{quickstart}{readme}", unsafe_allow_html=False)


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
        search_text = st.text_input("Search building/agent", key="mgmt_search")
        
        q = session.query(ESGEntry)
        if client_sel != "All":
            q = q.filter(ESGEntry.client == client_sel)
        
        if search_text:
            like = f"%{search_text}%"
            q = q.filter((ESGEntry.building.ilike(like)) | (ESGEntry.agent.ilike(like)))
        
        entries = q.order_by(ESGEntry.timestamp.desc()).all()
        
        if entries:
            data = []
            for e in entries:
                score_e, score_s, score_g, score_esg = compute_esg_scores(e)
                data.append({
                    'id': e.id,
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
                    'Staff': e.employee_count,
                    'Approve': False
                })
            
            df = pd.DataFrame(data)
            # Prefer st.data_editor (Streamlit ≥ 1.23); fall back to read-only dataframe
            editor_supported = hasattr(st, 'data_editor') or hasattr(st, 'experimental_data_editor')
            if editor_supported:
                if hasattr(st, 'data_editor'):
                    edited = st.data_editor(df, num_rows="dynamic")
                else:
                    edited = st.experimental_data_editor(df, num_rows="dynamic")
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.download_button("📥 Download CSV", edited.to_csv(index=False), "esg_data.csv", "text/csv")
                with col2:
                    if st.button("Apply Approved Changes"):
                        if not require_admin_ui("Admin only: sign in to apply approved data changes."):
                            st.stop()
                        # commit rows marked Approve=True
                        approver = st.session_state.get('user') or 'system'
                        for _, row in edited[edited['Approve'] == True].iterrows():
                            eid = int(row['id'])
                            ent = session.query(ESGEntry).filter(ESGEntry.id == eid).first()
                            if ent:
                                changes = {}
                                try:
                                    old_waste = ent.waste_tonnes
                                    new_waste = float(row.get('Waste (T)') or 0)
                                    if old_waste != new_waste:
                                        changes['waste_tonnes'] = [old_waste, new_waste]
                                        ent.waste_tonnes = new_waste
                                except Exception:
                                    pass
                                try:
                                    old_energy = ent.energy_kwh
                                    new_energy = float(row.get('Energy (kWh)') or 0)
                                    if old_energy != new_energy:
                                        changes['energy_kwh'] = [old_energy, new_energy]
                                        ent.energy_kwh = new_energy
                                except Exception:
                                    pass
                                try:
                                    old_staff = ent.employee_count
                                    new_staff = int(float(row.get('Staff') or 0))
                                    if old_staff != new_staff:
                                        changes['employee_count'] = [old_staff, new_staff]
                                        ent.employee_count = new_staff
                                except Exception:
                                    pass

                                # persist entry and log edit if changes exist
                                session.add(ent)
                                if changes:
                                    eh = EditHistory(
                                        entry_id=ent.id,
                                        editor=st.session_state.get('user') or 'unknown',
                                        changes=json.dumps(changes),
                                        approved_by=approver,
                                        approved_at=_utcnow()
                                    )
                                    session.add(eh)
                        session.commit()
                        st.success("✅ Applied approved changes and logged edits")
                        st.rerun()
            else:
                st.dataframe(df, width="stretch", height=400)
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

            12 months of monthly historical records are included per building so the
            Historical Trends chart in the Dashboard shows meaningful trend data.
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if require_role('admin'):
                    if st.button("📥 Load Savills Demo Data", use_container_width=True, type="primary", key="load_savills"):
                        try:
                            load_savills_demo_data()
                            st.session_state.clients_data = load_clients_data()
                            st.success("✅ Savills demo data loaded successfully!")
                            st.info("View the data in the Dashboard or Raw Data tab")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error loading demo data: {e}")
                else:
                    st.info("Admin only: sign in to load demo data")
            
            with col2:
                if require_role('admin'):
                    if savills_count > 0:
                        if st.button("🗑️ Clear Savills Data", use_container_width=True, type="secondary", key="clear_savills"):
                            deleted = clear_savills_demo_data()
                            st.success(f"✅ Cleared {deleted} Savills records")
                            st.rerun()
                    else:
                        st.info("No Savills data to clear")
                else:
                    st.info("Admin only: sign in to clear demo data")
        
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
                if require_role('admin'):
                    if st.button("📥 Load Test Client Data", use_container_width=True, type="primary", key="load_test"):
                        try:
                            load_test_client_data()
                            st.session_state.clients_data = load_clients_data()
                            st.success("✅ Test Client demo data loaded successfully!")
                            st.info("View the data in the Dashboard or Raw Data tab")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error loading demo data: {e}")
                else:
                    st.info("Admin only: sign in to load demo data")
            
            with col2:
                if require_role('admin'):
                    if test_count > 0:
                        if st.button("🗑️ Clear Test Client Data", use_container_width=True, type="secondary", key="clear_test"):
                            deleted = clear_test_client_data()
                            st.success(f"✅ Cleared {deleted} Test Client records")
                            st.rerun()
                    else:
                        st.info("No Test Client data to clear")
                else:
                    st.info("Admin only: sign in to clear demo data")


# ==================== SERVICE SCOPE & CLEANING ESG PAGES ====================

def page_service_scope():
    """ESG Scope Configuration – toggle which service lines are in scope."""
    from service_lines import SERVICE_LINES, save_service_lines, get_active_service_lines

    st.header("🔧 ESG Scope Configuration")
    st.markdown(
        "Select the service lines you **control** for each building. "
        "Only active services will influence your Service ESG Score. "
        "Deselecting a line removes it from your score without affecting the "
        "building-level ESG portfolio view."
    )

    all_buildings = [
        b
        for client_data in st.session_state.clients_data.values()
        for b in client_data.get("Buildings", [])
    ]

    if not all_buildings:
        st.info("No buildings found. Add buildings in the Management page first.")
        return

    building = st.selectbox("Select Building", sorted(all_buildings), key="scope_building")

    current_active = get_active_service_lines(session, building)

    st.subheader("Service Lines")
    st.caption(
        "Only selected services will influence your Service ESG Score. "
        "Score reflects active services only."
    )

    new_active: list[str] = []
    cols = st.columns(2)
    for i, (line, meta) in enumerate(SERVICE_LINES.items()):
        col = cols[i % 2]
        with col:
            checked = col.checkbox(
                f"{line}  *(ESG: {', '.join(meta['domains'])} | Weight: {int(meta['weight']*100)}%)*",
                value=(line in current_active),
                key=f"scope_{line}_{building}",
            )
            if checked:
                new_active.append(line)

    if st.button("💾 Save Scope Configuration", type="primary"):
        save_service_lines(session, building, new_active)
        st.success(
            f"✅ Scope saved for **{building}**. "
            f"Active services: {', '.join(new_active) if new_active else 'None'}."
        )
        st.rerun()

    st.divider()
    st.info(
        "ℹ️ **Governance safeguard:** Where a metric is influenced by tenant "
        "behaviour or landlord systems, this is flagged as 'Influencing factors "
        "outside cleaning scope detected' in the Cleaning ESG page."
    )


def page_cleaning_esg():
    """Cleaning ESG Contribution – KPI entry, RAG signals, recommendations."""
    from service_lines import (
        CLEANING_KPI_FIELDS,
        compute_contribution_score,
        get_rag_status,
        generate_recommendations,
        get_active_service_lines,
        RAG_THRESHOLDS,
    )

    st.header("🧹 Cleaning ESG Performance")
    st.markdown(
        "Record and analyse cleaning-specific ESG KPIs. "
        "The **Cleaning ESG Contribution Score** reflects how cleaning operations "
        "influence the building's overall ESG rating."
    )

    all_buildings = sorted(
        b
        for client_data in st.session_state.clients_data.values()
        for b in client_data.get("Buildings", [])
    )
    if not all_buildings:
        st.info("No buildings found. Add buildings in the Management page first.")
        return

    col_b, col_p = st.columns(2)
    with col_b:
        building = st.selectbox("Building", all_buildings, key="kpi_building")
    with col_p:
        period = st.text_input("Period (e.g. 2025-Q1)", value="2025-Q1", key="kpi_period")

    # Load latest KPI for this building/period
    existing = (
        session.query(CleaningKPI)
        .filter(CleaningKPI.building == building, CleaningKPI.period == period)
        .order_by(CleaningKPI.created_at.desc())
        .first()
    )

    tab_entry, tab_rag, tab_recommend = st.tabs(
        ["📝 KPI Entry", "🚦 RAG Status", "💡 Recommendations"]
    )

    # Build field groups for display
    env_fields = {k: v for k, v in CLEANING_KPI_FIELDS.items() if v["domain"] == "E"}
    soc_fields = {k: v for k, v in CLEANING_KPI_FIELDS.items() if v["domain"] == "S"}
    gov_fields = {k: v for k, v in CLEANING_KPI_FIELDS.items() if v["domain"] == "G"}

    def _default(field: str) -> float:
        return float(getattr(existing, field, 0.0) or 0.0) if existing else 0.0

    with tab_entry:
        st.subheader("A. Environmental – Cleaning Impact")
        env_vals: dict[str, float] = {}
        c1, c2 = st.columns(2)
        for i, (field, meta) in enumerate(env_fields.items()):
            col = c1 if i % 2 == 0 else c2
            env_vals[field] = col.number_input(
                meta["label"], min_value=0.0, value=_default(field), key=f"kpi_e_{field}"
            )

        st.subheader("B. Social – Workforce & Occupant Impact")
        soc_vals: dict[str, float] = {}
        c1, c2 = st.columns(2)
        for i, (field, meta) in enumerate(soc_fields.items()):
            col = c1 if i % 2 == 0 else c2
            soc_vals[field] = col.number_input(
                meta["label"], min_value=0.0, value=_default(field), key=f"kpi_s_{field}"
            )

        st.subheader("C. Governance – Controls & Assurance")
        gov_vals: dict[str, float] = {}
        c1, c2 = st.columns(2)
        for i, (field, meta) in enumerate(gov_fields.items()):
            col = c1 if i % 2 == 0 else c2
            gov_vals[field] = col.number_input(
                meta["label"], min_value=0.0, value=_default(field), key=f"kpi_g_{field}"
            )

        all_vals = {**env_vals, **soc_vals, **gov_vals}

        if st.button("💾 Save KPIs", type="primary"):
            kpi_row = CleaningKPI(
                building=building,
                period=period,
                **{f: all_vals.get(f, 0.0) for f in CLEANING_KPI_FIELDS},
            )
            session.add(kpi_row)
            session.commit()
            st.success("✅ KPIs saved successfully.")
            st.rerun()

        # Contribution score preview
        if existing or any(v > 0 for v in all_vals.values()):
            if any(v > 0 for v in all_vals.values()):
                score_data = all_vals
            else:
                score_data = {f: getattr(existing, f, 0.0) for f in CLEANING_KPI_FIELDS}
            score = compute_contribution_score(score_data)
            st.divider()
            st.metric(
                "🏅 Cleaning ESG Contribution Score",
                f"{score} / 100",
                delta="Based on: chemical quality × 0.25 + waste segregation × 0.30 + training × 0.15 + carbon × 0.30",
                delta_color="off",
            )

    with tab_rag:
        st.subheader("🚦 RAG Status by KPI")
        if not existing:
            st.info("No KPI data saved yet for this building/period. Use the KPI Entry tab first.")
        else:
            kpi_dict = {f: float(getattr(existing, f, 0.0) or 0.0) for f in CLEANING_KPI_FIELDS}
            rag_map = {"green": "🟢", "amber": "🟠", "red": "🔴", "grey": "⚪"}

            active_lines = get_active_service_lines(session, building)
            if "Cleaning" not in active_lines:
                st.warning(
                    "⚠️ Cleaning is not in the active service scope for this building. "
                    "KPI scores are shown for reference only and do not affect your Service ESG Score."
                )

            for domain_label, fields in [
                ("A. Environmental", env_fields),
                ("B. Social", soc_fields),
                ("C. Governance", gov_fields),
            ]:
                st.markdown(f"**{domain_label}**")
                rows = []
                for field, meta in fields.items():
                    value = kpi_dict.get(field, 0.0)
                    status = get_rag_status(field, value)
                    cfg = RAG_THRESHOLDS.get(field, {})
                    threshold_note = (
                        f"Green ≥ {cfg.get('green', '–')} / Amber ≥ {cfg.get('amber', '–')}"
                        if cfg.get("direction") == "higher_better"
                        else f"Green ≤ {cfg.get('amber', '–')} / Amber ≤ {cfg.get('red', '–')}"
                    )
                    rows.append({
                        "KPI": meta["label"],
                        "Value": round(value, 2),
                        "Status": f"{rag_map.get(status, '⚪')} {status.capitalize()}",
                        "Threshold": threshold_note,
                    })
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    width="stretch",
                )

    with tab_recommend:
        st.subheader("💡 Intelligent Recommendations")
        st.caption(
            "These recommendations are operationally driven. "
            "Only the final action in each group may have revenue impact, "
            "and only where operationally justified."
        )
        if not existing:
            st.info("No KPI data saved yet. Save KPIs to generate recommendations.")
        else:
            kpi_dict = {f: float(getattr(existing, f, 0.0) or 0.0) for f in CLEANING_KPI_FIELDS}
            recs = generate_recommendations(kpi_dict)

            # Check if any external factors might influence metrics
            active_lines = get_active_service_lines(session, building)
            if "Waste Management" not in active_lines and kpi_dict.get("waste_seg_accuracy", 0) < 90:
                st.warning(
                    "⚠️ **Influencing factors outside cleaning scope detected.** "
                    "Waste segregation accuracy may be affected by the external waste "
                    "contractor. Current scope: Cleaning only."
                )

            if not recs:
                st.success("✅ All monitored KPIs are within acceptable thresholds. No actions required.")
            else:
                for rec in recs:
                    rag_icon = {"red": "🔴", "amber": "🟠"}.get(rec["rag_status"], "⚪")
                    with st.expander(f"{rag_icon} {rec['observation']}", expanded=(rec["rag_status"] == "red")):
                        st.markdown("**Likely drivers:**")
                        for d in rec["drivers"]:
                            st.markdown(f"- {d}")
                        st.markdown("**Recommended Actions:**")
                        for j, a in enumerate(rec["actions"], 1):
                            st.markdown(f"{j}. {a}")
                        st.markdown(f"*Projected Outcome:* {rec['projected_outcome']}")


# ==================== MAIN APP ====================

def main():
    """Main application"""
    # Page config
    apply_theme()

    # Initialise session state so re-runs in a new session don't raise AttributeError
    if 'clients_data' not in st.session_state:
        st.session_state.clients_data = load_clients_data()
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'Home'
    
    # Top banner – Nexus-Opus brand header
    st.title("Nexus-Opus | ESG Intelligence")
    st.caption("Precision FM Reporting & ESG Analytics · Powered by Nexus-Opus")
    # run simple data quality checks at startup
    check_quality_alerts()
    # schedule periodic checks in background once per process
    try:
        if not st.session_state.get('_alerts_thread_started'):
            def _bg():
                interval = int(os.environ.get('ALERT_INTERVAL_HOURS', '24')) * 3600
                while True:
                    time.sleep(interval)
                    try:
                        # Use the headless function – check_quality_alerts renders
                        # Streamlit UI elements and must not be called from a
                        # background thread outside a Streamlit script run context.
                        perform_quality_checks(send_email=True)
                    except Exception:
                        pass

            t = threading.Thread(target=_bg, daemon=True)
            t.start()
            st.session_state['_alerts_thread_started'] = True
    except Exception:
        pass

    # simple login UI in the sidebar
    with st.sidebar:
        # ── Nexus-Opus brand logo ──────────────────────────────────────
        render_sidebar_logo()
        st.divider()
        st.header("Account")
        if not st.session_state.get('user'):
            user_in = st.text_input("Username", key="login_user")
            pass_in = st.text_input("Password", type="password", key="login_pass")
            if st.button("Sign in", key="signin"):
                auth = authenticate(user_in, pass_in)
                if auth:
                    st.session_state.user = auth['username']
                    st.session_state.user_role = auth['role']
                    st.success(f"Signed in as {auth['username']}")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        else:
            st.write(f"Signed in as {st.session_state.get('user')} ({st.session_state.get('user_role')})")
            if st.button("Sign out", key="signout"):
                st.session_state.user = None
                st.session_state.user_role = None
                st.rerun()
    
    # Navigation
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    
    with col1:
        if st.button("🏠 Home", width="stretch", key="nav_home"):
            st.session_state.current_page = 'Home'
    
    with col2:
        if st.button("📤 Upload Data", width="stretch", key="nav_upload"):
            st.session_state.current_page = 'Data Upload'
    
    with col3:
        if st.button("📊 Dashboard", width="stretch", key="nav_dashboard"):
            st.session_state.current_page = 'Dashboard'
    
    with col4:
        if st.button("📄 Reports", width="stretch", key="nav_reports"):
            st.session_state.current_page = 'Reports'
    
    with col5:
        if st.button("⚙️ Management", width="stretch", key="nav_management"):
            st.session_state.current_page = 'Management'

    with col6:
        if st.button("🔧 ESG Scope", width="stretch", key="nav_scope"):
            st.session_state.current_page = 'ESG Scope'

    with col7:
        if st.button("🧹 Cleaning ESG", width="stretch", key="nav_cleaning"):
            st.session_state.current_page = 'Cleaning ESG'
    
    with col8:
        if st.button("❓ Help", width="stretch", key="nav_help"):
            st.session_state.current_page = 'Help'
    
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
    elif page == 'ESG Scope':
        page_service_scope()
    elif page == 'Cleaning ESG':
        page_cleaning_esg()
    elif page == 'Help':
        page_help()


if __name__ == "__main__":
    main()
