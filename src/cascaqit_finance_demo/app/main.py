"""Bokeh Server entry point."""

from bokeh.io import curdoc

from cascaqit_finance_demo.app.factory import build_document

build_document(curdoc())
