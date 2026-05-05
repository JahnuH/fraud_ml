import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import DB_HOST, DB_NAME, DB_PORT, DB_USER, DEFAULT_CSV_PATH
from app.services.simulator import generate_simulation_batch, persist_simulation_batch


def str_to_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError("Expected a boolean value: true/false")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic transaction data for anomaly detection."
    )
    parser.add_argument("--months", type=int, default=4, help="Total months of data to generate, between 3 and 6.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output.")
    parser.add_argument("--customers", type=int, default=1, help="Number of synthetic customers to generate, between 1 and 50.")
    parser.add_argument("--inject-time-shift", type=str_to_bool, default=True, help="Whether to inject a time-shift anomaly in the anomalous month.")
    parser.add_argument("--inject-amount-spike", type=str_to_bool, default=False, help="Whether to inject a large transaction amount anomaly.")
    parser.add_argument("--inject-new-ip", type=str_to_bool, default=False, help="Whether to inject a new IP usage anomaly.")
    parser.add_argument(
        "--output",
        choices=["csv", "postgres", "both", "memory"],
        default="csv",
        help="Output destination for generated transactions.",
    )
    parser.add_argument(
        "--summary-json",
        action="store_true",
        help="Print a JSON summary for automation or UI integration.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    transactions, summary = generate_simulation_batch(
        months=args.months,
        seed=args.seed,
        customers=args.customers,
        inject_time_shift=args.inject_time_shift,
        inject_amount_spike=args.inject_amount_spike,
        inject_new_ip=args.inject_new_ip,
    )
    persist_simulation_batch(transactions, output=args.output)

    print(f"Generated {summary['total_transactions']} transactions for {summary['customers']} customer(s).")
    print(f"Baseline months: {summary['months'] - 1}")
    print(f"Baseline transactions: {summary['baseline_transactions']}")
    print(f"Anomalous month transactions: {summary['anomalous_transactions']}")
    print(f"Output mode: {args.output}")

    if args.output in {"csv", "both"}:
        print(f"CSV path: {DEFAULT_CSV_PATH}")
    if args.output in {"postgres", "both"}:
        print(f"Postgres target: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    if args.summary_json:
        print(json.dumps(summary))


if __name__ == "__main__":
    main()
