import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from src.llm.llm_client import OpenAIClient
from src.tools.execute_sql import execute_sql
from src.tools.get_unique_value import get_unique_values
from src.prompts.Analyst_prompt import ANALYST_PROMPT
from src.utils.chart_labels_loader import load_chart_labels
from src.tools.calculator import add, subtract, multiply, divide
from src.tools.get_schema import get_schema

_REASONING_MODELS = frozenset({"o4-mini"})
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def create_analyst_agent(model: str = _DEFAULT_MODEL):
    temperature = 1 if model in _REASONING_MODELS else 0
    llm = OpenAIClient(model=model, temperature=temperature)

    system_prompt = ANALYST_PROMPT.format(
        chart_labels=load_chart_labels()
    )

    return create_agent(
        model=llm,
        tools=[get_schema, get_unique_values, execute_sql, add, subtract, multiply, divide],
        system_prompt=system_prompt,
        name="Analyst_Agent",
    )


TEST_CASES = [
    {
        "level": 1,
        "id": "L1-1",
        "desc": "Count toàn bảng",
        "query": "Có bao nhiêu bất động sản trong hệ thống?",
        "expect": "text",
    },
    {
        "level": 1,
        "id": "L1-2",
        "desc": "AVG tổng giá toàn thành phố",
        "query": "Giá trung bình toàn Hà Nội là bao nhiêu?",
        "expect": "text",
    },
    {
        "level": 1,
        "id": "L1-3",
        "desc": "AVG diện tích toàn bảng",
        "query": "Diện tích trung bình của bất động sản tại Hà Nội là bao nhiêu m²?",
        "expect": "text",
    },

    {
        "level": 2,
        "id": "L2-1",
        "desc": "Top N ranking",
        "query": "Top 5 quận có giá trung bình cao nhất Hà Nội",
        "expect": "text",
    },
    {
        "level": 2,
        "id": "L2-2",
        "desc": "Group by categorical",
        "query": "Số lượng bất động sản theo tình trạng nội thất",
        "expect": "text",
    },
    {
        "level": 2,
        "id": "L2-3",
        "desc": "Group by pháp lý",
        "query": "Phân bố số lượng bất động sản theo loại pháp lý",
        "expect": "text",
    },

    {
        "level": 3,
        "id": "L3-1",
        "desc": "AVG filter theo quận rõ ràng",
        "query": "Giá trung bình tại quận Cầu Giấy là bao nhiêu?",
        "expect": "text",
    },
    {
        "level": 3,
        "id": "L3-2",
        "desc": "Histogram khoảng giá",
        "query": "Phân bố bất động sản theo khoảng giá (dưới 2 tỷ, 2-5 tỷ, 5-10 tỷ, trên 10 tỷ)",
        "expect": "text",
    },
    {
        "level": 3,
        "id": "L3-3",
        "desc": "Bar chart giá theo quận",
        "query": "Vẽ biểu đồ giá trung bình theo quận tại Hà Nội",
        "expect": "json",
    },
    {
        "level": 3,
        "id": "L3-4",
        "desc": "Pie chart phân bố pháp lý",
        "query": "Vẽ biểu đồ tỷ lệ bất động sản theo loại pháp lý",
        "expect": "json",
    },

    {
        "level": 4,
        "id": "L4-1",
        "desc": "Window: so sánh với trung bình toàn thành phố",
        "query": "Quận nào có giá/m² cao hơn mặt bằng chung toàn Hà Nội? Chênh lệch là bao nhiêu?",
        "expect": "text",
    },
    {
        "level": 4,
        "id": "L4-2",
        "desc": "Time series xu hướng giá theo tháng",
        "query": "Vẽ biểu đồ xu hướng giá trung bình theo tháng tại Hà Nội",
        "expect": "json",
    },
    {
        "level": 4,
        "id": "L4-3",
        "desc": "Scatter tương quan diện tích và giá",
        "query": "Vẽ biểu đồ tương quan giữa diện tích và giá bán tại quận Ba Đình",
        "expect": "json",
    },
    {
        "level": 4,
        "id": "L4-4",
        "desc": "Tính toán phát sinh: tỷ lệ % chênh lệch",
        "query": "Giá trung bình Hoàn Kiếm cao hơn giá trung bình Hà Đông bao nhiêu phần trăm?",
        "expect": "text",
    },
    {
        "level": 4,
        "id": "L4-5",
        "desc": "Top N trong phường, filter theo quận",
        "query": "Top 3 phường có giá/m² cao nhất tại quận Cầu Giấy",
        "expect": "text",
    },

    {
        "level": 5,
        "id": "L5-1",
        "desc": "Budget filtering + phân tích đa chiều",
        "query": "Với tài chính 2-4 tỷ, khu vực nào tại Hà Nội phù hợp nhất? Cho biết số lượng, giá TB và diện tích TB theo từng quận",
        "expect": "text",
    },
    {
        "level": 5,
        "id": "L5-2",
        "desc": "Stacked bar: cơ cấu nội thất theo quận",
        "query": "Vẽ biểu đồ cơ cấu nội thất (full, cơ bản, không nội thất) theo quận tại Hà Nội",
        "expect": "json",
    },
    {
        "level": 5,
        "id": "L5-3",
        "desc": "Window + HAVING: outlier giá/m² vượt ngưỡng",
        "query": "Phường nào có giá/m² trung bình cao hơn 1.5 lần mặt bằng toàn quận của nó? Liệt kê theo quận",
        "expect": "text",
    },
    {
        "level": 5,
        "id": "L5-4",
        "desc": "Time series + filter + tính toán % tăng trưởng",
        "query": "Giá trung bình tại Cầu Giấy thay đổi như thế nào theo từng quý? Quý nào tăng mạnh nhất?",
        "expect": "text",
    },
    {
        "level": 5,
        "id": "L5-5",
        "desc": "get_unique_values bắt buộc: filter nội thất mơ hồ",
        "query": "Bất động sản full nội thất tại Đống Đa có giá trung bình bao nhiêu? So sánh với không nội thất",
        "expect": "text",
    },
]


def run_test(agent, case: dict):
    print(f"\n{'=' * 70}")
    print(f"[{case['id']}] Level {case['level']} — {case['desc']}")
    print(f"Query: {case['query']}")
    print(f"Expect output: {case['expect']}")
    print("-" * 70)
    result = asyncio.run(agent.ainvoke({
        "messages": [HumanMessage(content=case["query"])]
    }))
    print(result["messages"][-1].content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=None, help="Chạy test level cụ thể (1-5), bỏ qua để chạy tất cả")
    parser.add_argument("--id", type=str, default=None, help="Chạy test case cụ thể theo id (vd: L3-2)")
    args = parser.parse_args()

    agent = create_analyst_agent()

    cases = TEST_CASES
    if args.id:
        cases = [c for c in TEST_CASES if c["id"] == args.id]
    elif args.level:
        cases = [c for c in TEST_CASES if c["level"] == args.level]

    print(f"Chạy {len(cases)} test case(s)...")
    for case in cases:
        run_test(agent, case)
