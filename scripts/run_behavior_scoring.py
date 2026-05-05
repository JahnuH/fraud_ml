import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.modeling import HybridBehaviorScorer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the hybrid behavioral anomaly detector on baseline transactions and score the anomalous month."
    )
    parser.add_argument("--account-id", default=None, help="Optional account_id filter.")
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top-scored anomalous transactions to print.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    scorer = HybridBehaviorScorer(account_id=args.account_id)
    artifacts = scorer.run()
    scorer.persist_scoring_results(artifacts.scored_transactions)

    print("Hybrid anomaly scoring completed.")
    print(f"Baseline transactions used for training: {len(artifacts.baseline_transactions)}")
    print(f"Anomalous-month transactions scored: {len(artifacts.anomalous_transactions)}")
    print()
    print("Monthly summary:")
    print(artifacts.monthly_summary.to_string(index=False))
    print()
    print("Top anomalous transactions:")
    display_columns = [
        "event_id",
        "event_ts",
        "amount",
        "behavior_score",
        "behavior_change",
        "behavior_reasons",
    ]
    print(
        artifacts.scored_transactions.sort_values("behavior_score", ascending=False)
        .head(args.top_n)[display_columns]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
