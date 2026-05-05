import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DB_HOST, DB_NAME, DB_PORT, DB_USER, DEFAULT_CSV_PATH
from app.services.simulator import TransactionSimulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic single-customer transaction data for anomaly detection."
    )
    parser.add_argument("--months", type=int, default=4, help="Total months of data to generate, between 3 and 6.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output.")
    parser.add_argument(
        "--output",
        choices=["csv", "postgres", "both", "memory"],
        default="csv",
        help="Output destination for generated transactions.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    simulator = TransactionSimulator(months=args.months, seed=args.seed)
    transactions, summary = simulator.generate()
    persisted_summary = simulator.persist(transactions, summary, output=args.output)

    print(f"Generated {persisted_summary.total_transactions} transactions for account {persisted_summary.account_id}.")
    print(f"Baseline months: {persisted_summary.baseline_months}")
    print(f"Baseline transactions: {persisted_summary.baseline_transaction_count}")
    print(f"Anomalous month transactions: {persisted_summary.anomalous_month_transaction_count}")
    print(f"Output mode: {persisted_summary.output_mode}")

    if args.output in {"csv", "both"}:
        print(f"CSV path: {DEFAULT_CSV_PATH}")
    if args.output in {"postgres", "both"}:
        print(f"Postgres target: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


if __name__ == "__main__":
    main()
