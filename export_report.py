"""
ESG Export & Reporting Module
Handles advanced export in multiple formats and custom report generation.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
import json
from main_app import (
    ESGEntry, ScoreSnapshot, ReportRun, ActionLog, EvidenceRegister,
    session, compute_esg_scores, grade_data_quality
)

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
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
        q = q.filter(ESGEntry.timestamp <= end_date)
    
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
            
            date_format = workbook.add_format({
                'num_format': 'yyyy-mm-dd',
                'border': 1
            })
            
            # Apply formats
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
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
    Generate comprehensive PDF report.
    Uses ReportLab to create professional PDF output.
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    
    # Get data
    esg_data = get_esg_data_for_export(client, agent, building, start_date, end_date)
    dq = grade_data_quality(client, agent, building)
    
    # Create PDF
    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#102A43'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#F5A623'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    # Add content
    story.append(Paragraph("ESG Intelligence Report", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Report info
    scope = []
    if client:
        scope.append(f"Client: {client}")
    if agent:
        scope.append(f"Agent: {agent}")
    if building:
        scope.append(f"Building: {building}")
    
    scope_text = " | ".join(scope) if scope else "Portfolio"
    story.append(Paragraph(f"<b>Scope:</b> {scope_text}", styles['Normal']))
    story.append(Paragraph(f"<b>Period:</b> {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(f"Data Quality Grade: <b>{dq['grade']}</b>", styles['Normal']))
    story.append(Paragraph(f"Data Completeness: {dq['current_data_pct']}%", styles['Normal']))
    story.append(Paragraph(f"Evidence Coverage: {dq['obligations_with_evidence_pct']}%", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Data table
    if not esg_data.empty:
        story.append(Paragraph("ESG Metrics Detail", heading_style))
        
        # Create summary statistics
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
        
        summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#102A43')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.2*inch))
    
    # Recommendations
    story.append(Paragraph("Recommendations", heading_style))
    
    # Determine recommendations based on scores
    recommendations = []
    
    # Get latest entry for recommendations
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
            recommendations.append("🔴 Environmental Score Below Target - Increase waste reduction and energy efficiency initiatives")
        if s < 50:
            recommendations.append("🔴 Social Score Below Target - Enhance employee wellbeing and community engagement programs")
        if g < 50:
            recommendations.append("🔴 Governance Score Below Target - Strengthen compliance documentation and evidence collection")
        if esg > 80:
            recommendations.append("🟢 Strong Overall Performance - Continue current initiatives and consider best practice sharing")
    
    for rec in recommendations:
        story.append(Paragraph("• " + rec, styles['Normal']))
    
    # Build PDF
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
        agent_options = []
        if client_sel:
            agent_options = st.session_state.clients_data.get(client_sel, {}).get("Agents", [])
        
        agent_sel = st.selectbox(
            "Agent (Optional)",
            [None] + agent_options,
            format_func=lambda x: "All Agents" if x is None else x
        )
    
    with col3:
        building_options = []
        if client_sel:
            building_options = st.session_state.clients_data.get(client_sel, {}).get("Buildings", [])
        
        building_sel = st.selectbox(
            "Building (Optional)",
            [None] + building_options,
            format_func=lambda x: "All Buildings" if x is None else x
        )
    
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input("Start Date", key='export_start')
    
    with col2:
        end_date = st.date_input("End Date", key='export_end')
    
    st.divider()
    
    # Get data
    esg_data = get_esg_data_for_export(client_sel, agent_sel, building_sel, start_date, end_date)
    
    if esg_data.empty:
        st.warning("⚠️ No data found for the selected filters. Please upload ESG data first.")
        return
    
    st.info(f"📊 Found **{len(esg_data)}** records for export")
    
    # Preview
    with st.expander("👁️ Preview Data", expanded=False):
        st.dataframe(esg_data, use_container_width=True)
    
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
        except:
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
        if st.button("📑 PDF Report", use_container_width=True, type="primary"):
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
        
        st.plotly_chart(fig_hist, use_container_width=True)
    
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
        
        st.plotly_chart(fig_box, use_container_width=True)
