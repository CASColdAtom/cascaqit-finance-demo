"""Visual system for the finance demo workbench.

The Bokeh models remain responsible for interaction and plotting. This module
only owns page-level layout, color, typography, and responsive behavior so the
three cases share one coherent interface.
"""

from __future__ import annotations

from bokeh.models import InlineStyleSheet
from bokeh.themes import Theme

GREEN = "#146c43"
GREEN_DARK = "#0d5533"
BLUE = "#2568a8"
AMBER = "#b66f12"
RED = "#b4473d"
VIOLET = "#7256a3"
MUTED = "#5c6b64"
SURFACE = "#ffffff"
BACKGROUND = "#f4f6f5"
SURFACE_SOFT = "#edf2ef"
BORDER = "#d7dfda"
GRID = "#e5eae7"


APP_TEMPLATE = """
{% block preamble %}
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {
  color-scheme: light;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
  font-size: 14px;
  background: #f4f6f5;
  color: #17211c;
}

* { box-sizing: border-box; }

html, body {
  width: 100%;
  min-width: 320px;
  margin: 0;
  padding: 0;
  overflow-x: clip;
  background: #f4f6f5;
  color: #17211c;
}

body { min-height: 100vh; }

.app-root { width: 100%; min-width: 0; }
.app-header { min-height: 58px; background: #ffffff; border-bottom: 1px solid #d7dfda; }
.workspace-shell { min-width: 0; align-items: stretch; }
.case-navigation {
  min-height: calc(100vh - 58px);
  background: #e9eeeb;
  border-right: 1px solid #d7dfda;
}
.case-body { min-width: 0; }
.case-workspace { min-width: 0; align-items: stretch; }
.control-panel {
  min-width: 300px;
  background: #ffffff;
  border-right: 1px solid #d7dfda;
}
.result-panel { min-width: 0; background: #f4f6f5; }
.metric-row { min-width: 0; }
.result-tabs { min-width: 0; }

@media (max-width: 760px) {
  .case-navigation {
    width: 100% !important;
    min-width: 100% !important;
    flex: 1 1 100% !important;
    min-height: auto;
    border-right: 0;
    border-bottom: 1px solid #d7dfda;
  }
  .case-body, .case-workspace, .control-panel, .result-panel {
    width: 100% !important;
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }
  .control-panel { border-right: 0; border-bottom: 1px solid #d7dfda; }
}
</style>
{% endblock %}
"""


def finance_theme() -> Theme:
    """Return the shared Bokeh theme used by every finance case."""
    return Theme(
        json={
            "attrs": {
                "figure": {
                    "background_fill_color": SURFACE,
                    "border_fill_color": SURFACE,
                    "outline_line_color": BORDER,
                    "outline_line_width": 1,
                    # The embedded toolbar overflows narrow plots and duplicates
                    # actions that are not part of the guided demo workflow.
                    "toolbar_location": None,
                },
                "grid": {"grid_line_color": GRID, "grid_line_alpha": 0.9},
                "axis": {
                    "axis_line_color": BORDER,
                    "major_tick_line_color": BORDER,
                    "minor_tick_line_color": None,
                    "major_label_text_color": MUTED,
                    "axis_label_text_color": "#33423a",
                },
                "title": {
                    "text_color": "#17211c",
                    "text_font_size": "14px",
                    "text_font_style": "normal",
                },
            }
        }
    )


def mobile_full_width_stylesheet() -> InlineStyleSheet:
    """Force one Bokeh layout host onto its own row on narrow screens.

    Bokeh renders every layout model inside a Shadow DOM. A template-level
    media query cannot reach those hosts, so responsive host rules must travel
    with the model itself.
    """
    return InlineStyleSheet(
        css="""
        @media (max-width: 760px) {
          :host {
            box-sizing: border-box;
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
          }
        }
        """
    )


def block_div_stylesheet() -> InlineStyleSheet:
    """Make Bokeh Div content fill the width allocated by its layout host."""
    return InlineStyleSheet(
        css="""
        .bk-clearfix {
          box-sizing: border-box;
          display: block !important;
          width: 100% !important;
          min-width: 0 !important;
        }
        """
    )


def primary_button_stylesheet() -> InlineStyleSheet:
    """Use the workbench primary color for case execution actions."""
    return InlineStyleSheet(
        css="""
        .bk-btn-success {
          background-color: #146c43 !important;
          border-color: #146c43 !important;
          color: #ffffff !important;
        }
        .bk-btn-success:hover {
          background-color: #0d5533 !important;
          border-color: #0d5533 !important;
        }
        """
    )
