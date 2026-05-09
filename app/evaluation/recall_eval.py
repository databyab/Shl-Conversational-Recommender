from __future__ import annotations


def recall_at_k(expected: list[str], recommended: list[str], k: int = 10) -> float:
    if not expected:
        return 1.0
    expected_norm = {_norm(name) for name in expected}
    recommended_norm = {_norm(name) for name in recommended[:k]}
    return len(expected_norm & recommended_norm) / len(expected_norm)


def _norm(name: str) -> str:
    return " ".join(name.lower().replace("–", "-").split())


def aggregate_recall(results: list[dict], k: int = 10) -> dict:
    scores = [
        recall_at_k(result.get("expected", []), result.get("recommended", []), k=k)
        for result in results
    ]
    return {
        "k": k,
        "conversation_count": len(results),
        "mean_recall": sum(scores) / max(len(scores), 1),
        "scores": scores,
    }
