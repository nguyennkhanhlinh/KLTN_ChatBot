import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from langsmith import Client

from evaluation.dataset_e2e import DATASET_NAME
from configs.llm import MODEL_REGISTRY

QUALITY_KEYS = ["groundedness", "relevance", "completeness", "clarity"]
OUT_JSON = Path(__file__).resolve().parent / "evaluation_metrics.json"

def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name.lower())

_SLUG_TO_MODEL = {_slug(m): m for m in MODEL_REGISTRY}


def _avg(lst: list) -> float | None:
    return sum(lst) / len(lst) if lst else None


def _normalize_model_name(name: str) -> str:
    """Quy mọi biến thể tên (slug LangSmith, có hậu tố hash) về id chuẩn trong registry."""
    if name in MODEL_REGISTRY:
        return name
    slug = _slug(name)
    if slug in _SLUG_TO_MODEL:
        return _SLUG_TO_MODEL[slug]
    # tên experiment có thể kèm hậu tố (vd "gpt_4.1_mini-1a2b") -> khớp theo tiền tố slug
    for known_slug, model in _SLUG_TO_MODEL.items():
        if slug.startswith(known_slug):
            return model
    return name


def _model_of(experiment) -> str:
    """Lấy tên model từ metadata experiment, fallback về tên experiment, đã chuẩn hoá."""
    meta = (getattr(experiment, "metadata", None) or {})
    raw = meta.get("model") or getattr(experiment, "name", "unknown")
    return _normalize_model_name(raw)


def collect_rows(client: Client) -> list[dict]:
    # 1. Tìm dataset "evaluation"
    datasets = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if not datasets:
        raise SystemExit(f"Không tìm thấy dataset '{DATASET_NAME}' trên LangSmith.")
    dataset_id = datasets[0].id
    print(f"[dataset] {DATASET_NAME} ({dataset_id})")

    # 2. Liệt kê các experiment (project test) tham chiếu dataset này
    experiments = list(client.list_projects(reference_dataset_id=dataset_id))
    print(f"[experiments] tìm thấy {len(experiments)} experiment")

    rows: list[dict] = []
    for exp in experiments:
        model = _model_of(exp)
        # Chỉ giữ 4 model trong registry — bỏ qua experiment lạ / thử nghiệm khác.
        if model not in MODEL_REGISTRY:
            print(f"[skip] experiment '{getattr(exp, 'name', '?')}' -> model '{model}' không thuộc registry")
            continue
        runs = client.list_runs(project_id=exp.id, is_root=True)
        for run in runs:
            feedbacks = list(client.list_feedback(run_ids=[run.id]))
            row = {
                "experiment": getattr(exp, "name", None),
                "model": model,
                "run_id": str(run.id),
                "question": (run.inputs or {}).get("question"),
                "response": (run.outputs or {}).get("response") if run.outputs else None,
                "created_at": run.start_time.isoformat() if run.start_time else None,
            }
            for fb in feedbacks:
                if fb.key in QUALITY_KEYS and fb.score is not None:
                    row[fb.key] = fb.score
            rows.append(row)

    print(f"[runs] thu thập {len(rows)} run")
    return rows


def summarize(rows: list[dict]) -> dict:
    """Trung bình từng chỉ số theo model (thang 1-5)."""
    by_model: dict[str, dict[str, list]] = defaultdict(
        lambda: {k: [] for k in QUALITY_KEYS}
    )
    for row in rows:
        for k in QUALITY_KEYS:
            if k in row:
                by_model[row["model"]][k].append(float(row[k]))

    summary = {}
    for model, metrics in by_model.items():
        per_metric_01 = {k: _avg(metrics[k]) for k in QUALITY_KEYS}
        all_scores = [s for lst in metrics.values() for s in lst]
        overall_01 = _avg(all_scores)
        # Chỉ xuất chỉ số thang 1-5 (bỏ thang 0-1).
        summary[model] = {
            "by_metric_1_5": {
                k: (v * 5 if v is not None else None) for k, v in per_metric_01.items()
            },
            "overall_1_5": overall_01 * 5 if overall_01 is not None else None,
        }
    return summary


def main():
    client = Client()
    rows = collect_rows(client)
    summary = summarize(rows)

    payload = {"summary": summary, "runs": rows}
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[saved] {OUT_JSON}")


if __name__ == "__main__":
    main()
