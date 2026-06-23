import sys
import os
import re
import unicodedata

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from data.database import Database

CSV_PATH = os.path.join(os.path.dirname(__file__), "data_clean.csv")


def _light_normalize(value):
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value)).strip()
    if text.lower() == "nan":
        return "NAN"
    text = text.lstrip("-").strip()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(" .")
    return text or None


def normalize_phap_ly(value):
    text = _light_normalize(value)
    if not text or text == "NAN":
        return text
    core = re.sub(r"\s*/\s*", "/", text.lower())
    if core.startswith("sổ đỏ/sổ hồng"):
        return "Sổ đỏ/ Sổ hồng (sử dụng chung)" if "sử dụng chung" in core else "Sổ đỏ/ Sổ hồng"
    return text


def normalize_noi_that(value):
    return _light_normalize(value)


PROPERTIES_SQL = """
    INSERT INTO properties (ma_code, tieu_de, ngay_dang, quan, phuong, tong_gia, gia_theo_m2, dien_tich, so_tang, so_phong_ngu, so_phong_tam, phap_ly, noi_that)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (ma_code) DO NOTHING
"""


def load_data():
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    df = df.where(pd.notna(df), None)

    properties_rows = [
        (
            row["Mã code"],
            row["Tiêu đề"],
            row["Ngày đăng"] if row["Ngày đăng"] else None,
            row["Quận/Huyện"],
            row["Phường/Xã"],
            row["Tổng giá (tỷ)"],
            row["Giá theo m² (triệu/m²)"],
            row["Diện tích (m²)"],
            int(row["Số tầng"]) if row["Số tầng"] is not None else None,
            int(row["Số phòng ngủ"]) if row["Số phòng ngủ"] is not None else None,
            int(row["Số phòng tắm, vệ sinh"]) if row["Số phòng tắm, vệ sinh"] is not None else None,
            normalize_phap_ly(row["Pháp lý"]),
            normalize_noi_that(row["Nội thất"]),
        )
        for _, row in df.iterrows()
    ]

   

    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            from psycopg2.extras import execute_batch
            execute_batch(cur, PROPERTIES_SQL, properties_rows)

    print(f"Inserted {len(properties_rows)} rows into properties ")

if __name__ == "__main__":
    try:
        load_data()
    except Exception as e:
        print("Error ingesting data:", e)
