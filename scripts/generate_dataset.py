"""
generate_dataset.py
===================

Generates a realistic (fictional) e-commerce dataset for the
"E-Commerce Sales Analysis" portfolio project.

The data is fully reproducible: a fixed random seed is used, so
running this script again always produces exactly the same files.

Tables generated into ../data/ :

    customers.csv   1,500 rows
    products.csv      300 rows
    orders.csv      12,000 rows
    order_items.csv ~30,000 rows
    payments.csv    12,000 rows

IMPORTANT DESIGN DECISIONS
--------------------------
* No total amount column is stored anywhere. Revenue is meant to be
  calculated later as:
      quantity * unit_price * (1 - discount_percent / 100)
* Product cost is stored in products.csv so profit can be calculated
  later by joining order_items -> products.
* Money values are in PKR (Pakistani Rupees).
* The dataset is intentionally clean. Any missing-value / dirty-data
  practice will be done in later phases on purpose.

Usage:
    python scripts/generate_dataset.py
"""

import os

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------------------------

RANDOM_SEED = 20240615  # fixed seed -> reproducible dataset

NUM_CUSTOMERS = 1_500
NUM_PRODUCTS = 300
NUM_ORDERS = 12_000

# Average number of product lines per order (produces ~30,000 order items)
ITEMS_PER_ORDER_AVG = 2.5

# The company "went live" ~2 years before the end of the data window
ORDER_START = pd.Timestamp("2024-10-01")
ORDER_END = pd.Timestamp("2026-09-26")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")

rng = np.random.default_rng(RANDOM_SEED)


# ---------------------------------------------------------------------------
# 2. SMALL HELPER FUNCTIONS
# ---------------------------------------------------------------------------


def weighted_pick(choices, weights, size):
    """Pick `size` values from `choices` using relative `weights`."""
    probabilities = np.asarray(weights, dtype=float)
    probabilities = probabilities / probabilities.sum()
    return np.asarray(choices)[rng.choice(len(choices), size=size, p=probabilities)]


def clamp(values, low, high):
    """Restrict values to the [low, high] range."""
    return np.clip(values, low, high)


def round_price(value):
    """Round a price to a realistic looking value (e.g. 49999 instead of 49998.7)."""
    value = float(value)
    if value >= 50_000:
        step = 500
    elif value >= 10_000:
        step = 100
    elif value >= 1_000:
        step = 50
    else:
        step = 10
    return float(round(value / step) * step)


def make_unique(name, used, variants):
    """Return a unique product name, adding a variant if the name repeats."""
    candidate = name
    for _ in range(len(variants) + 1):
        if candidate not in used:
            used.add(candidate)
            return candidate
        for variant in variants:
            trial = f"{name} {variant}"
            if trial not in used:
                used.add(trial)
                return trial
    # Last resort so the function can never loop forever
    index = 2
    while f"{name} Edition {index}" in used:
        index += 1
    final = f"{name} Edition {index}"
    used.add(final)
    return final


# ---------------------------------------------------------------------------
# 3. REFERENCE DATA (names, cities, categories)
# ---------------------------------------------------------------------------

MALE_FIRST_NAMES = [
    "Ahmed", "Ali", "Hassan", "Usman", "Bilal", "Imran", "Junaid", "Kamran",
    "Salman", "Tariq", "Adnan", "Faizan", "Hamza", "Kashif", "Luqman", "Nadeem",
    "Rehan", "Saif", "Waleed", "Yasir", "Zeeshan", "Ahsan", "Asad", "Danial",
    "Ehtesham", "Faisal", "Hammad", "Ilyas", "Javed", "Kashif", "Moin", "Noman",
    "Owais", "Qasim", "Rizwan", "Shahid", "Tanveer", "Umair", "Yahya", "Zafar",
]

FEMALE_FIRST_NAMES = [
    "Ayesha", "Fatima", "Zainab", "Sara", "Maria", "Hina", "Kiran", "Nadia",
    "Sadia", "Rabia", "Sumaira", "Yasmin", "Amna", "Bushra", "Farah", "Gulnaz",
    "Humaira", "Iqra", "Javeria", "Kausar", "Laila", "Mehwish", "Nida", "Rania",
    "Saira", "Tehmina", "Uzma", "Wajiha", "Zoha", "Alia", "Maryam", "Nimra",
    "Sanam", "Sheeba", "Nazia", "Farzana", "Saba", "Mahnoor", "Hafsa", "Iqraa",
]

LAST_NAMES = [
    "Khan", "Ahmed", "Ali", "Malik", "Hussain", "Raza", "Sheikh", "Farooq",
    "Aslam", "Butt", "Chaudhry", "Qureshi", "Siddiqui", "Nadeem", "Iqbal",
    "Javed", "Akram", "Baloch", "Durrani", "Hashmi", "Sattar", "Yousaf",
    "Zafar", "Munir", "Rafiq", "Shafiq", "Usman", "Waris", "Zaman", "Kazmi",
    "Gilani", "Lodhi", "Mirza", "Nawaz", "Pervez", "Qayyum", "Rasheed", "Sabir",
    "Tariq", "Zubair", "Abbasi", "Bukhari", "Chishti", "Durrani",
]

# Pakistani cities with (roughly) realistic population weights
CITIES = [
    ("Karachi", 165), ("Lahore", 150), ("Islamabad", 85), ("Rawalpindi", 60),
    ("Faisalabad", 58), ("Gujranwala", 48), ("Multan", 45), ("Peshawar", 40),
    ("Quetta", 30), ("Sialkot", 25), ("Hyderabad", 25), ("Bahawalpur", 22),
    ("Sargodha", 20), ("Abbottabad", 18), ("Sukkur", 16), ("Sahiwal", 15),
    ("Mirpur Khas", 12), ("Rahim Yar Khan", 11), ("Mardan", 9), ("Gwadar", 8),
]
CITY_NAMES = [city for city, _ in CITIES]
CITY_WEIGHTS = [weight for _, weight in CITIES]

EMAIL_DOMAINS = [
    ("gmail.com", 45), ("yahoo.com", 18), ("outlook.com", 12),
    ("hotmail.com", 8), ("protonmail.com", 5), ("zoho.com", 4),
    ("mail.com", 3), ("icloud.com", 2),
]

# 10 categories x 4 subcategories = 40 subcategories
SUBCATEGORY_CATALOGUE = {
    "Electronics": {
        "Audio": (["Sony", "JBL", "Bose", "Samsung", "LG", "Philips", "Panasonic",
                   "Anker", "Sennheiser", "Beats"],
                  ["Wireless Earbuds", "Bluetooth Speaker", "Over-Ear Headphone",
                   "Soundbar", "Party Speaker", "Studio Monitor"],
                  (2_500, 85_000)),
        "Televisions": (["Samsung", "LG", "Sony", "TCL", "Hisense", "Sharp", "Toshiba", "Philips"],
                        ["Smart TV", "OLED TV", "QLED TV", "LED TV"],
                        (45_000, 400_000)),
        "Cameras": (["Canon", "Nikon", "Fujifilm", "GoPro", "Sigma", "Polaroid", "Tamron"],
                    ["DSLR Camera", "Mirrorless Camera", "Action Camera", "Instant Camera",
                     "Telephoto Lens", "Camera Tripod"],
                    (4_000, 450_000)),
        "Wearables": (["Apple", "Samsung", "Garmin", "Fitbit", "Amazfit", "Huawei", "Noise"],
                      ["Smart Watch", "Fitness Band", "Smart Ring", "Kids Smart Watch"],
                      (3_500, 95_000)),
    },
    "Computers": {
        "Laptops": (["Dell", "HP", "Lenovo", "Asus", "Acer", "Apple", "MSI", "Microsoft"],
                    ["Gaming Laptop", "Ultrabook", "Business Laptop", "Student Laptop",
                     "Convertible Laptop", "Workstation Laptop"],
                    (85_000, 320_000)),
        "Desktops": (["Dell", "HP", "Lenovo", "Asus", "Acer", "Apple", "MSI"],
                     ["Gaming PC", "Office PC", "All-in-One PC", "Mini PC", "Workstation PC"],
                     (55_000, 180_000)),
        "Monitors": (["Dell", "LG", "Samsung", "ASUS", "BenQ", "ViewSonic", "Acer"],
                     ["LED Monitor", "Gaming Monitor", "Ultrawide Monitor", "Curved Monitor",
                      "Portable Monitor"],
                     (18_000, 75_000)),
        "Accessories": (["Logitech", "Corsair", "Kingston", "Seagate", "Western Digital",
                         "Anker", "HyperX", "TP-Link"],
                        ["Mechanical Keyboard", "Wireless Mouse", "External SSD",
                         "USB Hub", "Webcam", "UPS Backup", "RAM Module", "Wi-Fi Adapter"],
                        (900, 28_000)),
    },
    "Mobile Accessories": {
        "Chargers": (["Anker", "Baseus", "Ugreen", "Samsung", "Apple", "Oppo", "Xiaomi"],
                     ["Fast Charger", "Wireless Charging Pad", "Charging Cable",
                      "Car Charger", "Power Bank Charger"],
                     (350, 6_500)),
        "Cases": (["Spigen", "UAG", "ESR", "Xiaomi", "Samsung", "Ringke"],
                 ["Silicone Case", "Clear Case", "Rugged Case", "Flip Cover",
                  "Wallet Case", "Camera Protection Case"],
                 (400, 4_500)),
        "Earbuds": (["Samsung", "Apple", "Sony", "JBL", "Realme", "Xiaomi", "Oppo"],
                    ["TWS Earbuds", "Neckband Earphones", "Gaming Earbuds",
                     "Sport Earbuds", "In-Ear Headphones"],
                    (800, 18_000)),
        "Power Banks": (["Anker", "Xiaomi", "Romoss", "Baseus", "New Age"],
                        ["Power Bank 10000mAh", "Power Bank 20000mAh",
                         "Power Bank 27000mAh", "Solar Power Bank", "Laptop Power Bank"],
                        (1_200, 12_000)),
    },
    "Home Appliances": {
        "Refrigerators": (["Samsung", "LG", "Haier", "Hisense", "Gree", "Dawlance", "Singer"],
                          ["Double Door Refrigerator", "Single Door Refrigerator",
                           "French Door Refrigerator", "Mini Refrigerator"],
                          (55_000, 320_000)),
        "Washing Machines": (["Samsung", "LG", "Haier", "Whirlpool", "Dawlance", "Singer", "Toshiba"],
                             ["Front Load Washer", "Top Load Washer", "Twin Tub Washer",
                              "Washer Dryer Combo"],
                             (32_000, 180_000)),
        "Air Conditioners": (["Gree", "Haier", "Orient", "Samsung", "Daikin", "Super General", "Toshiba"],
                             ["Split AC", "Window AC", "Inverter AC", "Portable AC",
                              "Cassette AC"],
                             (65_000, 380_000)),
        "Kitchen Appliances": (["Philips", "Braun", "Kenwood", "Prestige", "Ramtons",
                                "Singer", "Inalsa", "Moulinex"],
                               ["Microwave Oven", "Air Fryer", "Blender", "Toaster",
                                "Electric Kettle", "Rice Cooker", "Sandwich Maker",
                                "Food Processor"],
                               (1_800, 65_000)),
    },
    "Fashion": {
        "Men's Clothing": (["Levi's", "Tommy Hilfiger", "Calvin Klein", "Nike", "Adidas",
                            "Gul Ahmed", "Khaadi", "Sapphire"],
                           ["Cotton T-Shirt", "Formal Shirt", "Denim Jeans", "Kurta Shirt",
                            "Hoodie", "Chino Trousers", "Jacket", "Sweater"],
                           (1_200, 18_000)),
        "Women's Clothing": (["Khaadi", "Gul Ahmed", "Sana Safinaz", "Sapphire", "H&M", "Zara", "Noor"],
                             ["Lawn Suit", "Cotton Kurta", "Maxi Dress", "Shawl",
                              "Trousers", "Ready-to-Wear Dress", "Winter Jacket"],
                             (1_500, 22_000)),
        "Footwear": (["Nike", "Adidas", "Puma", "Bata", "Servis", "Skechers", "Jordans"],
                     ["Running Shoes", "Sneakers", "Formal Shoes", "Sandals",
                      "Sports Shoes", "Leather Boots", "Loafers"],
                     (1_800, 25_000)),
        "Accessories": (["Nike", "Adidas", "Hidesign", "Bags More", "Da Milano", "Fossil", "Timex"],
                        ["Leather Belt", "Wallet", "Sunglasses", "Watch", "Backpack",
                         "Handbag", "Tie"],
                        (600, 9_000)),
    },
    "Beauty": {
        "Skincare": (["Neutrogena", "Cetaphil", "Garnier", "The Ordinary", "L'Oreal",
                      "Himalaya", "Clean & Clear", "Bio Aqua"],
                     ["Face Wash", "Moisturizer", "Sunscreen", "Face Serum",
                      "Cleansing Oil", "Night Cream", "Face Mask"],
                     (350, 9_000)),
        "Haircare": (["Tresemme", "Sunsilk", "L'Oreal", "Gatsby", "Head & Shoulders",
                      "Wella", "Saeed Ghani"],
                     ["Shampoo", "Conditioner", "Hair Oil", "Hair Serum",
                      "Hair Mask", "Hair Dryer", "Grooming Kit"],
                     (400, 7_500)),
        "Makeup": (["Maybelline", "L'Oreal", "MAC", "Huda Beauty", "Urban Decay",
                    "Fenty", "Swiss Beauty", "Juvia's Place"],
                   ["Lipstick", "Foundation", "Mascara", "Eyeshadow Palette",
                    "Concealer", "Blush", "Makeup Brush Set", "Compact Powder"],
                   (500, 12_000)),
        "Fragrances": (["L'Oreal", "Al Haramain", "Javerian", "Sapphire", "Armaf",
                        "Sabah", "Gul Ahmed"],
                       ["Eau de Parfum", "Eau de Toilette", "Attar", "Body Spray",
                        "Perfume Gift Set", "Musk Spray"],
                       (800, 11_000)),
    },
    "Sports": {
        "Fitness Equipment": (["Decathlon", "Musclemania", "PowerGym", "FitZone",
                               "Imported Fitness", "CoreFit"],
                              ["Adjustable Dumbbell", "Yoga Mat", "Skipping Rope",
                               "Resistance Band", "Weight Bench", "Kettlebell",
                               "Treadmill", "Pull-up Bar"],
                              (1_500, 90_000)),
        "Team Sports": (["Adidas", "Puma", "Molten", "Nivia", "SG", "Cosco", "Franklin",
                         "Yonex"],
                        ["Football", "Basketball", "Volleyball", "Cricket Bat",
                         "Cricket Ball", "Badminton Racket", "Table Tennis Bat"],
                        (800, 35_000)),
        "Outdoor": (["Decathlon", "Wild Country", "Coleman", "Naturehike", "Quechua", "Lowe Alpine"],
                    ["Camping Tent", "Sleeping Bag", "Trekking Backpack", "Water Bottle",
                     "Camp Stove", "Trekking Poles", "Hammock"],
                    (1_200, 40_000)),
        "Sportswear": (["Nike", "Adidas", "Puma", "Under Armour", "Reebok", "Kappa", "Hummel"],
                       ["Sports T-Shirt", "Track Pants", "Training Shorts", "Sports Jacket",
                        "Compression Shirt", "Jersey"],
                       (700, 8_000)),
    },
    "Books": {
        "Fiction": (["Penguin", "HarperCollins", "Hachette", "Random House", "Rupa", "Ilm Kitab"],
                    ["The Silent River", "Dawn of Echoes", "Sands of Time", "The Last Garden",
                     "Whispers in the Valley", "Guardians of Dawn", "The Broken Promise",
                     "Shadows of Autumn", "Beyond the Bridge", "Forgotten Kingdom",
                     "Rising from the Storm", "The Silver Path", "Echoes of Tomorrow",
                     "Legacy of Fire", "The Hidden Road"],
                    (300, 3_500)),
        "Non-Fiction": (["Penguin", "HarperCollins", "Juggernaut", "Rupa", "Ilm Kitab", "WordPress"],
                        ["Habits of High Achievers", "A Practical Guide to Personal Finance",
                         "The Discipline of Focus", "Understanding Modern Economics",
                         "Mindset and Motivation", "The Art of Clear Writing",
                         "Healthy Living Blueprint", "Mastering Time Management"],
                        (350, 3_200)),
        "Academic": (["Ilm Kitab", "National Book Foundation", "Cambridge Pakistan", "Oxford Pakistan",
                      "Ilm Kitab", "Uswa", "Danish"],
                     ["Physics Grade 11", "Chemistry Part 1", "Calculus Made Easy",
                      "Organic Chemistry Essentials", "Statistics for Engineers",
                      "Computer Science Algorithms", "Economics Grade 12",
                      "Biology Grade 10", "English Grammar Handbook",
                      "Discrete Mathematics"],
                     (400, 4_500)),
        "Children": (["Ilm Kitab", "Uswa", "National Book Foundation", "Little Book House", "Kids Zone"],
                     ["The Adventures of Bilal", "Magic Tree Readers", "Bedtime Stories Collection",
                      "Fairy Tales for Boys", "Learn to Read: Level 1",
                      "Illustrated Quran Stories", "Animal Friends",
                      "Science Facts for Kids", "My First Activity Book"],
                     (250, 2_500)),
    },
    "Grocery": {
        "Tea & Coffee": (["Tapal", "National", "Lipton", "Nescafe", "Maxwell House",
                          "Brooke Bond", "Kashmiri Chai", "Shezan"],
                         ["Tea 250g", "Tea 500g", "Instant Coffee Jar", "Coffee Beans 500g",
                          "Green Tea", "Coffee Powder 200g", "Chocolate Drink Powder"],
                         (180, 4_500)),
        "Snacks": (["Bisconni", "EBM", "Super Crisp", "Peanuts", "Continental", "Takeo", "Rupali"],
                   ["Biscuit Pack", "Chips Pack", "Wafer", "Cookies", "Chocolate Bar",
                    "Peanut Pack", "Chocolatto"],
                   (120, 2_000)),
        "Dairy": (["Nestle Milkpak", "FrieslandCampina", "Olper's", "Amul", "Meadow Gold", "GoodMilk"],
                  ["Milk 1L", "Butter", "Cheese Block", "Yogurt", "Cream", "Lassi", "Cheese Slice"],
                  (180, 3_500)),
        "Staples": (["Unilever", "Dalda", "Teco", "National", "Sunfeast", "Shan", "Dalda",
                     "National Foods"],
                    ["Cooking Oil 3L", "Basmati Rice 5kg", "Wheat Flour 10kg", "Sugar 1kg",
                     "Salt 800g", "Red Chilli Powder", "Turmeric Powder", "Ghee 1kg"],
                    (150, 5_500)),
    },
    "Home & Kitchen": {
        "Cookware": (["Tefal", "Prestige", "Rachael Ray", "Pigeon", "Hawkins", "Borosil", "Pigeon"],
                     ["Non-Stick Fry Pan", "Pressure Cooker", "Cookware Set", "Kadai",
                      "Grill Pan", "Casserole Set", "Milk Pan"],
                     (800, 25_000)),
        "Furniture": (["Interwood", "Galaxy", "Idea", "Eureka", "Metro", "Felix", "Sapphire"],
                      ["Sofa Set", "Bed", "Dining Table", "Office Chair", "Wardrobe",
                       "Coffee Table", "Bookshelf"],
                      (4_000, 85_000)),
        "Bedding": (["Sapphire", "Dalsy", "Clovia", "SleepWell", "Cotton House", "Crown"],
                    ["Comforter Set", "Bed Sheet Set", "Pillow Pack", "Mattress",
                     "Blanket", "Duvet Cover"],
                    (900, 12_000)),
        "Decor": (["IKEA", "Home Decor Centre", "Artisan", "WoodNest", "Pottery Studio",
                   "Chandelier House", "Home Living"],
                  ["Wall Art", "Table Lamp", "Flower Vase", "Area Rug", "Cushion Covers",
                   "Shelf Decor", "Photo Frame"],
                  (600, 18_000)),
    },
}

# Category -> subcategory -> (brands, product types, (min price, max price))

# How often each category appears in a *product line* of an order
# (not the same as revenue: revenue is driven by price, not by frequency)
CATEGORY_LINE_FREQUENCY = {
    "Electronics": 1.25, "Computers": 0.80, "Mobile Accessories": 1.60,
    "Home Appliances": 0.55, "Fashion": 1.35, "Beauty": 1.30,
    "Sports": 0.90, "Books": 1.15, "Grocery": 1.45, "Home & Kitchen": 0.85,
}

# Average quantity per line - groceries and books are bought in bigger amounts
CATEGORY_QUANTITY_MEAN = {
    "Electronics": 1.0, "Computers": 1.0, "Mobile Accessories": 1.6,
    "Home Appliances": 1.0, "Fashion": 1.5, "Beauty": 1.6,
    "Sports": 1.4, "Books": 1.8, "Grocery": 2.2, "Home & Kitchen": 1.4,
}

ORDER_STATUSES = ["Completed", "Pending", "Cancelled", "Returned"]
ORDER_STATUS_WEIGHTS = [0.775, 0.085, 0.065, 0.075]

PAYMENT_METHODS = ["Cash on Delivery", "Credit Card", "Debit Card",
                   "Bank Transfer", "JazzCash", "EasyPaisa"]
PAYMENT_METHOD_WEIGHTS = [0.34, 0.17, 0.10, 0.08, 0.19, 0.12]

# Bigger cities use cards more often than smaller ones
METRO_CITIES = {"Karachi", "Lahore", "Islamabad", "Rawalpindi"}

BOOK_FORMATS = ["Paperback", "Hardcover", "E-Book", "Deluxe Edition", "Illustrated"]


# ---------------------------------------------------------------------------
# 4. CUSTOMERS  (1,500 rows)
# ---------------------------------------------------------------------------

def generate_customers():
    """Create the customers table."""
    print("Generating customers ...")

    customer_ids = [f"CUST-{i:05d}" for i in range(1, NUM_CUSTOMERS + 1)]

    # Gender is decided first, then a first name that matches it is picked
    last_names = weighted_pick(LAST_NAMES, [1] * len(LAST_NAMES), NUM_CUSTOMERS)
    is_female = rng.random(NUM_CUSTOMERS) < 0.49
    first_names = np.empty(NUM_CUSTOMERS, dtype=object)
    female_positions = np.where(is_female)[0]
    male_positions = np.where(~is_female)[0]
    first_names[female_positions] = weighted_pick(
        FEMALE_FIRST_NAMES, [1] * len(FEMALE_FIRST_NAMES), len(female_positions)
    )
    first_names[male_positions] = weighted_pick(
        MALE_FIRST_NAMES, [1] * len(MALE_FIRST_NAMES), len(male_positions)
    )
    genders = np.where(is_female, "Female", "Male")

    full_names = [f"{first} {last}" for first, last in zip(first_names, last_names)]

    # Emails are built from the name + the customer id so they are always unique
    domains = weighted_pick(
        [domain for domain, _ in EMAIL_DOMAINS],
        [weight for _, weight in EMAIL_DOMAINS],
        NUM_CUSTOMERS,
    )
    emails = []
    for customer_id, first, last, domain in zip(customer_ids, first_names, last_names, domains):
        local_part = f"{first.lower()}.{last.lower()}.{customer_id.lower().replace('-', '')}"
        emails.append(f"{local_part}@{domain}")

    # Ages are right-skewed towards young adults, but include older customers
    ages = clamp(np.round(rng.normal(33, 10, NUM_CUSTOMERS)), 18, 72).astype(int)

    cities = weighted_pick(CITY_NAMES, CITY_WEIGHTS, NUM_CUSTOMERS)

    customers = pd.DataFrame({
        "customer_id": customer_ids,
        "name": full_names,
        "email": emails,
        "gender": genders,
        "age": ages,
        "city": cities,
    })

    return customers


# ---------------------------------------------------------------------------
# 5. PRODUCTS  (300 rows)
# ---------------------------------------------------------------------------

def generate_products():
    """Create the products table (price > cost for every product)."""
    print("Generating products ...")

    # 7 products per subcategory = 280, then 20 extra spread around.
    # The key is (category, subcategory) because two different categories
    # both contain a subcategory called "Accessories".
    subcategory_keys = [
        (category, subcategory)
        for category, subcategories in SUBCATEGORY_CATALOGUE.items()
        for subcategory in subcategories
    ]
    products_per_subcategory = {key: 7 for key in subcategory_keys}
    for key in rng.choice(len(subcategory_keys), size=20, replace=False):
        products_per_subcategory[subcategory_keys[key]] += 1

    product_ids = []
    product_names = []
    product_categories = []
    product_subcategories = []
    product_brands = []
    prices = []
    costs = []

    used_names = set()

    for category, category_subcategories in SUBCATEGORY_CATALOGUE.items():
        for subcategory, (brand_list, type_list, (low_price, high_price)) in category_subcategories.items():
            count = products_per_subcategory[(category, subcategory)]
            # Pick brands with replacement but keep the first brands slightly favoured
            brand_weights = np.linspace(1.4, 0.6, len(brand_list))
            picked_brands = weighted_pick(brand_list, brand_weights, count)
            picked_types = weighted_pick(type_list, [1] * len(type_list), count)

            for brand, product_type in zip(picked_brands, picked_types):
                product_ids.append(f"PROD-{len(product_ids) + 1:04d}")
                product_categories.append(category)
                product_subcategories.append(subcategory)
                product_brands.append(brand)

                base_name = f"{brand} {product_type}"
                if category == "Books":
                    base_name = f"{product_type}"
                product_names.append(make_unique(base_name, used_names, BOOK_FORMATS))

                # Log-uniform pricing: most products are affordable, a few are expensive
                price = float(np.exp(rng.uniform(np.log(low_price), np.log(high_price))))
                price = round_price(price)

                # Margin varies between 12% and 55% - no two categories are alike
                margin = clamp(rng.normal(0.32, 0.11), 0.12, 0.55)
                cost = round_price(price * (1 - margin))
                cost = min(cost, price - 10)  # guarantee cost < price

                prices.append(price)
                costs.append(max(cost, 10.0))

    stock_quantities = []
    for _ in range(len(product_ids)):
        # 5% of products are out of stock, otherwise a small or a large quantity
        if rng.random() < 0.05:
            stock_quantities.append(0)
        else:
            stock_quantities.append(int(np.exp(rng.uniform(np.log(5), np.log(600)))))

    products = pd.DataFrame({
        "product_id": product_ids,
        "product_name": product_names,
        "category": product_categories,
        "subcategory": product_subcategories,
        "brand": product_brands,
        "price": prices,
        "cost": costs,
        "stock_quantity": stock_quantities,
    })

    return products


# ---------------------------------------------------------------------------
# 6. ORDERS  (12,000 rows)
# ---------------------------------------------------------------------------

def generate_orders(customers, products):
    """Create the orders table with realistic customers, dates and statuses."""
    print("Generating orders ...")

    # --- 6.1 which customer places which order -----------------------------
    # A lognormal weight creates "whale" customers (many orders) and
    # one-time buyers, instead of every customer ordering the same amount.
    raw_loyalty = rng.lognormal(mean=0.0, sigma=1.0, size=NUM_CUSTOMERS)
    loyalty = clamp(raw_loyalty, 0.15, 3.0)
    orders_per_customer = rng.multinomial(NUM_ORDERS, loyalty / loyalty.sum())

    customer_index = np.repeat(np.arange(NUM_CUSTOMERS), orders_per_customer)

    # --- 6.2 order dates --------------------------------------------------
    # The last month is cut off at ORDER_END so the whole dataset stays
    # inside the intended two-year window.
    month_index = pd.date_range(ORDER_START, ORDER_END, freq="MS")
    month_starts = month_index.to_numpy()
    month_lengths = np.array(
        [
            min(
                (month + pd.offsets.MonthEnd(1)).day,
                (ORDER_END - month).days + 1,   # last month is partial
            )
            for month in month_index
        ]
    )

    # Seasonality for a Pakistani e-commerce shop:
    # low in Jan/Feb, high around Eid (May, Aug-Oct) and in November (11.11 sale)
    seasonal = [0.88, 0.92, 1.00, 0.95, 1.10, 1.02, 1.05, 1.12,
               1.08, 1.10, 1.30, 1.15]
    month_weights = [
        seasonal[i % 12] * (1 + 0.18 * (i // 12))  # gentle yearly growth
        for i in range(len(month_starts))
    ]

    picked_months = rng.choice(
        len(month_starts), size=NUM_ORDERS, p=np.array(month_weights) / sum(month_weights)
    )
    picked_days = rng.integers(0, month_lengths[picked_months], NUM_ORDERS)
    order_dates = month_starts[picked_months] + pd.to_timedelta(picked_days, unit="D").to_numpy()

    # In Pakistan Sunday is the weekend, so fewer orders are placed on Sundays
    sunday_orders = pd.DatetimeIndex(order_dates).dayofweek == 6
    resample = sunday_orders & (rng.random(NUM_ORDERS) > 0.55)
    new_days = rng.integers(0, month_lengths[picked_months[resample]], resample.sum())
    order_dates[resample] = (
        month_starts[picked_months[resample]] + pd.to_timedelta(new_days, unit="D").to_numpy()
    )

    # --- 6.3 order status -------------------------------------------------
    statuses = weighted_pick(ORDER_STATUSES, ORDER_STATUS_WEIGHTS, NUM_ORDERS)

    # Orders placed in the last few weeks are more likely to still be "Pending"
    recent = order_dates >= (ORDER_END - pd.Timedelta(days=25))
    become_pending = recent & (rng.random(NUM_ORDERS) < 0.35)
    statuses[become_pending] = "Pending"

    # --- 6.4 shipping city ------------------------------------------------
    # 82% of orders ship to the customer's own city, the rest go elsewhere
    # (metro cities receive more incoming orders than small towns).
    home_city = customers["city"].to_numpy()[customer_index]
    shipping_city = home_city.copy()
    ship_elsewhere = rng.random(NUM_ORDERS) > 0.82

    alternative = weighted_pick(CITY_NAMES, CITY_WEIGHTS, NUM_ORDERS)
    # never "ship elsewhere" to the customer's own city
    clash = alternative == home_city
    alternative[clash] = weighted_pick(
        [city for city in CITY_NAMES if city != "Karachi"],
        CITY_WEIGHTS[:-1],
        clash.sum(),
    )
    shipping_city[ship_elsewhere] = alternative[ship_elsewhere]

    # --- 6.5 build the table, sorted by date ------------------------------
    orders = pd.DataFrame({
        "order_id": [f"ORD-{i + 1:06d}" for i in range(NUM_ORDERS)],
        "customer_id": customers["customer_id"].to_numpy()[customer_index],
        "order_date": order_dates,
        "status": statuses,
        "shipping_city": shipping_city,
    })
    orders = orders.sort_values("order_date").reset_index(drop=True)
    orders["order_id"] = [f"ORD-{i + 1:06d}" for i in range(NUM_ORDERS)]
    orders["order_date"] = orders["order_date"].dt.strftime("%Y-%m-%d")

    # Signup dates are added here because they must be older than the
    # customer's first order (see add_signup_dates).
    add_signup_dates(orders, customers)

    return orders


def add_signup_dates(orders, customers):
    """Add a realistic signup_date to every customer (always before their first order)."""
    print("Adding customer signup dates ...")

    # Align the first-order lookup with the full customer list
    first_order = orders.groupby("customer_id")["order_date"].min()
    first_order = first_order.reindex(customers["customer_id"]).to_numpy()
    first_order_dates = pd.to_datetime(pd.Series(first_order)).fillna(pd.NaT)

    # Customers sign up between 1 and ~730 days before their first order
    gap_days = pd.Series(rng.integers(1, 731, NUM_CUSTOMERS), index=first_order_dates.index)
    signup = first_order_dates - pd.to_timedelta(gap_days, unit="D")

    # A few customers sign up but never order - give them a date inside the
    # window in which the shop was already running
    never_ordered = first_order_dates.isna()
    random_offsets = rng.integers(0, 690, never_ordered.sum())
    signup[never_ordered] = (
        ORDER_START - pd.to_timedelta(random_offsets, unit="D")
    ).values

    # Never go earlier than the company founding date (2022-01-01)
    signup = signup.clip(lower=pd.Timestamp("2022-01-01"))

    # Safety net: a signup date must always be before the first order
    too_late = signup >= first_order_dates
    signup[too_late] = first_order_dates[too_late] - pd.Timedelta(days=1)

    customers["signup_date"] = signup.dt.strftime("%Y-%m-%d").to_numpy()


# ---------------------------------------------------------------------------
# 7. ORDER_ITEMS  (~30,000 rows)
# ---------------------------------------------------------------------------

def generate_order_items(orders, products):
    """Create the order_items table: which products, how many, at what price."""
    print("Generating order items ...")

    n_orders = len(orders)
    n_products = len(products)

    # --- 7.1 how many product lines does an order have? -------------------
    # Many orders have 1 item, some have 2-3, a few have 5 or more.
    line_counts = weighted_pick(
        [1, 2, 3, 4, 5, 6],
        [0.34, 0.25, 0.17, 0.11, 0.075, 0.055],
        n_orders,
    )
    total_items = int(line_counts.sum())

    # --- 7.2 which products are popular? ---------------------------------
    # Every product gets a demand weight, so a few products are best sellers
    # while many others are only bought occasionally.
    product_demand = clamp(rng.lognormal(mean=0.0, sigma=0.9, size=n_products), 0.15, 8.0)
    category_frequency = products["category"].map(CATEGORY_LINE_FREQUENCY).to_numpy()
    line_probability = product_demand * category_frequency
    line_probability = line_probability / line_probability.sum()

    # One product line per (order, product) - no duplicate products in an order
    chosen = rng.choice(n_products, size=total_items, p=line_probability)
    order_index = np.repeat(np.arange(n_orders), line_counts)
    starts = np.concatenate([[0], np.cumsum(line_counts)[:-1]])

    for order_no in range(n_orders):
        start = starts[order_no]
        end = start + line_counts[order_no]
        block = chosen[start:end]

        seen = set()
        duplicates = []
        for position, product in enumerate(block):
            if product in seen:
                duplicates.append(position)
            else:
                seen.add(product)

        # Re-pick duplicated products until every product in the order is unique
        while duplicates:
            replacements = rng.choice(n_products, size=len(duplicates), p=line_probability)
            still_duplicated = []
            for position, replacement in zip(duplicates, replacements):
                if replacement in seen:
                    still_duplicated.append(position)
                else:
                    block[position] = replacement
                    seen.add(replacement)
            duplicates = still_duplicated

        chosen[start:end] = block

    # --- 7.3 quantity -----------------------------------------------------
    product_category = products["category"].to_numpy()[chosen]
    category_mean = np.array([CATEGORY_QUANTITY_MEAN[c] for c in product_category])
    quantity = clamp(np.round(rng.normal(category_mean, 0.9)), 1, 8).astype(int)

    # --- 7.4 unit price ---------------------------------------------------
    # The selling price is the catalogue price with a small fluctuation,
    # plus a small bulk discount when 3 or more units are bought.
    catalogue_price = products["price"].to_numpy()[chosen]
    fluctuation = rng.normal(0, 0.015, total_items)
    bulk_discount = np.where(quantity >= 3, 0.02, 0.0)
    unit_price = catalogue_price * (1 + fluctuation - bulk_discount)
    unit_price = np.round(clamp(unit_price, catalogue_price * 0.70, catalogue_price * 1.15), 2)

    # --- 7.5 discount -----------------------------------------------------
    # Loyal customers (many orders) receive a discount slightly more often.
    orders_per_customer = orders["customer_id"].value_counts()
    loyalty_rank = (
        (orders_per_customer.reindex(orders["customer_id"]).to_numpy() - 1)
        / (orders_per_customer.max() - 1)
    )
    discount_probability = clamp(0.62 - 0.30 * loyalty_rank, 0.20, 0.75)
    gets_discount = rng.random(total_items) < discount_probability[order_index]

    discount_values = weighted_pick([5, 10, 15, 20, 25, 30], [34, 26, 18, 12, 6, 4], total_items)
    discount_percent = np.where(gets_discount, discount_values, 0).astype(int)

    order_items = pd.DataFrame({
        "order_item_id": [f"ITEM-{i + 1:06d}" for i in range(total_items)],
        "order_id": orders["order_id"].to_numpy()[order_index],
        "product_id": products["product_id"].to_numpy()[chosen],
        "quantity": quantity,
        "unit_price": unit_price,
        "discount_percent": discount_percent,
    })

    return order_items


# ---------------------------------------------------------------------------
# 8. PAYMENTS  (12,000 rows - exactly one per order)
# ---------------------------------------------------------------------------

def generate_payments(orders):
    """Create the payments table with one, and only one, payment per order."""
    print("Generating payments ...")

    n_orders = len(orders)
    order_status = orders["status"].to_numpy()
    shipping_city = orders["shipping_city"].to_numpy()
    order_date = pd.to_datetime(orders["order_date"])

    # --- 8.1 payment method ----------------------------------------------
    # Cash on Delivery still dominates, but large cities use cards more often.
    methods = weighted_pick(PAYMENT_METHODS, PAYMENT_METHOD_WEIGHTS, n_orders)
    is_metro = np.isin(shipping_city, list(METRO_CITIES))
    metro_cities = is_metro & (rng.random(n_orders) < 0.35)
    metro_method = weighted_pick(["Credit Card", "Debit Card"], [0.65, 0.35], metro_cities.sum())
    methods[metro_cities] = metro_method

    # --- 8.2 payment status ----------------------------------------------
    # The payment status follows the order status (this is what a real
    # e-commerce database looks like).
    payment_status = np.empty(n_orders, dtype=object)
    payment_status[order_status == "Completed"] = weighted_pick(
        ["Paid", "Refunded"], [0.93, 0.07], (order_status == "Completed").sum()
    )
    payment_status[order_status == "Pending"] = weighted_pick(
        ["Pending", "Paid"], [0.85, 0.15], (order_status == "Pending").sum()
    )
    payment_status[order_status == "Cancelled"] = weighted_pick(
        ["Failed", "Refunded"], [0.75, 0.25], (order_status == "Cancelled").sum()
    )
    payment_status[order_status == "Returned"] = weighted_pick(
        ["Refunded", "Paid"], [0.90, 0.10], (order_status == "Returned").sum()
    )

    # --- 8.3 payment date -------------------------------------------------
    # Cash and bank transfers settle slower than online card payments.
    slow_methods = np.isin(methods, ["Cash on Delivery", "Bank Transfer"])
    lag = np.where(
        slow_methods,
        rng.integers(1, 7, n_orders),
        rng.integers(0, 3, n_orders),
    )
    payment_date = order_date + pd.to_timedelta(lag, unit="D")
    payment_date = payment_date.clip(upper=ORDER_END)  # never in the future

    payments = pd.DataFrame({
        "payment_id": [f"PAY-{i + 1:06d}" for i in range(n_orders)],
        "order_id": orders["order_id"].to_numpy(),
        "payment_method": methods,
        "payment_status": payment_status,
        "payment_date": payment_date.dt.strftime("%Y-%m-%d"),
    })

    return payments


# ---------------------------------------------------------------------------
# 9. WRITE THE CSV FILES
# ---------------------------------------------------------------------------

def save_csv(dataframe, filename):
    """Write one dataframe to the data folder and report its size."""
    path = os.path.join(DATA_DIR, filename)
    dataframe.to_csv(path, index=False)
    print(f"  saved {filename:<17} rows={len(dataframe):>6}  columns={len(dataframe.columns)}")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print("=" * 70)
    print("E-COMMERCE SALES ANALYSIS - DATASET GENERATION")
    print(f"Random seed: {RANDOM_SEED}")
    print("=" * 70)

    customers = generate_customers()
    products = generate_products()
    orders = generate_orders(customers, products)
    order_items = generate_order_items(orders, products)
    payments = generate_payments(orders)

    print("\nWriting CSV files to data/ ...")
    save_csv(customers, "customers.csv")
    save_csv(products, "products.csv")
    save_csv(orders, "orders.csv")
    save_csv(order_items, "order_items.csv")
    save_csv(payments, "payments.csv")

    # A short summary so the shape of the data is visible right away
    print("\nQuick summary")
    print("-" * 70)
    print(f"  date range            : {orders['order_date'].min()} -> {orders['order_date'].max()}")
    print(f"  cities                : {customers['city'].nunique()}")
    print(f"  categories            : {products['category'].nunique()}")
    print(f"  subcategories         : {products['subcategory'].nunique()}")
    print(f"  completed orders      : {(orders['status'] == 'Completed').sum()} "
          f"({(orders['status'] == 'Completed').mean():.1%})")
    print(f"  lines per order (avg) : {len(order_items) / len(orders):.2f}")
    print(f"  lines with discount   : {(order_items['discount_percent'] > 0).mean():.1%}")

    top_customers = orders["customer_id"].value_counts()
    print(f"  orders per customer   : min={top_customers.min()} "
          f"median={int(top_customers.median())} max={top_customers.max()}")

    top_products = order_items["product_id"].value_counts()
    print(f"  lines per product     : min={top_products.min()} "
          f"median={int(top_products.median())} max={top_products.max()}")

    print("\nDone. Next step:  python scripts/validate_dataset.py")


if __name__ == "__main__":
    main()
