"""
Dataset v2 — cùng bộ 50 test cases với v1, upload lên LangSmith dưới tên mới
để chạy experiment độc lập mà không ghi đè kết quả cũ.
"""

from evaluation.end_to_end.dataset_e2e import EXAMPLES

DATASET_NAME = "e2e_workflow_v1"

__all__ = ["DATASET_NAME", "EXAMPLES"]
