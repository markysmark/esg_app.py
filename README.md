# ESG Intelligence Platform

A **comprehensive, corporate-grade Environmental, Social & Governance (ESG) management system** built with Streamlit. Designed for property portfolio managers, corporate sustainability teams, and ESG consultants.

## 🌟 Key Features

### 📊 Dashboard & Analytics
- **Real-time ESG performance dashboard** with KPIs
- **Portfolio-level analytics** and risk assessment
- **Building performance ranking** and comparisons
- **Historical trends** and pattern analysis
- **Data quality grading** (A-F assessment)

### 📤 Bulk Data Upload
- **CSV/Excel import** - Process multiple sites at once
- **Smart column mapping** - Auto-detect and map data fields
- **Real-time validation** - Preview before import
- **Batch processing** - Handle thousands of records
- **Duplicate handling** - Skip or overwrite as needed
- **Template download** - Example data to get started

### 📄 Advanced Reporting  
- **Multi-format export**: CSV, Excel, JSON, PDF
- **Custom filtering** - By client, agent, building, dates
- **Professional reports** - Executive summaries & recommendations
- **Performance analytics** - Distribution and risk analysis

### 🏢 Portfolio Management
- **Multi-client support** - Manage multiple organizations
- **Agent tracking** - Monitor portfolios by managing agent
- **Site management** - Track individual properties
- **Document library** - Upload & store ESG evidence
- **Audit trails** - Complete activity logging

## 🚀 Quick Start

### Installation

1. **Create virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run the app**:
```bash
streamlit run esg_app.py
```

4. Open `http://localhost:8501` in your browser

### Docker

```bash
docker build -t esg_intelligence:latest .
docker run -it -p 8501:8501 -v $(pwd)/data:/app esg_intelligence:latest
```

### CI/CD – Docker Hub publishing

The `Build and push Docker image` workflow automatically publishes to Docker Hub on every push to `main`. It requires two GitHub repository secrets to be configured:

| Secret name | Description |
|---|---|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | A Docker Hub [access token](https://docs.docker.com/security/for-developers/access-tokens/) |

Add these in **Settings → Secrets and variables → Actions → New repository secret**. Without them the login and push steps are skipped automatically.

## 📚 Using the App

> **New in‑app instructions:** click the **❓ Help** button in the top navigation bar to view this README (and more) directly inside the running application.


### 1. Home Dashboard
Overview with portfolio statistics, a **data quality grade** (A–F) for the entire portfolio, and quick navigation buttons.

> The grade is calculated based on completeness, recency and evidence coverage; hover over the metric for percent/completeness details in the app.

### 2. Upload Data
### 2. Upload Data
- Download CSV template
- Prepare data file with ESG metrics
- Map columns to platform fields
- Import with validation

    **Profile support**: once you've mapped a set of columns, expand the
    "Save / manage profile" section to give the mapping a name. Future uploads
    of the same format can be restored from the profile dropdown, saving time
    when you regularly ingest files from the same source.

**Required columns**: Building Name, Waste (Tonnes), Energy (kWh), Chemicals (L), Eco Chemicals %, Staff Count, Total Hours

### 3. View Dashboard
- **KPI Cards**: Key metrics overview
- **Score Breakdown**: E/S/G composition
- **Rankings**: Building comparison
- **Risk Matrix**: Identify problem areas
- **Trends**: Performance over time
- **Export**: Download detailed data

### 4. Generate Reports
Export filtered data in CSV, Excel, JSON, or PDF format with custom date ranges and scope.

### 5. Manage Data
- View portfolio structure (a special "Top Agents" entry lists the most common managers so you can start with them)
- Browse raw ESG records
- Add clients, agents, buildings (you can create new clients anytime via the in‑app form)
- Manage uploaded evidence documents

## 📊 ESG Scoring Methodology

**Overall ESG Score** = (E × 50%) + (S × 30%) + (G × 20%)

### Environmental (E) Score
- Waste reduction scoring (0-20 tonnes scale)
- Energy efficiency scoring (0-20,000 kWh scale)  
- Eco-chemical percentage bonus
- **Max: 100 points**

### Social (S) Score
- Hours worked per employee vs. baseline (40 hrs/week)
- Employee headcount bonus
- **Max: 100 points**

### Governance (G) Score
- Base compliance score (50 pts)
- Eco-chemical percentage contribution
- Evidence document bonus (+2 pts each)
- **Max: 100 points**

## 📁 Structure

```
├── main_app.py           # Main application entry (run via esg_app.py)
├── esg_app.py            # Compatibility shim for the entrypoint
├── data_upload.py        # Bulk import module
├── dashboard.py          # Analytics & visualizations
├── export_report.py      # Reporting module
├── theme.py              # Styling & branding
│
├── jpc_esg_intelligence.db  # SQLite database
├── clients_agents.json      # Configuration
├── evidence/                # Uploaded documents
└── reports/                 # Generated reports
```

## 🔐 Security

**Production recommendations**:

1. Change admin password:
```bash
export ADMIN_PASSWORD="your_secure_password"
```

2. Use PostgreSQL instead of SQLite:
```python
# In main_app.py
engine = create_engine('postgresql://user:pass@localhost/esg_db')
```

3. Store files in S3 or cloud storage
4. Add authentication (LDAP, SAML, OAuth)
5. Regular backups and monitoring

## 🎨 Customization

Edit colors and branding in `theme.py`:
```python
brand_palette = {
    "brand_primary": "#102A43",      # Dark navy
    "brand_accent": "#F5A623",       # Orange
    "success_color": "#2E7D32",      # Green
    "danger_color": "#D32F2F"        # Red
}
```

Modify scoring weights in `main_app.py`:
```python
overall = round((e * 0.50) + (s * 0.30) + (g * 0.20), 1)
```

## 📞 Support

- **Bugs**: GitHub Issues
- **Questions**: GitHub Discussions  
- **Suggestions**: Pull Requests welcome

## 📄 License

[Your License Here]

---

Built with [Streamlit](https://streamlit.io) | Database: SQLite/SQLAlchemy | Charts: Plotly

*ESG Intelligence Platform v2.0 - March 2026*
