import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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
