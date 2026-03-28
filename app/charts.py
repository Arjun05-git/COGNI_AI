from __future__ import annotations

from datetime import date, datetime
from typing import Any

import plotly.graph_objects as go


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_date_like(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    return isinstance(value, str) and any(char.isdigit() for char in value) and "-" in value


def build_chart_payload(columns: list[str], rows: list[list[Any]]) -> tuple[dict[str, Any] | None, str | None]:
    if len(columns) < 2 or not rows:
        return None, None

    x_values = [row[0] for row in rows]
    y_values = [row[1] for row in rows]

    if not all(_is_numeric(value) for value in y_values):
        return None, None

    chart_type = "line" if all(_is_date_like(value) for value in x_values) else "bar"
    if chart_type == "line":
        figure = go.Figure(data=[go.Scatter(x=x_values, y=y_values, mode="lines+markers")])
    else:
        figure = go.Figure(data=[go.Bar(x=x_values, y=y_values)])

    figure.update_layout(
        title=f"{columns[1].replace('_', ' ').title()} by {columns[0].replace('_', ' ').title()}",
        xaxis_title=columns[0].replace("_", " ").title(),
        yaxis_title=columns[1].replace("_", " ").title(),
        template="plotly_white",
    )
    return figure.to_plotly_json(), chart_type
