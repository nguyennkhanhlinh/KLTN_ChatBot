import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from src.llm.llm_client import OpenAIClient
from src.tools.calculate_finance import calculate_finance
from src.tools.compare_loan_scenarios import compare_loan_scenarios
from src.tools.calculate_hybrid_rate import calculate_hybrid_rate
from src.tools.calculator import add, subtract, multiply, divide
from src.prompts.Finance_prompt import FINANCE_PROMPT


_REASONING_MODELS = frozenset({"o4-mini"})
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def create_finance_agent(model: str = _DEFAULT_MODEL):
    temperature = 1 if model in _REASONING_MODELS else 0
    llm = OpenAIClient(model=model, temperature=temperature)

   
    return create_agent(
        model=llm,
        tools=[calculate_finance, compare_loan_scenarios, calculate_hybrid_rate, add, subtract, multiply, divide],
        system_prompt=FINANCE_PROMPT,
        name="Finance_Agent",
    )


if __name__ == "__main__":
    import asyncio

    agent = create_finance_agent()

    questions = [
        "Tôi có 1.5 tỷ, lãi suất 9%/năm, thu nhập 30 triệu/tháng, muốn vay 20 năm. Tôi mua được nhà ở đâu?",
        "Với 2 tỷ vốn tự có, thu nhập 40tr, lãi 8.5%, vay 25 năm thì trả góp bao nhiêu?",
        
    ]

    for q in questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")
        result = asyncio.run(agent.ainvoke({
            "messages": [HumanMessage(content=q)]
        }))
        print(result["messages"][-1].content)
