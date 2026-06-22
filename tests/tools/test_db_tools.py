import json
from src.tools.execute_sql import execute_sql
from src.tools.get_schema import get_schema
from src.tools.get_unique_value import get_unique_values


class TestExecuteSql:
    def test_blocks_drop(self, mock_db):
        out = execute_sql.invoke({"sql_query": "DROP TABLE properties"})
        assert "không được phép" in out
        assert "DROP" in out
        assert mock_db.executed == []  

    def test_blocks_delete(self, mock_db):
        out = execute_sql.invoke({"sql_query": "DELETE FROM properties WHERE ma_code = 1"})
        assert "không được phép" in out
        assert "DELETE" in out
        assert mock_db.executed == []

    def test_blocks_insert(self, mock_db):
        out = execute_sql.invoke({"sql_query": "INSERT INTO properties VALUES (1)"})
        assert "không được phép" in out
        assert "INSERT" in out
        assert mock_db.executed == []

    def test_blocks_update(self, mock_db):
        out = execute_sql.invoke({"sql_query": "UPDATE properties SET tong_gia = 0"})
        assert "không được phép" in out
        assert "UPDATE" in out
        assert mock_db.executed == []

    def test_blocks_alter(self, mock_db):
        out = execute_sql.invoke({"sql_query": "ALTER TABLE properties ADD COLUMN x int"})
        assert "không được phép" in out
        assert "ALTER" in out
        assert mock_db.executed == []

    def test_blocks_truncate(self, mock_db):
        out = execute_sql.invoke({"sql_query": "TRUNCATE properties"})
        assert "không được phép" in out
        assert "TRUNCATE" in out
        assert mock_db.executed == []

    def test_blocks_grant(self, mock_db):
        out = execute_sql.invoke({"sql_query": "GRANT ALL ON properties TO public"})
        assert "không được phép" in out
        assert "GRANT" in out
        assert mock_db.executed == []

    def test_blocks_revoke(self, mock_db):
        out = execute_sql.invoke({"sql_query": "REVOKE ALL ON properties FROM public"})
        assert "không được phép" in out
        assert "REVOKE" in out
        assert mock_db.executed == []

    def test_blocks_replace(self, mock_db):
        out = execute_sql.invoke({"sql_query": "REPLACE INTO properties VALUES (1)"})
        assert "không được phép" in out
        assert "REPLACE" in out
        assert mock_db.executed == []

    def test_forbidden_is_case_insensitive(self, mock_db):
        # token được .upper() trước khi so khớp -> chữ thường vẫn bị chặn
        out = execute_sql.invoke({"sql_query": "drop table properties"})
        assert "không được phép" in out
        assert "DROP" in out
        assert mock_db.executed == []

    def test_blocks_multiple_keywords_sorted(self, mock_db):
        out = execute_sql.invoke({"sql_query": "DROP TABLE x; CREATE TABLE y (id int)"})
        # blocked được sort theo alphabet -> "CREATE, DROP"
        assert "CREATE, DROP" in out
        assert mock_db.executed == []

    def test_text_output(self, mock_db):
        mock_db.description = [("ma_code",), ("quan",)]
        mock_db.fetchall_results = [[(1, "Q1"), (2, "Q2")]]
        out = execute_sql.invoke({"sql_query": "SELECT ma_code, quan FROM properties"})
        assert "ma_code | quan" in out
        assert "1 | Q1" in out
        assert "2 | Q2" in out

    def test_auto_appends_limit(self, mock_db):
        mock_db.description = [("ma_code",)]
        mock_db.fetchall_results = [[(1,)]]
        execute_sql.invoke({"sql_query": "SELECT ma_code FROM properties"})
        assert "LIMIT 100" in mock_db.executed[-1]

    def test_keeps_existing_limit(self, mock_db):
        mock_db.description = [("ma_code",)]
        mock_db.fetchall_results = [[(1,)]]
        execute_sql.invoke({"sql_query": "SELECT ma_code FROM properties LIMIT 5"})
        assert "LIMIT 100" not in mock_db.executed[-1]

    def test_json_output(self, mock_db):
        mock_db.description = [("ma_code",), ("quan",)]
        mock_db.fetchall_results = [[(1, "Q1"), (2, None)]]
        out = execute_sql.invoke({
            "sql_query": "SELECT ma_code, quan FROM properties",
            "output_format": "json",
        })
        data = json.loads(out)
        assert data["columns"] == ["ma_code", "quan"]
        assert data["data"] == [["1", "Q1"], ["2", None]]  # giá trị -> str, None giữ nguyên

    def test_no_rows(self, mock_db):
        mock_db.description = [("ma_code",)]
        mock_db.fetchall_results = [[]]
        out = execute_sql.invoke({"sql_query": "SELECT ma_code FROM properties WHERE 1=0"})
        assert out == "Không tìm thấy dữ liệu phù hợp."

    def test_no_result_set(self, mock_db):
        mock_db.description = None  # câu lệnh không trả dữ liệu
        out = execute_sql.invoke({"sql_query": "SELECT set_config('x','y',false)"})
        assert "không có dữ liệu trả về" in out

    def test_db_error(self, mock_db):
        mock_db.raise_exc = Exception("connection lost")
        out = execute_sql.invoke({"sql_query": "SELECT * FROM properties"})
        assert "Lỗi khi thực thi SQL" in out
        assert "connection lost" in out


# get_schema
class TestGetSchema:
    def test_returns_columns(self, mock_db):
        mock_db.fetchall_results = [[
            ("ma_code", "integer", "Mã tin"),
            ("quan", "text", None),
        ]]
        out = get_schema.invoke({"table_name": "properties"})
        assert "Table: properties" in out
        assert "ma_code (integer) — Mã tin" in out
        assert "quan (text)" in out

    def test_table_not_found(self, mock_db):
        mock_db.fetchall_results = [[]]
        out = get_schema.invoke({"table_name": "khong_ton_tai"})
        assert "Không tìm thấy bảng 'khong_ton_tai'." == out

    def test_error(self, mock_db):
        mock_db.raise_exc = Exception("permission denied")
        out = get_schema.invoke({"table_name": "properties"})
        assert "Lỗi khi lấy schema" in out


# get_unique_values
class TestGetUniqueValues:
    def test_empty_columns(self, mock_db):
        out = get_unique_values.invoke({"table_name": "properties", "columns": []})
        assert out == "Lỗi: cần ít nhất 1 cột."
        assert mock_db.executed == []

    def test_single_column(self, mock_db):
        mock_db.fetchall_results = [[("Q1",), ("Q2",), ("Q3",)]]
        out = get_unique_values.invoke({"table_name": "properties", "columns": ["quan"]})
        assert out == "quan (3): Q1, Q2, Q3"

    def test_multiple_columns(self, mock_db):
        mock_db.fetchall_results = [
            [("Quận 1",), ("Quận 2",)],
            [("Sổ đỏ",), ("HĐMB",)],
        ]
        out = get_unique_values.invoke({
            "table_name": "properties", "columns": ["quan", "phap_ly"],
        })
        lines = out.split("\n")
        assert lines[0] == "quan (2): Quận 1, Quận 2"
        assert lines[1] == "phap_ly (2): Sổ đỏ, HĐMB"

    def test_error(self, mock_db):
        mock_db.raise_exc = Exception("undefined column")
        out = get_unique_values.invoke({"table_name": "properties", "columns": ["quan"]})
        assert "Lỗi:" in out
        assert "undefined column" in out
