import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.feature_engineering import BehavioralFeatureEngineer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract behavioral features from baseline raw transactions and persist behavioral profiles."
    )
    parser.add_argument("--account-id", default=None, help="Optional account_id filter.")
    parser.add_argument(
        "--print-model-frame",
        action="store_true",
        help="Print the model-ready feature frame after extraction.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engineer = BehavioralFeatureEngineer(account_id=args.account_id)
    transactions = engineer.load_raw_transactions()
    result = engineer.build_features(transactions)
    engineer.persist_behavioral_profile(result.profile_frame)

    print("Behavioral profile extracted successfully.")
    print(f"Baseline transactions used: {len(result.baseline_transactions)}")
    print(f"Profiles written: {len(result.profile_frame)}")
    print(f"Unique accounts processed: {result.profile_frame['account_id'].nunique()}")

    if args.print_model_frame:
        print(result.model_frame.to_string(index=False))


if __name__ == "__main__":
    main()
