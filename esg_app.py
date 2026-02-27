import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime

# --- 1. CONFIG & STYLING ---
st.set_page_config(page_title="Concierge ESG Strategy Engine", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIC ENGINE (2026 BENCHMARKS) ---
def get_site_logic(market, staff, profit):
    # 2026 Wage Rates
    london_wage, uk_wage = 14.80, 13.45
    
    # 2026 Compliance Risks
    dwt_fine = 150000 
    hiring_cost = staff * 0.30 * 6125 # 30% churn * avg hire cost
    
    return {
        "london_wage": london_wage,
        "uk_wage": uk_wage,
        "dwt_fine": dwt_fine,
        "hiring_risk": hiring_cost,
        "asset_value": profit * 12 # Simple 12x multiplier for illustrative asset value
    }

# --- 3. PDF GENERATOR ---
class ESG_PDF(FPDF):
    def header(self):
        self.set_fill_color(24, 44, 67)
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 16)
        self.cell(0, 20, 'CONCIERGE ESG STRATEGIC REPORT 2026', 0, 1, 'C')
        self.ln(10)

def generate_report_pdf(site_name, results_df, reward_logic, carbon_data):
    pdf = ESG_PDF()
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    
    # Risk Section
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"Strategic Risk Assessment: {site_name}", ln=True)
    pdf.set_font('Arial', '', 11)
    pdf.multi_cell(0, 7, f"Based on Feb 2026 UK SRS Standards, this site faces a combined liability of £{results_df['Cost'].sum():,} if non-compliant by Oct 1st.")
    
    # Testimonial Section
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.multi_cell(0, 10, f'"The ESG Reward Program has transformed our team. Knowing our precision in digital waste tracking directly funds our Longevity Grant makes us feel like true asset guardians."', border=1, fill=True)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. UI LAYOUT ---
st.title("🛡️ Concierge ESG & Asset Guardian Engine")
st.subheader("2026 Strategic Compliance & Staff Incentivisation")

with st.sidebar:
    st.header("📍 Site Configuration")
    site_name = st.text_input("Site Name", "Elite Commercial Plaza")
    market = st.selectbox("Sector", ["Skyscrapers", "Commercial Offices", "Data Centres", "Managing Agents", "Casinos"])
    location = st.selectbox("Location", ["London (Inner)", "London (Outer)", "UK Regional"])
    staff_count = st.number_input("Staff on Site", value=50)
    profit_val = st.number_input("Annual Site Profit (£)", value=200000)
    
    st.divider()
    st.header("🤝 Service Expansion")
    s_lines = st.multiselect("Active Concierge Lines", ["Digital Waste API", "IAQ Monitoring", "Biophilic Care", "Asset Audits"])

# --- 5. DASHBOARD CALCULATIONS ---
logic = get_site_logic(market, staff_count, profit_val)
wage_choice = logic['london_wage'] if "London" in location else logic['uk_wage']

# Main Metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("2026 Real Living Wage", f"£{wage_choice}/hr")
c2.metric("Oct 2026 Fine Risk", f"£{logic['dwt_fine']:,}")
c3.metric("Retention Value", f"£{logic['hiring_risk']:,.0f}")
c4.metric("Carbon Offset", f"{staff_count * 36} kg CO2e")

# --- 6. COMPETITIVE SWOT & BENCHMARKING ---
st.divider()
col_a, col_b = st.columns(2)

with col_a:
    st.write("### 🕵️ Competitive Gap Analysis")
    fig = go.Figure(data=[
        go.Bar(name='Current Site', x=['Env', 'Soc', 'Gov'], y=[55, 60, 45], marker_color='#EF553B'),
        go.Bar(name='2026 Industry Avg', x=['Env', 'Soc', 'Gov'], y=[82, 85, 80], marker_color='#00CC96')
    ])
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.write("### ⚔️ SWOT vs Traditional Giants")
    st.success("**Strength:** Your 95% staff retention vs their 40% average.")
    st.error("**Threat:** Competitors lack Digital Waste API integration for Oct 2026.")
    st.info("**Opportunity:** Upsell IAQ monitoring to secure Grade A+ rent premiums.")

# --- 7. STAFF REWARD SECTION ---
st.divider()
st.header("🎁 Staff ESG Incentive Program")
reward_pool = (logic['dwt_fine'] * 0.05) + (logic['hiring_risk'] * 0.10)
st.write(f"By hitting ESG targets, we create a **£{reward_pool:,.2f}** self-funded reward pool for the team.")

# --- 8. REPORT GENERATOR ---
st.divider()
if st.button("🚀 Generate Final Contractual ESG Report"):
    # Create a dummy DF for the PDF summary
    pdf_data = pd.DataFrame([
        {"Risk": "Digital Waste Fine", "Cost": logic['dwt_fine']},
        {"Risk": "Recruitment Sunk Cost", "Cost": logic['hiring_risk']}
    ])
    
    report_pdf = generate_report_pdf(site_name, pdf_data, reward_pool, staff_count * 36)
    st.download_button("📥 Download Official 2026 ESG Report", report_pdf, f"{site_name}_ESG_2026.pdf")