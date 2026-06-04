import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DIR = Path(__file__).parent
CSV_PATH  = DIR / ".." / "data" / "data_clean.csv"
OUT_PATH  = DIR / "descriptions_clean_1.json"

FIELD_MAP = {
    "Mã code":                 "ma_code",
    "Mô tả":                   "mo_ta",
}


def _regex_clean(text: str) -> str:
    text = re.sub(r"\b0\d{1,2}[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}\b", "", text)
    text = re.sub(r"\d{2,4}[\s.\-]?\*+\d*", "", text)
    text = re.sub(r"\*{2,}", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\S+@\S+\.\S+", "", text)
    text = re.sub(r"#\S+", "", text)
    text = re.sub(r"={3,}|-{3,}|_{3,}", "", text)
    # Xóa block "Hotline ... ***" (số điện thoại ẩn có thể ở cùng dòng hoặc dòng tiếp theo)
    text = re.sub(r"(?i)-?\s*hotline[^\n]*(?:\n[^\n]*)?\*{2,}", "", text)
    text = re.sub(r"(?i)\b(liên hệ|hotline|zalo|call|inbox|sđt|điện thoại)\b\s*:?", "", text)
    return text


def _normalize(text: str) -> str:
    text = re.sub(r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|mét vuông|met vuong)", r"\1m2", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)\s*(?:PN\b|p\.?\s*ngủ|phòng ngủ)", r"\1 phòng ngủ", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+)\s*(?:WC\b|toilet\b|p\.?\s*tắm|phòng tắm)", r"\1 phòng tắm", text, flags=re.IGNORECASE)
    text = re.sub(r"(\d+),(\d+)\s*(tỷ|triệu|tr)", r"\1.\2 \3", text, flags=re.IGNORECASE)
    return text


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    seen, out = set(), []
    for line in text.split("\n"):
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)


def clean_text(text: str) -> str:
    return _tidy(_normalize(_regex_clean(text)))


def build(csv_path: Path = CSV_PATH, out_path: Path = OUT_PATH) -> int:
    items = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            item = {key: (row.get(col) or "").strip() for col, key in FIELD_MAP.items()}
            if not item["ma_code"] or not item["mo_ta"]:
                continue
            item["mo_ta"] = clean_text(item["mo_ta"])
            if item["mo_ta"]:
                items.append(item)

    out_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(items)} listings → {out_path}")
    return len(items)


if __name__ == "__main__":
    build()
