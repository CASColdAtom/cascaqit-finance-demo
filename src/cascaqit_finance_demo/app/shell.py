"""Reusable Bokeh layout pieces for the finance workbench."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bokeh.layouts import column, row
from bokeh.models import Button, Div, Select

from cascaqit_finance_demo.app.theme import (
    BORDER,
    GREEN,
    MUTED,
    SURFACE,
    mobile_full_width_stylesheet,
)


def build_header() -> Div:
    """Create the stable product header and explicit execution-boundary labels."""
    return Div(
        text=(
            '<div style="min-height:58px;display:flex;align-items:center;'
            'justify-content:space-between;gap:16px;padding:10px 20px;flex-wrap:wrap">'
            '<div style="display:flex;align-items:baseline;gap:9px">'
            '<strong style="font-size:18px;font-weight:600">'
            "中科酷原行业量子实验台</strong>"
            f'<span style="color:{MUTED}">金融领域</span></div>'
            '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">'
            f'<span style="border:1px solid {BORDER};border-radius:5px;padding:5px 9px;'
            f'background:{SURFACE}"><span style="color:{GREEN}">●</span> '
            "实验环境 · 本地模拟</span>"
            f'<span style="border:1px solid {BORDER};border-radius:5px;padding:5px 9px;'
            f'background:{SURFACE}">合成数据</span>'
            f'<span style="border:1px solid {BORDER};border-radius:5px;padding:5px 9px;'
            f'background:{SURFACE};color:{MUTED}">未调用真实硬件</span>'
            "</div></div>"
        ),
        sizing_mode="stretch_width",
        css_classes=["app-header"],
    )


def build_case_navigation(
    selector: Select,
    on_select: Callable[[str], None],
) -> tuple[Any, dict[str, Button]]:
    """Build the prototype-style case rail with real Bokeh buttons."""
    cases = (
        ("portfolio", "01  投资组合", "QUBO · QAOA"),
        ("settlement", "02  交易结算", "QUBO · QAOA · Hybrid"),
        ("fraud_routing", "03  调查编排", "QUBO · QAOA"),
    )
    buttons: dict[str, Button] = {}
    items = []
    for case_id, label, method in cases:
        button = Button(
            label=label,
            button_type="success" if case_id == selector.value else "default",
            height=38,
            sizing_mode="stretch_width",
        )
        button.on_click(lambda case_id=case_id: on_select(case_id))
        buttons[case_id] = button
        items.append(
            column(
                button,
                Div(
                    text=f'<div style="color:{MUTED};font-size:12px">{method}</div>',
                    sizing_mode="stretch_width",
                ),
                spacing=3,
                width=120,
                styles={
                    "flex": "1 1 120px",
                    "padding": "6px",
                    "min-width": "120px",
                },
            )
        )
    item_grid = row(
        *items,
        spacing=0,
        sizing_mode="stretch_width",
        styles={"flex-wrap": "wrap", "align-content": "flex-start"},
    )
    navigation = column(
        Div(
            text=(
                f'<div style="color:{MUTED};font-size:12px;'
                'font-weight:600">金融案例</div>'
            )
        ),
        item_grid,
        width=205,
        min_width=205,
        spacing=8,
        css_classes=["case-navigation"],
        styles={
            "flex": "0 0 205px",
            "padding": "20px 12px",
            "background": "#e9eeeb",
            "border-right": f"1px solid {BORDER}",
        },
        stylesheets=[mobile_full_width_stylesheet()],
    )
    return navigation, buttons


def set_active_case(buttons: dict[str, Button], active_case: str) -> None:
    """Keep navigation state visible when a case changes from Python or JS."""
    for case_id, button in buttons.items():
        button.button_type = "success" if case_id == active_case else "default"


def panel_heading(title: str, description: str) -> Div:
    return Div(
        text=(
            f'<div><h2 style="margin:0;font-size:16px;font-weight:600">{title}</h2>'
            f'<p style="margin:6px 0 0;color:{MUTED}">{description}</p></div>'
        ),
        sizing_mode="stretch_width",
        styles={
            "display": "block",
            "width": "100%",
            "min-width": "0",
            "max-width": "100%",
            "overflow": "hidden",
        },
    )


def result_heading(title: str, description: str, badge: str) -> Div:
    return Div(
        text=(
            '<div style="display:flex;align-items:flex-start;'
            "justify-content:space-between;"
            'gap:16px;flex-wrap:wrap">'
            f'<div><h1 style="margin:0;font-size:22px;font-weight:600">{title}</h1>'
            f'<p style="max-width:760px;margin:6px 0 0;color:{MUTED}">'
            f"{description}</p></div>"
            f'<div style="color:{GREEN};white-space:nowrap">● {badge}</div></div>'
        ),
        sizing_mode="stretch_width",
        styles={
            "display": "block",
            "width": "100%",
            "min-width": "0",
            "max-width": "100%",
            "overflow": "hidden",
        },
    )


def model_strip(*items: tuple[str, str]) -> Div:
    cells = "".join(
        f'<span style="padding:0 14px;border-right:1px solid {BORDER};'
        'white-space:nowrap">'
        f'{label} <strong style="color:#17211c">{value}</strong></span>'
        for label, value in items
    )
    return Div(
        text=(
            f'<div style="display:flex;align-items:center;overflow-x:auto;'
            f"color:{MUTED};"
            f"padding:10px 0;border-top:1px solid {BORDER};"
            f'border-bottom:1px solid {BORDER}">{cells}</div>'
        ),
        sizing_mode="stretch_width",
        styles={
            "display": "block",
            "width": "100%",
            "min-width": "0",
            "max-width": "100%",
            "overflow": "hidden",
        },
    )
