import os
import yaml


def load_chart_labels() -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "label", "chart_labels.yaml",
    )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    lines = []
    for col, label in data.get("labels", {}).items():
        lines.append(f'- {col} → "{label}"')

    fallback = data.get("fallback", "").strip()
    if fallback:
        lines.append(f"- {fallback}")

    return "\n".join(lines)
