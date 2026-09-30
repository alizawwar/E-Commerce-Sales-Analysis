"""
validate_dataset.py
===================

Checks the five CSV files in ../data/ for data quality and referential
integrity problems BEFORE any analysis is done.

Checks performed:

  * files exist and can be read
  * expected columns are present
  * missing values
  * duplicate primary keys
  * invalid foreign keys
  * invalid / unparsable dates
  * negative prices, costs, quantities, stock
  * impossible discounts
  * cost higher than price (would create a negative margin)
  * invalid order statuses
  * invalid payment statuses
  * invalid payment methods
  * orphan order_items (order_id or product_id not found)
  * orphan payments (order_id not found)
  * orders without any order_items or payments
  * duplicate products inside a single order
  * payment dates before the order date
  * shipping cities that are not real cities
  * a sample of "does it look realistic" checks

Every check prints PASS or FAIL. The script exits with code 1 if any
check fails, so it can be used in a pipeline later.

Usage:
    python scripts/validate_dataset.py
"""

import os
import re
import sys

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1. SETTINGS
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

EXPECTED_COLUMNS = {
    "customers.csv": [
        "customer_id", "name", "email", "gender", "age", "city", "signup_date",
    ],
    "products.csv": [
        "product_id", "product_name", "category", "subcategory",
        "brand", "price", "cost", "stock_quantity",
    ],
    "orders.csv": [
        "order_id", "customer_id", "order_date", "status", "shipping_city",
    ],
    "order_items.csv": [
        "order_item_id", "order_id", "product_id",
        "quantity", "unit_price", "discount_percent",
    ],
    "payments.csv": [
        "payment_id", "order_id", "payment_method",
        "payment_status", "payment_date",
    ],
}

PRIMARY_KEYS = {
    "customers.csv": "customer_id",
    "products.csv": "product_id",
    "orders.csv": "order_id",
    "order_items.csv": "order_item_id",
    "payments.csv": "payment_id",
}

VALID_ORDER_STATUSES = {"Completed", "Pending", "Cancelled", "Returned"}
VALID_PAYMENT_STATUSES = {"Paid", "Pending", "Failed", "Refunded"}
VALID_PAYMENT_METHODS = {
    "Cash on Delivery", "Credit Card", "Debit Card",
    "Bank Transfer", "JazzCash", "EasyPaisa",
}
VALID_CATEGORIES = {
    "Electronics", "Computers", "Mobile Accessories", "Home Appliances",
    "Fashion", "Beauty", "Sports", "Books", "Grocery", "Home & Kitchen",
}
VALID_GENDERS = {"Male", "Female"}

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# Row counts the dataset is expected to be in
EXPECTED_ROW_RANGE = {
    "customers.csv": (1_000, 2_000),
    "products.csv": (250, 350),
    "orders.csv": (11_000, 13_000),
    "order_items.csv": (25_000, 35_000),
    "payments.csv": (11_000, 13_000),
}

VALID_CITIES = {
    "Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad",
    "Gujranwala", "Multan", "Peshawar", "Quetta", "Sialkot", "Hyderabad",
    "Bahawalpur", "Sargodha", "Abbottabad", "Sukkur", "Sahiwal",
    "Mirpur Khas", "Rahim Yar Khan", "Mardan", "Gwadar",
}

results = []   # list of (section, check name, passed, message, filename)


# ---------------------------------------------------------------------------
# 2. SMALL HELPERS
# ---------------------------------------------------------------------------

def record(section, name, passed, message="", filename=None):
    """Store the result of one check so it can be printed in the summary."""
    results.append((section, name, bool(passed), message, filename))


def check(section, name, passed, message="", filename=None):
    """Record a check and print it immediately."""
    record(section, name, passed, message, filename)
    mark = "PASS" if passed else "FAIL"
    line = f"  [{mark}] {name}"
    if message:
        line += f" - {message}"
    print(line)
    return passed


def fail_count():
    return sum(1 for _, _, passed, _, _ in results if not passed)


def header(text):
    print("\n" + text)
    print("-" * len(text))


def parse_dates(values):
    """Parse dates safely. Bad values become NaT instead of raising an error,
    so the validator can report the problem instead of crashing."""
    return pd.to_datetime(pd.Series(values), errors="coerce")


# ---------------------------------------------------------------------------
# 3. LOAD THE DATA
# ---------------------------------------------------------------------------

def load_data():
    """Read every CSV file, reporting anything that is missing or unreadable."""
    header("STEP 1  Loading the CSV files")

    data = {}
    all_readable = True

    for filename in EXPECTED_COLUMNS:
        path = os.path.join(DATA_DIR, filename)

        if not os.path.exists(path):
            check("Files", f"{filename} exists", False, "file not found")
            all_readable = False
            continue

        try:
            frame = pd.read_csv(path)
        except Exception as error:                      # noqa: BLE001
            check("Files", f"{filename} can be read", False, str(error))
            all_readable = False
            continue

        data[filename] = frame
        check(
            "Files",
            f"{filename} loaded",
            True,
            f"{len(frame):,} rows x {len(frame.columns)} columns",
            filename,
        )

    if not all_readable or len(data) != len(EXPECTED_COLUMNS):
        return None

    # --- columns ---------------------------------------------------------
    for filename, expected in EXPECTED_COLUMNS.items():
        actual = list(data[filename].columns)
        check(
            "Columns",
            f"{filename} has the expected columns",
            actual == expected,
            "" if actual == expected else f"found {actual}",
            filename,
        )

    return data


# ---------------------------------------------------------------------------
# 4. SCHEMA, ROW COUNTS, MISSING VALUES, DUPLICATE KEYS
# ---------------------------------------------------------------------------

def check_structure(data):
    header("STEP 2  Row counts")

    for filename, (low, high) in EXPECTED_ROW_RANGE.items():
        rows = len(data[filename])
        check(
            "Row counts",
            f"{filename} row count between {low:,} and {high:,}",
            low <= rows <= high,
            f"{rows:,} rows",
            filename,
        )

    header("STEP 3  Missing values")

    for filename, frame in data.items():
        missing = frame.isna().sum()
        total_missing = int(missing.sum())
        check(
            "Missing values",
            f"{filename} has no missing values",
            total_missing == 0,
            f"{total_missing} missing"
            + (f" -> {missing[missing > 0].to_dict()}" if total_missing else ""),
            filename,
        )

    header("STEP 4  Duplicate primary keys")

    for filename, key in PRIMARY_KEYS.items():
        duplicates = int(data[filename][key].duplicated().sum())
        check(
            "Primary keys",
            f"{filename}.{key} is unique",
            duplicates == 0,
            f"{duplicates} duplicates" if duplicates else "all unique",
            filename,
        )


# ---------------------------------------------------------------------------
# 5. DATA TYPES AND DATES
# ---------------------------------------------------------------------------

def check_types_and_dates(data):
    header("STEP 5  Numeric columns")

    numeric_columns = {
        "customers.csv": ["age"],
        "products.csv": ["price", "cost", "stock_quantity"],
        "order_items.csv": ["quantity", "unit_price", "discount_percent"],
    }
    for filename, columns in numeric_columns.items():
        for column in columns:
            is_numeric = pd.api.types.is_numeric_dtype(data[filename][column])
            check(
                "Types",
                f"{filename}.{column} is numeric",
                is_numeric,
                str(data[filename][column].dtype),
                filename,
            )

    header("STEP 6  Dates are valid and parsable")

    date_columns = {
        "customers.csv": ["signup_date"],
        "orders.csv": ["order_date"],
        "payments.csv": ["payment_date"],
    }
    parsed = {}

    for filename, columns in date_columns.items():
        for column in columns:
            values = parse_dates(data[filename][column])
            bad = int(values.isna().sum())
            bad_dates = data[filename][column][values.isna()].tolist()
            parsed[(filename, column)] = values

            # The raw text must also be in YYYY-MM-DD form, not another format
            wrong_format = [
                str(value) for value in data[filename][column]
                if pd.notna(value) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value))
            ]

            ok = bad == 0 and not wrong_format
            if ok:
                message = f"{values.min().date()} to {values.max().date()}"
            elif bad:
                message = f"{bad} unparsable values, e.g. {bad_dates[:3]}"
            else:
                message = f"{len(wrong_format)} wrong format, e.g. {wrong_format[:3]}"

            check(
                "Dates",
                f"{filename}.{column} is a real date in YYYY-MM-DD format",
                ok,
                message,
                filename,
            )

    return parsed


# ---------------------------------------------------------------------------
# 6. BUSINESS RULES
# ---------------------------------------------------------------------------

def check_business_rules(data, parsed_dates):
    customers = data["customers.csv"]
    products = data["products.csv"]
    orders = data["orders.csv"]
    order_items = data["order_items.csv"]
    payments = data["payments.csv"]

    header("STEP 7  Value ranges and impossible values")

    # --- customers -------------------------------------------------------
    age_ok = bool(customers["age"].between(18, 75).all())
    check(
        "Values",
        "customers.age is between 18 and 75",
        age_ok,
        f"min={customers['age'].min()} max={customers['age'].max()}" if age_ok
        else f"out of range: {sorted(customers.loc[~customers['age'].between(18, 75), 'age'].unique())}",
        "customers.csv",
    )
    check(
        "Values",
        "customers.gender is a valid value",
        set(customers["gender"]) <= VALID_GENDERS,
        f"found {sorted(set(customers['gender']))}",
        "customers.csv",
    )
    bad_emails = [email for email in customers["email"] if not EMAIL_PATTERN.match(str(email))]
    check(
        "Values",
        "customers.email is a valid email format",
        not bad_emails,
        f"{len(bad_emails)} invalid, e.g. {bad_emails[:3]}" if bad_emails else "all valid",
        "customers.csv",
    )

    # --- products --------------------------------------------------------
    negative_price = products[products["price"] <= 0]
    check(
        "Values",
        "products.price is never zero or negative",
        negative_price.empty,
        f"{len(negative_price)} invalid" if not negative_price.empty
        else f"min={products['price'].min():,.0f} max={products['price'].max():,.0f} PKR",
        "products.csv",
    )
    negative_cost = products[products["cost"] <= 0]
    check(
        "Values",
        "products.cost is never zero or negative",
        negative_cost.empty,
        f"{len(negative_cost)} invalid" if not negative_cost.empty
        else f"min={products['cost'].min():,.0f} max={products['cost'].max():,.0f} PKR",
        "products.csv",
    )
    bad_margin = products[products["cost"] >= products["price"]]
    check(
        "Values",
        "products.cost is lower than products.price",
        bad_margin.empty,
        f"{len(bad_margin)} products with cost >= price" if not bad_margin.empty
        else "all margins positive",
        "products.csv",
    )
    margin_pct = ((products["price"] - products["cost"]) / products["price"] * 100)
    check(
        "Values",
        "product margins vary (not all identical)",
        margin_pct.round(1).nunique() > 20,
        f"margin from {margin_pct.min():.0f}% to {margin_pct.max():.0f}%",
        "products.csv",
    )
    negative_stock = products[products["stock_quantity"] < 0]
    check(
        "Values",
        "products.stock_quantity is never negative",
        negative_stock.empty,
        f"{len(negative_stock)} invalid",
        "products.csv",
    )
    bad_category = set(products["category"]) - VALID_CATEGORIES
    check(
        "Values",
        "products.category is a valid category",
        not bad_category,
        f"unexpected: {bad_category}" if bad_category else f"{products['category'].nunique()} categories",
        "products.csv",
    )
    duplicate_names = int(products["product_name"].duplicated().sum())
    check(
        "Values",
        "products.product_name is unique",
        duplicate_names == 0,
        f"{duplicate_names} duplicates" if duplicate_names else "all unique",
        "products.csv",
    )

    # --- order items -----------------------------------------------------
    bad_quantity = order_items[order_items["quantity"] <= 0]
    check(
        "Values",
        "order_items.quantity is at least 1",
        bad_quantity.empty,
        f"{len(bad_quantity)} rows with quantity <= 0" if not bad_quantity.empty
        else f"min={order_items['quantity'].min()} max={order_items['quantity'].max()}",
        "order_items.csv",
    )
    check(
        "Values",
        "order_items.quantity is a whole number",
        bool((order_items["quantity"] % 1 == 0).all()),
        "order_items.csv",
    )
    bad_price = order_items[order_items["unit_price"] <= 0]
    check(
        "Values",
        "order_items.unit_price is never zero or negative",
        bad_price.empty,
        f"{len(bad_price)} invalid" if not bad_price.empty
        else f"min={order_items['unit_price'].min():,.0f} max={order_items['unit_price'].max():,.0f} PKR",
        "order_items.csv",
    )
    bad_discount = order_items[
        (order_items["discount_percent"] < 0) | (order_items["discount_percent"] > 100)
    ]
    check(
        "Values",
        "order_items.discount_percent is between 0 and 100",
        bad_discount.empty,
        f"{len(bad_discount)} invalid" if not bad_discount.empty
        else f"values used: {sorted(int(value) for value in order_items['discount_percent'].unique())}",
        "order_items.csv",
    )
    check(
        "Values",
        "order_items.discount_percent is mostly 0-30",
        bool((order_items["discount_percent"] <= 30).mean() > 0.95),
        f"{(order_items['discount_percent'] <= 30).mean():.1%} of lines are 0-30",
        "order_items.csv",
    )

    # --- orders ----------------------------------------------------------
    bad_status = set(orders["status"]) - VALID_ORDER_STATUSES
    check(
        "Values",
        "orders.status is a valid order status",
        not bad_status,
        f"unexpected: {bad_status}" if bad_status else f"{sorted(orders['status'].unique())}",
        "orders.csv",
    )
    completed_share = (orders["status"] == "Completed").mean()
    check(
        "Values",
        "Completed is the most common order status",
        bool(completed_share > 0.5),
        f"{completed_share:.1%} completed",
        "orders.csv",
    )

    # --- payments --------------------------------------------------------
    bad_method = set(payments["payment_method"]) - VALID_PAYMENT_METHODS
    check(
        "Values",
        "payments.payment_method is a valid payment method",
        not bad_method,
        f"unexpected: {bad_method}" if bad_method else f"{sorted(payments['payment_method'].unique())}",
        "payments.csv",
    )
    bad_payment_status = set(payments["payment_status"]) - VALID_PAYMENT_STATUSES
    check(
        "Values",
        "payments.payment_status is a valid payment status",
        not bad_payment_status,
        f"unexpected: {bad_payment_status}" if bad_payment_status
        else f"{sorted(payments['payment_status'].unique())}",
        "payments.csv",
    )


# ---------------------------------------------------------------------------
# 7. FOREIGN KEYS AND RELATIONSHIPS
# ---------------------------------------------------------------------------

def check_relationships(data, parsed_dates):
    customers = data["customers.csv"]
    products = data["products.csv"]
    orders = data["orders.csv"]
    order_items = data["order_items.csv"]
    payments = data["payments.csv"]

    header("STEP 8  Foreign keys")

    # orders.customer_id -> customers.customer_id
    orphan_orders = orders[~orders["customer_id"].isin(customers["customer_id"])]
    check(
        "Foreign keys",
        "orders.customer_id exists in customers",
        orphan_orders.empty,
        f"{len(orphan_orders)} orphan orders" if not orphan_orders.empty
        else f"{orders['customer_id'].nunique():,} customers linked",
        "orders.csv",
    )

    # order_items.order_id -> orders.order_id
    orphan_items = order_items[~order_items["order_id"].isin(orders["order_id"])]
    check(
        "Foreign keys",
        "order_items.order_id exists in orders (no orphan order_items)",
        orphan_items.empty,
        f"{len(orphan_items)} orphan order items" if not orphan_items.empty
        else f"{order_items['order_id'].nunique():,} orders linked",
        "order_items.csv",
    )

    # order_items.product_id -> products.product_id
    orphan_products = order_items[~order_items["product_id"].isin(products["product_id"])]
    check(
        "Foreign keys",
        "order_items.product_id exists in products",
        orphan_products.empty,
        f"{len(orphan_products)} orphan order items" if not orphan_products.empty
        else f"{order_items['product_id'].nunique():,} products linked",
        "order_items.csv",
    )

    # payments.order_id -> orders.order_id
    orphan_payments = payments[~payments["order_id"].isin(orders["order_id"])]
    check(
        "Foreign keys",
        "payments.order_id exists in orders (no orphan payments)",
        orphan_payments.empty,
        f"{len(orphan_payments)} orphan payments" if not orphan_payments.empty
        else f"{payments['order_id'].nunique():,} orders linked",
        "payments.csv",
    )

    header("STEP 9  Relationship completeness")

    # every order has at least one order item
    orders_without_items = orders[~orders["order_id"].isin(order_items["order_id"])]
    check(
        "Relationships",
        "every order has at least one order item",
        orders_without_items.empty,
        f"{len(orders_without_items)} empty orders" if not orders_without_items.empty
        else f"all {len(orders):,} orders have items",
        "orders.csv",
    )

    # every order has exactly one payment record
    payment_counts = payments.groupby("order_id").size()
    orders_without_payment = orders[~orders["order_id"].isin(payments["order_id"])]
    double_payments = payment_counts[payment_counts > 1]
    check(
        "Relationships",
        "every order has a payment record",
        orders_without_payment.empty,
        f"{len(orders_without_payment)} orders without payment" if not orders_without_payment.empty
        else f"all {len(orders):,} orders have one",
        "payments.csv",
    )
    check(
        "Relationships",
        "no order has more than one payment record",
        double_payments.empty,
        f"{len(double_payments)} orders with multiple payments" if not double_payments.empty
        else "exactly one payment per order",
        "payments.csv",
    )

    # no duplicate product inside the same order
    duplicate_lines = order_items.duplicated(subset=["order_id", "product_id"]).sum()
    check(
        "Relationships",
        "no duplicate product within an order",
        duplicate_lines == 0,
        f"{duplicate_lines} duplicates" if duplicate_lines else "all unique",
        "order_items.csv",
    )

    # every order item resolves to a real category
    category_of = dict(zip(products["product_id"], products["category"]))
    item_categories = order_items["product_id"].map(category_of)
    check(
        "Relationships",
        "every order item resolves to a real category",
        item_categories.notna().all(),
        "order_items.csv",
    )

    header("STEP 10  Date logic")

    signup = parsed_dates[("customers.csv", "signup_date")]
    order_date = parsed_dates[("orders.csv", "order_date")]
    payment_date = parsed_dates[("payments.csv", "payment_date")]

    signup_by_customer = dict(zip(customers["customer_id"], signup))
    customer_signup = orders["customer_id"].map(signup_by_customer)
    too_early = customer_signup > order_date
    check(
        "Date logic",
        "no order is placed before the customer signed up",
        not bool(too_early.any()),
        f"{int(too_early.sum())} orders before signup" if too_early.any()
        else "signup always before first order",
        "orders.csv",
    )

    order_date_by_id = dict(zip(orders["order_id"], order_date))
    linked_order_date = payments["order_id"].map(order_date_by_id)
    paid_before_order = payment_date < linked_order_date
    check(
        "Date logic",
        "no payment is made before its order",
        not bool(paid_before_order.any()),
        f"{int(paid_before_order.sum())} payments before order" if paid_before_order.any()
        else "payment always on or after order date",
        "payments.csv",
    )

    span = order_date.max() - order_date.min()
    check(
        "Date logic",
        "order dates cover roughly two years",
        bool(pd.notna(span) and span.days >= 700),
        f"{span.days} days ({order_date.min().date()} to {order_date.max().date()})"
        if pd.notna(span) else "no usable order dates",
        "orders.csv",
    )
    signup_span = signup.max() - signup.min()
    check(
        "Date logic",
        "signup dates cover more than one year",
        bool(pd.notna(signup_span) and signup_span.days >= 365),
        f"{signup_span.days} days" if pd.notna(signup_span) else "no usable signup dates",
        "customers.csv",
    )


# ---------------------------------------------------------------------------
# 8. DOES IT LOOK REALISTIC?
# ---------------------------------------------------------------------------

def check_realism(data):
    customers = data["customers.csv"]
    products = data["products.csv"]
    orders = data["orders.csv"]
    order_items = data["order_items.csv"]
    payments = data["payments.csv"]

    header("STEP 11  Realism checks (warnings, not errors)")

    def warn(name, passed, message):
        mark = "OK  " if passed else "WARN"
        print(f"  [{mark}] {name} - {message}")
        record("Realism", name, passed, message, None)

    city_counts = customers["city"].value_counts()
    warn(
        "customer cities are not evenly distributed",
        city_counts.max() > city_counts.min(),
        f"most common={city_counts.index[0]} ({city_counts.iloc[0]}), "
        f"least common={city_counts.index[-1]} ({city_counts.iloc[-1]})",
    )

    orders_per_customer = orders["customer_id"].value_counts()
    warn(
        "some customers order much more than others",
        bool(orders_per_customer.max() > orders_per_customer.min() * 3),
        f"min={orders_per_customer.min()} median={int(orders_per_customer.median())} "
        f"max={orders_per_customer.max()} orders per customer",
    )

    items_per_product = order_items["product_id"].value_counts()
    warn(
        "some products sell much more than others",
        bool(items_per_product.max() > items_per_product.min() * 5),
        f"min={items_per_product.min()} median={int(items_per_product.median())} "
        f"max={items_per_product.max()} lines per product",
    )

    lines_per_order = order_items.groupby("order_id").size()
    warn(
        "orders contain both single-item and multi-item orders",
        bool(lines_per_order.min() == 1 and lines_per_order.max() > 3),
        f"min={lines_per_order.min()} avg={lines_per_order.mean():.2f} max={lines_per_order.max()} items per order",
    )

    discount_counts = order_items["discount_percent"].value_counts()
    warn(
        "discounts are not the same on every line",
        discount_counts.size > 3,
        f"discount values used: {sorted(discount_counts.index.tolist())}",
    )

    price_by_category = products.groupby("category")["price"].mean().sort_values()
    warn(
        "prices differ a lot between categories",
        bool(price_by_category.max() > price_by_category.min() * 5),
        f"cheapest category avg={price_by_category.index[0]} ({price_by_category.iloc[0]:,.0f} PKR), "
        f"most expensive avg={price_by_category.index[-1]} ({price_by_category.iloc[-1]:,.0f} PKR)",
    )

    method_counts = payments["payment_method"].value_counts()
    warn(
        "payment methods have different frequencies",
        bool(method_counts.max() > method_counts.min()),
        ", ".join(f"{method}={count:,}" for method, count in method_counts.items()),
    )

    order_cities = orders["shipping_city"].value_counts()
    warn(
        "some cities receive more orders than others",
        order_cities.max() > order_cities.min(),
        f"most orders go to {order_cities.index[0]} ({order_cities.iloc[0]:,}), "
        f"fewest to {order_cities.index[-1]} ({order_cities.iloc[-1]:,})",
    )

    monthly_orders = (
        parse_dates(orders["order_date"]).dropna().dt.to_period("M").value_counts().sort_index()
    )
    warn(
        "monthly order volume varies (seasonality)",
        bool(monthly_orders.max() > monthly_orders.min() * 1.2),
        f"busiest month={monthly_orders.max():,} ({monthly_orders.idxmax()}), "
        f"quietest month={monthly_orders.min():,} ({monthly_orders.idxmin()})",
    )

    status_counts = orders["status"].value_counts(normalize=True)
    minority = status_counts[["Cancelled", "Returned", "Pending"]].sum()
    warn(
        "cancelled and returned orders are a minority",
        bool(minority < 0.35),
        f"Cancelled={status_counts['Cancelled']:.1%} "
        f"Returned={status_counts['Returned']:.1%} "
        f"Pending={status_counts['Pending']:.1%}",
    )

    unknown_cities = (set(customers["city"]) | set(orders["shipping_city"])) - VALID_CITIES
    warn(
        "every city used is a real Pakistani city",
        not unknown_cities,
        f"{customers['city'].nunique()} distinct cities"
        + (f", unknown: {unknown_cities}" if unknown_cities else ""),
    )


# ---------------------------------------------------------------------------
# 9. FINAL SUMMARY
# ---------------------------------------------------------------------------

def print_summary(data):
    print("\n" + "=" * 74)
    print("FINAL REPORT")
    print("=" * 74)
    print(f"{'File':<20}{'Rows':>10}{'Columns':>10}  {'Validation'}")

    for filename in EXPECTED_COLUMNS:
        frame = data[filename]
        problems = [
            name for section, name, passed, _, owner in results
            if not passed and section != "Realism" and owner == filename
        ]
        status = "PASSED" if not problems else f"FAILED ({len(problems)})"
        print(f"{filename:<20}{len(frame):>10,}{len(frame.columns):>10}  {status}")

    total_checks = len(results)
    failed = fail_count()
    passed = total_checks - failed

    print("-" * 74)
    print(f"Checks run   : {total_checks}")
    print(f"Passed       : {passed}")
    print(f"Failed       : {failed}")

    realism_warnings = [name for section, name, passed, _, _ in results
                        if section == "Realism" and not passed]
    if realism_warnings:
        print(f"Warnings     : {len(realism_warnings)} realism check(s) flagged")

    print("=" * 74)

    if failed == 0:
        print("RESULT: ALL VALIDATION CHECKS PASSED - the dataset is ready to use.")
    else:
        print("RESULT: VALIDATION FAILED - fix the problems listed above before analysing.")

    return failed


# ---------------------------------------------------------------------------
# 10. MAIN
# ---------------------------------------------------------------------------

def main():
    print("=" * 74)
    print("E-COMMERCE SALES ANALYSIS - DATASET VALIDATION")
    print("=" * 74)

    data = load_data()
    if data is None:
        print("\nCould not load every CSV file. Validation stopped.")
        return 1

    # Each stage is run inside its own guard, so one unexpected problem in a
    # step still lets the remaining steps run and the summary still prints.
    try:
        check_structure(data)
        parsed_dates = check_types_and_dates(data)
        check_business_rules(data, parsed_dates)
        check_relationships(data, parsed_dates)
        check_realism(data)
    except Exception as error:                          # noqa: BLE001
        check("Validator", "validation ran to completion", False, f"{type(error).__name__}: {error}")
        parsed_dates = None

    failed = print_summary(data)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
