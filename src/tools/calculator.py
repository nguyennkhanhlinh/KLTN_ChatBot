import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool


@tool
def add(a: float, b: float) -> float:
    """Cộng hai số.

    Args:
        a: Số thứ nhất.
        b: Số thứ hai.
    """
    return a + b


@tool
def subtract(a: float, b: float) -> float:
    """Trừ hai số (a - b).

    Args:
        a: Số bị trừ.
        b: Số trừ.
    """
    return a - b


@tool
def multiply(a: float, b: float) -> float:
    """Nhân hai số.

    Args:
        a: Số thứ nhất.
        b: Số thứ hai.
    """
    return a * b


@tool
def divide(a: float, b: float) -> float | str:
    """Chia hai số (a / b).

    Args:
        a: Số bị chia.
        b: Số chia.
    """
    if b == 0:
        return "Lỗi: Không thể chia cho 0"
    return a / b
