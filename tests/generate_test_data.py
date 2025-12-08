#!/usr/bin/env python3
"""Generate test data from seed file."""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4


SEED_FILE = Path(__file__).parent / "fixtures" / "test_data_seed.json"
OUTPUT_FILE = Path(__file__).parent / "fixtures" / "test_data.json"


def load_seed() -> dict:
    """Load seed data from JSON file."""
    with open(SEED_FILE) as f:
        return json.load(f)


def generate_transaction_id() -> str:
    """Generate a transaction ID similar to Monarch's format."""
    return str(uuid4().int)[:18]


def generate_transaction(
    date: datetime,
    account: dict,
    merchant: dict,
    category: dict,
    amount_range: list[int],
) -> dict:
    """Generate a single transaction from seed data."""
    amount_min, amount_max = amount_range
    if amount_min == amount_max:
        amount = float(amount_min)
    else:
        amount = round(random.uniform(amount_min, amount_max), 2)

    return {
        "id": generate_transaction_id(),
        "amount": amount,
        "pending": False,
        "date": date.strftime("%Y-%m-%d"),
        "hideFromReports": False,
        "needsReview": random.random() < 0.05,
        "plaidName": f"{merchant['name'].upper()} #{random.randint(1000, 9999)}",
        "notes": "",
        "isRecurring": merchant["name"] in ("Netflix", "Spotify", "Fairview Bank Mortgage", "AutoFinance Co"),
        "reviewStatus": "reviewed",
        "isSplitTransaction": False,
        "account": {
            "id": account["id"],
            "displayName": account["displayName"],
        },
        "merchant": {
            "id": f"merch_{merchant['name'].lower().replace(' ', '_')}",
            "name": merchant["name"],
            "transactionsCount": random.randint(5, 100),
        },
        "category": {
            "id": category["id"],
            "name": category["name"],
        },
        "tags": [],
    }


def generate_test_data(output_path: Path = None) -> dict:
    """Generate test database from seed file."""
    if output_path is None:
        output_path = OUTPUT_FILE

    seed = load_seed()
    categories_by_name = {c["name"]: c for c in seed["categories"]}

    # Remove existing file if present
    if output_path.exists():
        output_path.unlink()

    # Use TinyDB to create properly formatted data
    from tinydb import TinyDB

    db = TinyDB(output_path)

    # Insert categories
    categories_table = db.table("categories")
    for category in seed["categories"]:
        categories_table.insert(category)

    # Insert accounts (without merchants - that's seed-only structure)
    accounts_table = db.table("accounts")
    for account in seed["accounts"]:
        account_data = {k: v for k, v in account.items() if k != "merchants"}
        accounts_table.insert(account_data)

    # Generate transactions spread over 12 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    transactions_table = db.table("transactions")
    total_txn_count = 0

    for account in seed["accounts"]:
        for merchant in account.get("merchants", []):
            for txn_spec in merchant.get("transactions", []):
                count = txn_spec["count"]
                amount_range = txn_spec["amount_range"]
                category_name = merchant["categories"][0]
                category = categories_by_name[category_name]

                for _ in range(count):
                    days_offset = random.randint(0, 365)
                    txn_date = start_date + timedelta(days=days_offset)
                    txn = generate_transaction(
                        txn_date, account, merchant, category, amount_range
                    )
                    transactions_table.insert(txn)
                    total_txn_count += 1

    db.close()

    print(f"Generated {total_txn_count} transactions across {len(seed['accounts'])} accounts")
    print(f"Data written to: {output_path}")

    return {"transactions": total_txn_count, "accounts": len(seed["accounts"]), "categories": len(seed["categories"])}


if __name__ == "__main__":
    generate_test_data()
