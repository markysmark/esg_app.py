import pandas as pd
import plotly.graph_objects as go

from dashboard import render_performance_comparison


def test_render_performance_comparison_uses_horizontal_bar():
    df = pd.DataFrame(
        [
            {"Building": "One", "Agent": "Savills", "ESG Score": 75, "E Score": 70, "S Score": 80, "G Score": 65},
            {"Building": "Two", "Agent": "CBRE", "ESG Score": 60, "E Score": 55, "S Score": 65, "G Score": 58},
        ]
    )

    fig = render_performance_comparison(df, brand_palette={"brand_primary": "#000"})

    assert isinstance(fig, go.Figure)
    assert any(getattr(trace, "orientation", None) == "h" for trace in fig.data)
