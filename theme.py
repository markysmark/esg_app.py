import streamlit as st

def apply_theme():
    """
    Apply corporate ESG intelligence theme to Streamlit app.
    Uses custom CSS and Streamlit theming capabilities.
    """
    st.set_page_config(
        page_title="ESG Intelligence Platform",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        /* Main color scheme */
        :root {
            --primary-color: #102A43;
            --accent-color: #F5A623;
            --success-color: #2E7D32;
            --warning-color: #FFA000;
            --danger-color: #D32F2F;
            --info-color: #1976D2;
            --secondary-color: #1e3a5f;
            --light-bg: #F5F7FA;
            --dark-text: #1A1A1A;
            --light-text: #FFFFFF;
        }
        
        /* Page background */
        .main {
            background-color: #F5F7FA;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #102A43;
            color: white;
        }
        
        [data-testid="stSidebar"] label {
            color: white;
        }

        /* Ensure sidebar headings remain visible on the dark sidebar background */
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6 {
            color: white !important;
        }
        
        [data-testid="stSidebar"] .stSelectbox, 
        [data-testid="stSidebar"] .stTextInput,
        [data-testid="stSidebar"] .stNumberInput {
            color: #102A43;
        }
        
        /* Headers */
        h1, h2, h3, h4, h5, h6 {
            color: #102A43;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-weight: 600;
        }
        
        h1 {
            color: #F5A623;
            border-bottom: 3px solid #F5A623;
            padding-bottom: 10px;
        }
        
        /* Buttons */
        .stButton > button {
            background-color: #F5A623;
            color: white;
            font-weight: 600;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .stButton > button:hover {
            background-color: #E08A1F;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* Metric cards */
        [data-testid="metric-container"] {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-left: 4px solid #F5A623;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            background-color: #F0F2F6;
            border-radius: 6px;
            color: #102A43;
            font-weight: 600;
        }
        
        /* Tab styling */
        [data-baseweb="tab-list"] {
            background-color: white;
            border-bottom: 2px solid #E0E0E0;
        }
        
        [data-baseweb="tab"] {
            color: #102A43;
            font-weight: 500;
        }
        
        [aria-selected="true"] {
            color: #F5A623;
            border-bottom: 3px solid #F5A623;
        }
        
        /* Cards and containers */
        .esg-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-top: 4px solid #F5A623;
        }
        
        /* Input fields */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stSelectbox > div > div,
        .stDateInput > div > div > input,
        .stTextArea > div > div > textarea {
            border-radius: 6px;
            border: 1px solid #D0D0D0;
            padding: 10px;
            color: #1A1A1A !important;
            background-color: #FFFFFF !important;
        }

        /* Ensure all input/textarea elements always show black text */
        input, textarea {
            color: #1A1A1A !important;
        }

        /* Selectbox/dropdown selected value and option text */
        [data-baseweb="select"] span,
        [data-baseweb="select"] div,
        [data-baseweb="select"] input,
        [data-baseweb="popover"] li,
        [data-baseweb="popover"] [role="option"] {
            color: #1A1A1A !important;
        }

        /* Multiselect tags */
        [data-baseweb="tag"] span {
            color: #1A1A1A !important;
        }
        
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #F5A623;
            box-shadow: 0 0 0 2px rgba(245, 166, 35, 0.1);
        }
        
        /* Success/Error/Warning messages */
        .stAlert {
            border-radius: 6px;
            border-left: 4px solid;
        }
        
        /* Divider */
        hr {
            border: none;
            border-top: 2px solid #E8E8E8;
            margin: 20px 0;
        }
        
        /* Data table styling */
        [data-testid="dataframe"] {
            border-radius: 6px;
            overflow: hidden;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #F0F0F0;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #F5A623;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #E08A1F;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            h1 { font-size: 1.8rem !important; }
            h2 { font-size: 1.4rem !important; }
        }
    </style>
    """, unsafe_allow_html=True)

brand_palette = {
    "brand_primary": "#102A43",
    "brand_secondary": "#1e3a5f",
    "brand_accent": "#F5A623",
    "success_color": "#2E7D32",
    "warning_color": "#FFA000",
    "danger_color": "#D32F2F",
    "info_color": "#1976D2",
    "light_bg": "#F5F7FA",
    "dark_text": "#1A1A1A",
    "light_text": "#FFFFFF"
}
