import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from src.llm.llm_client import OpenAIClient
from src.prompts.Recommendation_prompt import Recommendation_PROMPT
from src.tools.execute_sql import execute_sql
from src.tools.get_unique_value import get_unique_values
from src.tools.retrieve_context import retrieve_context
from src.tools.get_schema import get_schema

_REASONING_MODELS = frozenset({"o4-mini"})
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def create_Recommendation_agent(model: str = _DEFAULT_MODEL):
    """Recommendation agent: Hybrid Retrieval (SQL + Vector Search).

    Flow:
      Case A (structured + semantic): execute_sql → ma_codes → retrieve_context → merge
      Case B (structured only):       execute_sql → format
      Case C (semantic only):         retrieve_context(ma_codes=None) → format
    """
    temperature = 1 if model in _REASONING_MODELS else 0
    llm = OpenAIClient(model=model, temperature=temperature)

    return create_agent(
        model=llm,
        tools=[get_schema, execute_sql, get_unique_values, retrieve_context],
        system_prompt=Recommendation_PROMPT,
        name="Recommendation_agent",
    )


if __name__ == "__main__":
    agent = create_Recommendation_agent()

    test_questions = [
        "Căn hộ 3PN Cầu Giấy dưới 5 tỷ gần metro",        # Case A
        "Nhà 2PN dưới 5 tỷ ở Gia Lâm",                     # Case B
        "Căn nào view hồ Tây đẹp?",                         # Case C
        "Căn hộ 3PN Thanh Xuân, nội thất đầy đủ, tầm 7-8 tỷ có không gian sống thoáng mát",  # Case A
        "Nhà dưới 6 tỷ ở Đống Đa, diện tích trên 50m², gần hồ hoặc công viên",               # Case A
    ]

    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"{'='*60}")
        try:
            result = asyncio.run(agent.ainvoke({
                "messages": [HumanMessage(content=question)]
            }))
            print(result["messages"][-1].content)
        except Exception as e:
            print(f"Lỗi: {e}")
