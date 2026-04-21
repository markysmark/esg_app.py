import os
import streamlit as st

# ---------------------------------------------------------------------------
# Logo asset paths – relative to the application's working directory.
# ---------------------------------------------------------------------------
LOGO_MAIN = os.path.join("assets", "logo-main.svg")
LOGO_EXECUTIVE = os.path.join("assets", "logo-executive.svg")
LOGO_MARK = os.path.join("assets", "logo-mark.svg")


def render_sidebar_logo(executive: bool = False) -> None:
    """Render the Nexus-Opus logo at the top of the sidebar.

    Uses the executive (gold-accent) variant when *executive* is ``True``,
    otherwise renders the standard teal-accent logo.  Falls back to an
    inline HTML text mark when the SVG asset file is not found.
    """
    logo_path = LOGO_EXECUTIVE if executive else LOGO_MAIN
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, use_container_width=True)
    else:
        # Graceful text fallback when the SVG asset is missing
        accent = "#D97706" if executive else "#0D9488"
        st.sidebar.markdown(
            f"<div style='text-align:center; padding:14px 0 6px 0;'>"
            f"<span style='color:#FFFFFF;font-size:18px;font-weight:700;"
            f"letter-spacing:2.5px;font-family:\"Segoe UI\",sans-serif;'>"
            f"NEXUS</span><br/>"
            f"<span style='color:{accent};font-size:11px;letter-spacing:3.5px;"
            f"font-family:\"Segoe UI\",sans-serif;'>OPUS</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


def apply_theme():
    """Apply the Nexus-Opus brand theme to the Streamlit application."""
    st.set_page_config(
        page_title="Nexus-Opus | ESG Intelligence",
        page_icon="🔗",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS – Nexus-Opus Design System
    # Primary:   Deep Slate Navy  #1A202C
    # Action:    Kinetic Teal     #0D9488
    # Accent:    Amber Gold       #D97706  (executive / alerts)
    # Surface:   Frosted Silver   #E2E8F0
    # Success:   Emerald          #059669
    st.markdown("""
    <style>
        /* ── Nexus-Opus design tokens ───────────────────────────────── */
        :root {
            --nexus-navy:    #1A202C;
            --nexus-teal:    #0D9488;
            --nexus-teal-dk: #0B7A71;
            --opus-gold:     #D97706;
            --opus-gold-dk:  #B45309;
            --surface:       #E2E8F0;
            --bg-main:       #F8FAFC;
            --success:       #059669;
            --warning:       #FFA000;
            --danger:        #DC2626;
            --info:          #2563EB;
            --dark-text:     #1A1A1A;
            --light-text:    #FFFFFF;
        }

        /* ── Page background ─────────────────────────────────────────── */
        .main { background-color: var(--bg-main); }

        /* ── Sidebar ─────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background-color: var(--nexus-navy);
            color: white;
        }
        [data-testid="stSidebar"] label { color: white; }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6 { color: white !important; }
        [data-testid="stSidebar"] .stSelectbox,
        [data-testid="stSidebar"] .stTextInput,
        [data-testid="stSidebar"] .stNumberInput { color: var(--nexus-navy); }

        /* ── Typography ──────────────────────────────────────────────── */
        h1, h2, h3, h4, h5, h6 {
            color: var(--nexus-navy);
            font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-weight: 600;
        }
        h1 {
            color: var(--nexus-teal);
            border-bottom: 3px solid var(--nexus-teal);
            padding-bottom: 10px;
        }

        /* ── Buttons ─────────────────────────────────────────────────── */
        .stButton > button {
            background-color: var(--nexus-teal);
            color: white;
            font-weight: 600;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stButton > button:hover {
            background-color: var(--nexus-teal-dk);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }

        /* ── Metric cards ────────────────────────────────────────────── */
        [data-testid="metric-container"] {
            background-color: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            border-left: 4px solid var(--nexus-teal);
        }

        /* ── Expander ────────────────────────────────────────────────── */
        .streamlit-expanderHeader {
            background-color: #EEF2F7;
            border-radius: 6px;
            color: var(--nexus-navy);
            font-weight: 600;
        }

        /* ── Tabs ────────────────────────────────────────────────────── */
        [data-baseweb="tab-list"] {
            background-color: white;
            border-bottom: 2px solid var(--surface);
        }
        [data-baseweb="tab"] {
            color: var(--nexus-navy);
            font-weight: 500;
        }
        [aria-selected="true"] {
            color: var(--nexus-teal);
            border-bottom: 3px solid var(--nexus-teal);
        }

        /* ── Card component ──────────────────────────────────────────── */
        .esg-card {
            background: #FFFFFF;
            border: 1px solid var(--surface);
            border-radius: 12px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.07);
            border-top: 4px solid var(--nexus-teal);
        }

        /* ── Input fields ────────────────────────────────────────────── */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stSelectbox > div > div,
        .stDateInput > div > div > input,
        .stTextArea > div > div > textarea {
            border-radius: 6px;
            border: 1px solid #D0D0D0;
            padding: 10px;
            color: var(--dark-text) !important;
            background-color: #FFFFFF !important;
        }
        input, textarea { color: var(--dark-text) !important; }
        [data-baseweb="select"] span,
        [data-baseweb="select"] div,
        [data-baseweb="select"] input,
        [data-baseweb="popover"] li,
        [data-baseweb="popover"] [role="option"] { color: var(--dark-text) !important; }
        [data-baseweb="tag"] span { color: var(--dark-text) !important; }
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: var(--nexus-teal);
            box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.15);
        }

        /* ── Alerts ──────────────────────────────────────────────────── */
        .stAlert { border-radius: 6px; border-left: 4px solid; }

        /* ── Divider ─────────────────────────────────────────────────── */
        hr { border: none; border-top: 2px solid #E8E8E8; margin: 20px 0; }

        /* ── Data table ──────────────────────────────────────────────── */
        [data-testid="dataframe"] { border-radius: 6px; overflow: hidden; }

        /* ── Scrollbar ───────────────────────────────────────────────── */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #F0F0F0; }
        ::-webkit-scrollbar-thumb { background: var(--nexus-teal); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--nexus-teal-dk); }

        /* ── Responsive ──────────────────────────────────────────────── */
        @media (max-width: 768px) {
            h1 { font-size: 1.8rem !important; }
            h2 { font-size: 1.4rem !important; }
        }
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Nexus-Opus brand palette – shared across modules
# ---------------------------------------------------------------------------
brand_palette = {
    # Core brand
    "brand_primary":   "#1A202C",   # Deep Slate Navy
    "brand_secondary": "#2D3748",   # Secondary Navy
    "brand_action":    "#0D9488",   # Kinetic Teal (buttons, active states)
    "brand_accent":    "#D97706",   # Amber Gold (executive / premium)
    # Semantic
    "success_color":   "#059669",   # Emerald
    "warning_color":   "#FFA000",   # Amber
    "danger_color":    "#DC2626",   # Red
    "info_color":      "#2563EB",   # Blue
    # Surfaces
    "surface":         "#E2E8F0",   # Frosted Silver
    "light_bg":        "#F8FAFC",   # Off-white background
    "dark_text":       "#1A1A1A",
    "light_text":      "#FFFFFF",
}
