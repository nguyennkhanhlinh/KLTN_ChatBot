import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from psycopg2 import sql
from data.database import Database





@tool
def get_unique_values(table_name: str, columns: list[str]) -> str:
    """Lấy danh sách giá trị duy nhất của các cột text/categorical.

    Dùng khi cần biết các giá trị hợp lệ trong DB để viết SQL filter chính xác,
    tránh sai chính tả hoặc không khớp dữ liệu thực tế (vd: tên quận, pháp lý, nội thất).
    KHÔNG dùng cho cột có quá nhiều giá trị duy nhất (vd: tieu_de, ma_code).

    Args:
        table_name: Tên bảng (vd: "properties").
        columns: Danh sách tên cột cần lấy DISTINCT (vd: ["quan", "phap_ly"]).
    """
    if not columns:
        return "Lỗi: cần ít nhất 1 cột."

    try:
        lines = []
        with Database.get_conn() as conn:
            with conn.cursor() as cursor:
                for col in columns:
                    query = sql.SQL(
                        "SELECT DISTINCT {col} FROM {tbl} "
                        "WHERE {col} IS NOT NULL ORDER BY {col}"
                    ).format(
                        col=sql.Identifier(col),
                        tbl=sql.Identifier(table_name),
                       
                    )
                    cursor.execute(query)
                    values = [str(row[0]) for row in cursor.fetchall()]
                    lines.append(f"{col} ({len(values)}): {', '.join(values)}")
        return "\n".join(lines) if lines else "Không có dữ liệu."

    except Exception as e:
        return f"Lỗi: {e}"
