"""
ESG Export & Reporting Module
Handles advanced export in multiple formats and custom report generation.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO
from main_app import (
    ESGEntry,
    session, compute_esg_scores, grade_data_quality
)

try:
    import importlib.util as _importlib_util
    REPORTLAB_AVAILABLE = _importlib_util.find_spec('reportlab') is not None
except Exception:
    REPORTLAB_AVAILABLE = False


def get_esg_data_for_export(client=None, agent=None, building=None, start_date=None, end_date=None):
    """
    Extract ESG data for export based on filters.
    
    Returns:
        DataFrame with ESG data
    """
    q = session.query(ESGEntry)
    
    if client:
        q = q.filter(ESGEntry.client == client)
    if agent:
        q = q.filter(ESGEntry.agent == agent)
    if building:
        q = q.filter(ESGEntry.building == building)
    if start_date:
        q = q.filter(ESGEntry.timestamp >= start_date)
    if end_date:
        end_dt = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)
        q = q.filter(ESGEntry.timestamp <= end_dt)
    
    entries = q.order_by(ESGEntry.timestamp.desc()).all()
    
    data = []
    for entry in entries:
        e, s, g, esg = compute_esg_scores(entry)
        data.append({
            'Date': entry.timestamp.strftime('%Y-%m-%d %H:%M'),
            'Client': entry.client,
            'Agent': entry.agent,
            'Building': entry.building,
            'Waste (Tonnes)': entry.waste_tonnes,
            'Energy (kWh)': entry.energy_kwh,
            'Chemicals (L)': entry.chem_litres,
            'Eco-Chemicals %': entry.eco_chem_pct,
            'Staff Count': entry.employee_count,
            'Total Hours': entry.hours_worked,
            'E-Score': round(e, 1),
            'S-Score': round(s, 1),
            'G-Score': round(g, 1),
            'ESG Score': round(esg, 1)
        })
    
    return pd.DataFrame(data)


def export_to_csv(df, filename):
    """Export DataFrame to CSV."""
    return df.to_csv(index=False).encode('utf-8')


def export_to_excel(df, filename):
    """Export DataFrame to Excel with formatting."""
    output = BytesIO()
    
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='ESG Data', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['ESG Data']
            
            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#102A43',
                'font_color': 'white',
                'border': 1
            })
            
            number_format = workbook.add_format({
                'num_format': '0.00',
                'border': 1
            })
            
            # Apply formats
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Apply number format to numeric data columns
            for col_num, col_name in enumerate(df.columns):
                if pd.api.types.is_numeric_dtype(df[col_name]):
                    worksheet.set_column(col_num, col_num, None, number_format)
            
            # Auto-adjust column widths
            for col_num, col_name in enumerate(df.columns):
                max_length = max(
                    df[col_name].astype(str).apply(len).max(),
                    len(str(col_name))
                ) + 2
                worksheet.set_column(col_num, col_num, min(max_length, 50))
        
        return output.getvalue()
    except ImportError:
        # Fallback to simple CSV if xlsxwriter not available
        return export_to_csv(df, filename)


def generate_pdf_report(client, agent, building, start_date, end_date):
    """
    Generate comprehensive PDF report with Nexus-Opus branding.
    Uses ReportLab to create professional PDF output.
    """
    if not REPORTLAB_AVAILABLE:
        return None

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors

    # ── Nexus-Opus brand colours ──────────────────────────────────────────
    NEXUS_NAVY      = colors.HexColor('#1A202C')
    NEXUS_TEAL      = colors.HexColor('#0D9488')
    OPUS_GOLD       = colors.HexColor('#D97706')
    SURFACE         = colors.HexColor('#E2E8F0')
    ROW_ALT_BG      = colors.HexColor('#EDF7F6')  # teal-tinted alternate row

    # Get data
    esg_data = get_esg_data_for_export(client, agent, building, start_date, end_date)
    dq = grade_data_quality(client, agent, building)

    # Create PDF
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    story = []
    styles = getSampleStyleSheet()

    # ── Custom paragraph styles ───────────────────────────────────────────
    brand_label_style = ParagraphStyle(
        'BrandLabel',
        parent=styles['Normal'],
        fontSize=8,
        textColor=NEXUS_TEAL,
        fontName='Helvetica',
        spaceAfter=0,
        letterSpacing=2,
    )
    brand_name_style = ParagraphStyle(
        'BrandName',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.white,
        fontName='Helvetica-Bold',
        spaceAfter=2,
        leading=26,
    )
    brand_sub_style = ParagraphStyle(
        'BrandSub',
        parent=styles['Normal'],
        fontSize=10,
        textColor=NEXUS_TEAL,
        fontName='Helvetica',
        spaceAfter=0,
        letterSpacing=1.5,
    )
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=NEXUS_NAVY,
        spaceAfter=10,
        fontName='Helvetica-Bold',
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=NEXUS_TEAL,
        spaceAfter=8,
        fontName='Helvetica-Bold',
    )

    # ── Cover block ───────────────────────────────────────────────────────
    cover_data = [[
        Paragraph("NEXUS · OPUS", brand_name_style),
        Paragraph("ESG INTELLIGENCE REPORT", brand_label_style),
    ]]
    cover_table = Table(cover_data, colWidths=[6.5 * inch])
    cover_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), NEXUS_NAVY),
        ('TOPPADDING',    (0, 0), (-1, -1), 18),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 18),
        ('LEFTPADDING',   (0, 0), (-1, -1), 20),
        ('ROUNDEDCORNERS', [8]),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.25 * inch))

    # Teal rule under cover block
    story.append(HRFlowable(
        width="100%", thickness=2, color=NEXUS_TEAL, spaceAfter=0.2 * inch,
    ))

    # ── Report metadata ───────────────────────────────────────────────────
    story.append(Paragraph("ESG Intelligence Report", title_style))
    story.append(Spacer(1, 0.15 * inch))

    scope = []
    if client:
        scope.append(f"Client: {client}")
    if agent:
        scope.append(f"Agent: {agent}")
    if building:
        scope.append(f"Building: {building}")

    scope_text = " | ".join(scope) if scope else "Portfolio"
    story.append(Paragraph(f"<b>Scope:</b> {scope_text}", styles['Normal']))
    story.append(Paragraph(
        f"<b>Period:</b> {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        styles['Normal'],
    ))
    story.append(Paragraph(
        f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles['Normal'],
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ── Executive Summary ─────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(f"Data Quality Grade: <b>{dq['grade']}</b>", styles['Normal']))
    story.append(Paragraph(f"Data Completeness: {dq['current_data_pct']}%", styles['Normal']))
    story.append(Paragraph(f"Evidence Coverage: {dq['obligations_with_evidence_pct']}%", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # ── Data table ────────────────────────────────────────────────────────
    if not esg_data.empty:
        story.append(Paragraph("ESG Metrics Detail", heading_style))

        summary_data = [
            ['Metric', 'Value'],
            ['Total Records', str(len(esg_data))],
            ['Avg ESG Score', f"{esg_data['ESG Score'].astype(float).mean():.1f}"],
            ['Avg E-Score', f"{esg_data['E-Score'].astype(float).mean():.1f}"],
            ['Avg S-Score', f"{esg_data['S-Score'].astype(float).mean():.1f}"],
            ['Avg G-Score', f"{esg_data['G-Score'].astype(float).mean():.1f}"],
            ['Total Waste (T)', f"{esg_data['Waste (Tonnes)'].astype(float).sum():.1f}"],
            ['Total Energy (kWh)', f"{esg_data['Energy (kWh)'].astype(float).sum():,.0f}"],
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), NEXUS_NAVY),
            ('TEXTCOLOR',     (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND',    (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]),
            ('GRID',          (0, 0), (-1, -1), 0.5, SURFACE),
            ('LINEBELOW',     (0, 0), (-1, 0), 2, NEXUS_TEAL),
        ]))

        story.append(summary_table)
        story.append(Spacer(1, 0.2 * inch))

    # ── Recommendations ───────────────────────────────────────────────────
    story.append(Paragraph("Recommendations", heading_style))

    recommendations = []

    q = session.query(ESGEntry)
    if client:
        q = q.filter(ESGEntry.client == client)
    if agent:
        q = q.filter(ESGEntry.agent == agent)
    if building:
        q = q.filter(ESGEntry.building == building)

    latest = q.order_by(ESGEntry.timestamp.desc()).first()

    if latest:
        e, s, g, esg = compute_esg_scores(latest)

        if e < 50:
            recommendations.append(
                "Environmental Score Below Target – Increase waste reduction and energy efficiency initiatives"
            )
        if s < 50:
            recommendations.append(
                "Social Score Below Target – Enhance employee wellbeing and community engagement programs"
            )
        if g < 50:
            recommendations.append(
                "Governance Score Below Target – Strengthen compliance documentation and evidence collection"
            )
        if esg > 80:
            recommendations.append(
                "Strong Overall Performance – Continue current initiatives and consider best practice sharing"
            )

    for rec in recommendations:
        story.append(Paragraph("• " + rec, styles['Normal']))

    # ── Footer watermark ──────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=NEXUS_TEAL, spaceAfter=6))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#718096'),
        alignment=1,  # centre
    )
    story.append(Paragraph(
        f"Nexus-Opus ESG Intelligence Platform  ·  Confidential  ·  "
        f"Generated {datetime.now().strftime('%Y-%m-%d')}",
        footer_style,
    ))

    doc.build(story)
    return pdf_buffer.getvalue()


def render_export_interface():
    """
    Render the comprehensive export and reporting interface.
    """
    st.header("📄 Export & Reporting")
    st.markdown("Generate and export ESG data in multiple formats for analysis and compliance reporting.")
    
    # Filter section
    st.subheader("🔍 Select Data to Export")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        client_sel = st.selectbox(
            "Client (Optional)",
            [None] + list(st.session_state.clients_data.keys()),
            format_func=lambda x: "All Clients" if x is None else x
        )
    
    with col2:
        if client_sel:
            agent_options = st.session_state.clients_data.get(client_sel, {}).get("Agents", [])
        else:
            # Allow selecting any agent from the database when no client is chosen
            db_agents = session.query(ESGEntry.agent).filter(
                ESGEntry.agent.isnot(None)
            ).distinct().all()
            agent_options = sorted(set(a[0] for a in db_agents if a[0]))
        
        agent_sel = st.selectbox(
            "Agent (Optional)",
            [None] + agent_options,
            format_func=lambda x: "All Agents" if x is None else x
        )
    
    with col3:
        building_options = []
        if agent_sel:
            # Populate buildings from the database for the selected agent
            q_buildings = session.query(ESGEntry.building).filter(
                ESGEntry.agent == agent_sel,
                ESGEntry.building.isnot(None)
            )
            if client_sel:
                q_buildings = q_buildings.filter(ESGEntry.client == client_sel)
            building_options = sorted(set(
                b[0] for b in q_buildings.distinct().all() if b[0]
            ))
        elif client_sel:
            building_options = st.session_state.clients_data.get(client_sel, {}).get("Buildings", [])
        
        building_sel = st.selectbox(
            "Building (Optional)",
            [None] + building_options,
            format_func=lambda x: "All Buildings" if x is None else x
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=365), key='export_start')
    
    with col2:
        end_date = st.date_input("End Date", value=datetime.now().date(), key='export_end')
    
    st.divider()
    
    # Get data
    esg_data = get_esg_data_for_export(client_sel, agent_sel, building_sel, start_date, end_date)
    
    if esg_data.empty:
        st.warning("⚠️ No data found for the selected filters. Please upload ESG data first.")
        return
    
    st.info(f"📊 Found **{len(esg_data)}** records for export")
    
    # Preview
    with st.expander("👁️ Preview Data", expanded=False):
        st.dataframe(esg_data, width="stretch")
    
    st.divider()
    
    # Export options
    st.subheader("📥 Export Formats")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # CSV Export
        csv_data = export_to_csv(esg_data, 'esg_data.csv')
        st.download_button(
            label="📄 CSV",
            data=csv_data,
            file_name=f"esg_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Download as CSV - Compatible with Excel and most tools"
        )
    
    with col2:
        # Excel Export
        try:
            excel_data = export_to_excel(esg_data, 'esg_data.xlsx')
            st.download_button(
                label="📊 Excel",
                data=excel_data,
                file_name=f"esg_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Download as Excel - With formatting and formulas"
            )
        except Exception:
            st.info("Excel export unavailable")
    
    with col3:
        # JSON Export
        json_data = esg_data.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button(
            label="📋 JSON",
            data=json_data,
            file_name=f"esg_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            help="Download as JSON - For API integrations"
        )
    
    with col4:
        # PDF Report
        if st.button("📑 PDF Report", width="stretch", type="primary"):
            with st.spinner("Generating PDF report..."):
                pdf_data = generate_pdf_report(client_sel, agent_sel, building_sel, start_date, end_date)
                
                if pdf_data:
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_data,
                        file_name=f"esg_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf"
                    )
                    st.success("✅ PDF report generated successfully!")
                else:
                    st.warning("PDF generation requires reportlab library")
    
    st.divider()
    
    # Summary statistics
    st.subheader("📈 Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", len(esg_data))
    
    with col2:
        st.metric("AVG ESG Score", f"{esg_data['ESG Score'].astype(float).mean():.1f}/100")
    
    with col3:
        st.metric("Total Waste", f"{esg_data['Waste (Tonnes)'].astype(float).sum():.1f}T")
    
    with col4:
        st.metric("Total Energy", f"{esg_data['Energy (kWh)'].astype(float).sum():,.0f} kWh")
    
    # Score distribution
    st.subheader("Score Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Histogram of ESG scores
        fig_hist = go.Figure(data=[
            go.Histogram(
                x=esg_data['ESG Score'].astype(float),
                nbinsx=20,
                marker_color='#1976D2',
                name='ESG Score'
            )
        ])
        
        fig_hist.update_layout(
            title='Distribution of ESG Scores',
            xaxis_title='Score',
            yaxis_title='Count',
            height=400
        )
        
        st.plotly_chart(fig_hist, width="stretch")
    
    with col2:
        # Box plot of E/S/G scores
        fig_box = go.Figure()
        
        for col_name, color in [('E-Score', '#2E7D32'), ('S-Score', '#1976D2'), ('G-Score', '#F57C00')]:
            fig_box.add_trace(go.Box(
                y=esg_data[col_name].astype(float),
                name=col_name,
                marker_color=color
            ))
        
        fig_box.update_layout(
            title='E/S/G Score Distribution',
            yaxis_title='Score',
            height=400,
            showlegend=True
        )
        
        st.plotly_chart(fig_box, width="stretch")
