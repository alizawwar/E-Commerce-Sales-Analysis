"""E-Commerce Analytics Dashboard (Phase 4).

An interactive BI layer over the ``ecommerce_sales_analysis`` MySQL database
built in Phase 3. No figure shown in the UI is hardcoded; every number comes
from a query in :mod:`dashboard.queries`.
"""

__all__ = ["config", "database", "queries", "metrics", "charts", "components", "utils"]
