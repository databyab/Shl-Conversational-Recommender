from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.evaluation.recall_eval import aggregate_recall
from app.evaluation.replay_harness import replay_directory


def main() -> None:
    root = get_settings().root_dir
    results = replay_directory(root / "GenAI_SampleConversations")
    metrics = aggregate_recall(results, k=10)
    print(metrics)
    for result, score in zip(results, metrics["scores"]):
        print(f"{Path(result['file']).name}: recall@10={score:.2f} recommended={result['recommended']}")


if __name__ == "__main__":
    main()
