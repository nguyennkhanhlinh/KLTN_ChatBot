"""Test 4 tool số học cơ bản. Gọi tool qua .invoke({...})."""
from src.tools.calculator import add, subtract, multiply, divide


class TestAdd:
    def test_positive(self):
        assert add.invoke({"a": 2, "b": 3}) == 5

    def test_negative(self):
        assert add.invoke({"a": -5, "b": 2}) == -3

    def test_float(self):
        assert add.invoke({"a": 1.5, "b": 2.5}) == 4.0


class TestSubtract:
    def test_basic(self):
        assert subtract.invoke({"a": 10, "b": 4}) == 6

    def test_negative_result(self):
        assert subtract.invoke({"a": 3, "b": 8}) == -5


class TestMultiply:
    def test_basic(self):
        assert multiply.invoke({"a": 4, "b": 3}) == 12

    def test_by_zero(self):
        assert multiply.invoke({"a": 99, "b": 0}) == 0


class TestDivide:
    def test_basic(self):
        assert divide.invoke({"a": 10, "b": 2}) == 5

    def test_float_result(self):
        assert divide.invoke({"a": 7, "b": 2}) == 3.5

    def test_divide_by_zero(self):
        # Không raise — trả về chuỗi lỗi tiếng Việt
        assert divide.invoke({"a": 5, "b": 0}) == "Lỗi: Không thể chia cho 0"
