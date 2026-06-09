import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
IN_JSON = HERE / "evaluation_metrics.json"
OUT_DIR = HERE / "charts"

SCALE = "1_5"  # 
METRICS = ["clarity", "completeness", "groundedness", "relevance"]
METRIC_VI = {
    "groundedness": "Tính căn cứ dữ liệu",
    "relevance": "Tính liên quan",
    "completeness": "Tính đầy đủ",
    "clarity": "Tính rõ ràng",
}
_YMAX = 5 if SCALE == "1_5" else 1.0

METRIC_COLORS = {
    "clarity": "#6C2FBE",       # tím
    "completeness": "#C3A6E6",  # tím nhạt (lavender)
    "groundedness": "#3E8EF0",  # xanh dương
    "relevance": "#BFDCEA",     # xanh nhạt
}


def load_summary() -> dict:
    if not IN_JSON.exists():
        raise SystemExit(f"Không thấy {IN_JSON}. Chạy export_eval_metrics.py trước.")
    data = json.loads(IN_JSON.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    # sắp xếp model theo overall giảm dần cho biểu đồ gọn
    key = f"overall_{SCALE}"
    return dict(
        sorted(summary.items(), key=lambda kv: kv[1].get(key) or 0, reverse=True)
    )


def _metric_val(model_summary: dict, metric: str) -> float:
    return model_summary[f"by_metric_{SCALE}"].get(metric) or 0.0


# Tên hiển thị tuỳ chỉnh cho nhãn trục X (ghi đè tên mặc định).
MODEL_DISPLAY = {
    "mistralai/mistral-small-2603": "Mistral Small 4",
}


def _short_name(model: str) -> str:
    """Tên model gọn cho nhãn trục: ưu tiên tên tuỳ chỉnh, nếu không thì bỏ tiền tố provider."""
    if model in MODEL_DISPLAY:
        return MODEL_DISPLAY[model]
    return model.split("/")[-1]


def plot_grouped_bar(summary: dict):
    # summary đã sắp theo overall giảm dần -> model tốt nhất ở ngoài cùng bên trái.
    models = list(summary.keys())
    x = np.arange(len(models))
    width = 0.8 / len(METRICS)

    fig, ax = plt.subplots(figsize=(11, 6))
    for j, metric in enumerate(METRICS):
        vals = [_metric_val(summary[m], metric) for m in models]
        ax.bar(
            x + j * width, vals, width, label=METRIC_VI[metric],
            color=METRIC_COLORS[metric],
        )

    ax.set_xticks(x + width * (len(METRICS) - 1) / 2)
    ax.set_xticklabels([_short_name(m) for m in models], rotation=15, ha="right")
    ax.set_ylabel(f"Điểm ({'thang 1-5' if SCALE == '1_5' else 'thang 0-1'})")
    ax.set_ylim(0, _YMAX)
    ax.set_title("Kết quả chất lượng phản hồi của hệ thống")
    ax.legend(title="Chỉ số", bbox_to_anchor=(1.01, 1), loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    out = OUT_DIR / "grouped_bar.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"[saved] {out}")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"  # hỗ trợ tiếng Việt
    summary = load_summary()
    if not summary:
        raise SystemExit("summary rỗng — không có dữ liệu để vẽ.")
    print(f"[models] {', '.join(summary.keys())}")
    plot_grouped_bar(summary)


if __name__ == "__main__":
    main()
