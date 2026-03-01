"""
ESG Dashboard Module
Displays comprehensive ESG performance analytics and KPIs.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from main_app import ESGEntry, session, compute_esg_scores


def get_portfolio_stats(client_sel=None):
    """
    Calculate portfolio-wide ESG statistics.
    
    Args:
        client_sel: Optional client filter
    
    Returns:
        Dict with key metrics
    """
    q = session.query(ESGEntry)
    if client_sel:
        q = q.filter(ESGEntry.client == client_sel)
    
    entries = q.all()
    
    if not entries:
        return {
            'total_buildings': 0,
            'avg_esg_score': 0.0,
            'avg_e_score': 0.0,
            'avg_s_score': 0.0,
            'avg_g_score': 0.0,
            'total_waste': 0.0,
            'total_energy': 0.0,
            'total_employees': 0,
            'buildings_count': 0
        }
    
    # Get latest entry per building
    latest_entries = {}
    for entry in entries:
        key = entry.building
        if key not in latest_entries or entry.timestamp > latest_entries[key].timestamp:
            latest_entries[key] = entry
    
    latest_list = list(latest_entries.values())
    
    # Calculate scores
    scores = [compute_esg_scores(e) for e in latest_list]
    e_scores = [s[0] for s in scores]
    s_scores = [s[1] for s in scores]
    g_scores = [s[2] for s in scores]
    esg_scores = [s[3] for s in scores]
    
    return {
        'total_buildings': len(latest_entries),
        'avg_esg_score': round(sum(esg_scores) / len(esg_scores), 1) if esg_scores else 0.0,
        'avg_e_score': round(sum(e_scores) / len(e_scores), 1) if e_scores else 0.0,
        'avg_s_score': round(sum(s_scores) / len(s_scores), 1) if s_scores else 0.0,
        'avg_g_score': round(sum(g_scores) / len(g_scores), 1) if g_scores else 0.0,
        'total_waste': round(sum(e.waste_tonnes for e in latest_list), 1),
        'total_energy': round(sum(e.energy_kwh for e in latest_list), 0),
        'total_employees': sum(e.employee_count for e in latest_list),
        'buildings_count': len(latest_list)
    }


def get_building_performance(client_sel=None):
    """
    Get performance data for all buildings.
    
    Returns:
        DataFrame with building performance metrics
    """
    q = session.query(ESGEntry)
    if client_sel:
        q = q.filter(ESGEntry.client == client_sel)
    
    entries = q.all()
    
    if not entries:
        return pd.DataFrame()
    
    # Get latest entry per building
    latest_entries = {}
    for entry in entries:
        key = entry.building
        if key not in latest_entries or entry.timestamp > latest_entries[key].timestamp:
            latest_entries[key] = entry
    
    # Create DataFrame
    data = []
    for building, entry in latest_entries.items():
        e, s, g, esg = compute_esg_scores(entry)
        data.append({
            'Building': building,
            'Agent': entry.agent or 'N/A',
            'E Score': e,
            'S Score': s,
            'G Score': g,
            'ESG Score': esg,
            'Waste (T)': entry.waste_tonnes,
            'Energy (kWh)': entry.energy_kwh,
            'Employees': entry.employee_count,
            'Last Updated': entry.timestamp
        })
    
    return pd.DataFrame(data)


def render_kpi_cards(stats, brand_palette):
    """
    Render KPI metric cards.
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Portfolio ESG Score",
            f"{stats['avg_esg_score']}",
            delta="out of 100",
            delta_color="off"
        )
    
    with col2:
        st.metric(
            "Buildings Monitored",
            stats['total_buildings'],
            delta=f"{stats['buildings_count']} with data"
        )
    
    with col3:
        st.metric(
            "Avg Staff Count",
            f"{stats['total_employees'] // max(stats['total_buildings'], 1)}",
            delta=f"{stats['total_employees']} total"
        )
    
    with col4:
        st.metric(
            "Total Waste",
            f"{stats['total_waste']}T",
            delta=f"{stats['total_energy']:,.0f} kWh",
            delta_color="inverse"
        )


def render_esg_breakdown(stats, brand_palette):
    """
    Render E/S/G score breakdown visualization.
    """
    fig = go.Figure(data=[
        go.Bar(
            name='Environmental',
            x=['Score'],
            y=[stats['avg_e_score']],
            marker_color='#2E7D32',
            textposition='auto',
            text=[f"{stats['avg_e_score']:.1f}"]
        ),
        go.Bar(
            name='Social',
            x=['Score'],
            y=[stats['avg_s_score']],
            marker_color='#1976D2',
            textposition='auto',
            text=[f"{stats['avg_s_score']:.1f}"]
        ),
        go.Bar(
            name='Governance',
            x=['Score'],
            y=[stats['avg_g_score']],
            marker_color='#F57C00',
            textposition='auto',
            text=[f"{stats['avg_g_score']:.1f}"]
        ),
    ])
    
    fig.update_layout(
        barmode='stack',
        title='E/S/G Score Composition',
        yaxis_title='Score (0-100)',
        xaxis_title='',
        height=300,
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig


def render_performance_comparison(df_performance, brand_palette):
    """
    Render building performance comparison chart.
    """
    if df_performance.empty:
        fig = go.Figure()
        fig.add_annotation(text="No performance data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    df_sorted = df_performance.sort_values('ESG Score', ascending=True).tail(15)
    
    fig = px.bar(
        df_sorted,
        x='ESG Score',
        y='Building',
        color='ESG Score',
        color_continuous_scale=['#D32F2F', '#FFA000', '#2E7D32'],
        range_color=[0, 100],
        hover_data=['Agent', 'E Score', 'S Score', 'G Score'],
        orientation='h'
    )
    
    fig.update_layout(
        title='Top 15 Buildings - ESG Performance Ranking',
        xaxis_title='ESG Score',
        yaxis_title='',
        height=500,
        showlegend=False,
        hovermode='closest'
    )
    
    return fig


def render_esg_bubble_chart(df_performance):
    """
    Render bubble chart showing ESG distribution.
    """
    if df_performance.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data for visualization", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    fig = px.scatter(
        df_performance,
        x='E Score',
        y='S Score',
        size='ESG Score',
        color='G Score',
        hover_name='Building',
        hover_data=['Agent', 'ESG Score', 'Waste (T)', 'Energy (kWh)'],
        color_continuous_scale='Viridis',
        size_max=50
    )
    
    fig.update_layout(
        title='ESG Scores Distribution (E vs S, sized by Overall Score, colored by G)',
        xaxis_title='Environmental Score',
        yaxis_title='Social Score',
        height=500,
        hovermode='closest'
    )
    
    return fig


def render_risk_matrix(df_performance):
    """
    Render risk matrix heatmap based on E and G scores.
    """
    if df_performance.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data for risk matrix", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Bin scores into risk categories
    df_performance['E_Category'] = pd.cut(df_performance['E Score'], 
                                          bins=[0, 33, 66, 100], 
                                          labels=['High Risk', 'Medium Risk', 'Low Risk'],
                                          ordered=True)
    df_performance['G_Category'] = pd.cut(df_performance['G Score'], 
                                          bins=[0, 33, 66, 100], 
                                          labels=['High Risk', 'Medium Risk', 'Low Risk'],
                                          ordered=True)
    
    # Create risk matrix
    risk_matrix = pd.crosstab(
        df_performance['E_Category'],
        df_performance['G_Category'],
        margins=False
    )
    
    fig = go.Figure(data=go.Heatmap(
        z=risk_matrix.values,
        x=risk_matrix.columns,
        y=risk_matrix.index,
        colorscale='Reds',
        text=risk_matrix.values,
        texttemplate='%{text}',
        textfont={"size": 14}
    ))
    
    fig.update_layout(
        title='Risk Matrix: Environmental vs Governance',
        xaxis_title='Governance Risk Level',
        yaxis_title='Environmental Risk Level',
        height=400
    )
    
    return fig


def render_trends(client_sel=None):
    """
    Render ESG score trends over time.
    """
    q = session.query(ESGEntry)
    if client_sel:
        q = q.filter(ESGEntry.client == client_sel)
    
    entries = q.order_by(ESGEntry.timestamp.desc()).limit(500).all()
    
    if not entries:
        fig = go.Figure()
        fig.add_annotation(text="No historical data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Aggregate by building and date
    trends = []
    for entry in entries:
        e, s, g, esg = compute_esg_scores(entry)
        trends.append({
            'Date': entry.timestamp.date(),
            'Building': entry.building,
            'ESG Score': esg,
            'E Score': e,
            'S Score': s,
            'G Score': g
        })
    
    df_trends = pd.DataFrame(trends)
    
    if df_trends.empty:
        fig = go.Figure()
        fig.add_annotation(text="No historical data available", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    
    # Average by date
    daily_avg = df_trends.groupby('Date')[['ESG Score', 'E Score', 'S Score', 'G Score']].mean()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=daily_avg.index,
        y=daily_avg['ESG Score'],
        mode='lines+markers',
        name='Overall ESG',
        line=dict(color='#1976D2', width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=daily_avg.index,
        y=daily_avg['E Score'],
        mode='lines',
        name='Environmental',
        line=dict(color='#2E7D32', dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=daily_avg.index,
        y=daily_avg['S Score'],
        mode='lines',
        name='Social',
        line=dict(color='#F57C00', dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=daily_avg.index,
        y=daily_avg['G Score'],
        mode='lines',
        name='Governance',
        line=dict(color='#C2185B', dash='dash')
    ))
    
    fig.update_layout(
        title='ESG Score Trends Over Time',
        xaxis_title='Date',
        yaxis_title='Score (0-100)',
        height=400,
        hovermode='x unified'
    )
    
    return fig


def render_dashboard(client_sel=None, brand_palette=None):
    """
    Render the complete ESG dashboard.
    
    Args:
        client_sel: Optional client to filter by
        brand_palette: Brand color palette
    """
    if brand_palette is None:
        brand_palette = {
            'brand_primary': '#102A43',
            'brand_accent': '#F5A623'
        }
    
    # Get data
    stats = get_portfolio_stats(client_sel)
    df_performance = get_building_performance(client_sel)
    
    # Page header
    st.markdown("""
    <style>
    .dashboard-header {
        background: linear-gradient(135deg, #102A43 0%, #1e3a5f 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .dashboard-title {
        color: #FFD700;
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0;
    }
    .dashboard-subtitle {
        color: #F5A623;
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
    }
    </style>
    <div class="dashboard-header">
        <h1 class="dashboard-title">📊 ESG Intelligence Dashboard</h1>
        <p class="dashboard-subtitle">Comprehensive Performance Analytics & Risk Assessment</p>
    </div>
    """, unsafe_allow_html=True)
    
    # KPI Cards
    st.subheader("🎯 Key Performance Indicators")
    render_kpi_cards(stats, brand_palette)
    
    st.divider()
    
    # Main visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(render_esg_breakdown(stats, brand_palette), width="stretch")
    
    with col2:
        if not df_performance.empty:
            fig = px.pie(
                values=[stats['avg_e_score'], stats['avg_s_score'], stats['avg_g_score']],
                names=['Environmental', 'Social', 'Governance'],
                color_discrete_map={'Environmental': '#2E7D32', 'Social': '#1976D2', 'Governance': '#F57C00'},
                title='ESG Weighting Distribution'
            )
            st.plotly_chart(fig, width="stretch")
    
    st.divider()
    
    # Performance comparison
    st.subheader("🏢 Building Performance Ranking")
    st.plotly_chart(render_performance_comparison(df_performance, brand_palette), width="stretch")
    
    st.divider()
    
    # Bubble chart and risk matrix
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribution Analysis")
        st.plotly_chart(render_esg_bubble_chart(df_performance), width="stretch")
    
    with col2:
        st.subheader("Risk Assessment")
        st.plotly_chart(render_risk_matrix(df_performance), width="stretch")
    
    st.divider()
    
    # Trends
    st.subheader("📈 Historical Trends")
    st.plotly_chart(render_trends(client_sel), width="stretch")
    
    st.divider()
    
    # Performance table
    st.subheader("📋 Detailed Building Metrics")
    
    if not df_performance.empty:
        # Create display DataFrame
        df_display = df_performance.copy()
        df_display['Last Updated'] = pd.to_datetime(df_display['Last Updated']).dt.strftime('%Y-%m-%d %H:%M')
        df_display = df_display.sort_values('ESG Score', ascending=False)
        
        # Format numeric columns
        numeric_cols = ['E Score', 'S Score', 'G Score', 'ESG Score', 'Waste (T)', 'Energy (kWh)']
        for col in numeric_cols:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(lambda x: f"{x:.1f}" if isinstance(x, float) else x)
        
        st.dataframe(
            df_display[['Building', 'Agent', 'ESG Score', 'E Score', 'S Score', 'G Score', 'Waste (T)', 'Energy (kWh)', 'Last Updated']],
            width="stretch",
            hide_index=True
        )
        
        # Export option
        csv = df_display.to_csv(index=False)
        st.download_button(
            label="📥 Download Performance Data (CSV)",
            data=csv,
            file_name=f"esg_performance_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No data available. Upload ESG metrics to see performance analytics.")
