"""Page modules for the dashboard.

Named ``views`` rather than ``pages`` on purpose: a folder called ``pages``
next to the entry script is picked up by Streamlit's built-in multipage
navigation, which would conflict with the custom sidebar navigation defined in
``app.py``.
"""

from . import customers, insights, orders, overview, payments, products, sales

__all__ = ["overview", "sales", "products", "customers", "orders", "payments", "insights"]
