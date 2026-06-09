"""
Đánh giá chất lượng phản hồi — chỉ 4 chỉ số LLM-as-Judge 
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langsmith import Client
from langsmith.evaluation import evaluate

from src.agents.Supervisor_agent import build_supervisor
from evaluation.dataset_e2e import DATASET_NAME, EXAMPLES
from evaluation.evaluators_strict import QUALITY_EVALUATORS

DEFAULT_EVAL_MODELS = ["gpt-4.1-mini"]
DEFAULT_LANGSMITH_PROJECT = "KLTN_ChatBot"
QUALITY_KEYS = ["groundedness", "relevance", "completeness", "clarity"]
_RETRY_EXCEPTIONS = ("RateLimitError", "APIStatusError", "InternalServerError")
_MAX_RETRIES = 5


def get_eval_models() -> list[str]:
    models = os.getenv("E2E_EVAL_MODELS")
    if not models:
        return DEFAULT_EVAL_MODELS
    return [m.strip() for m in models.split(",") if m.strip()]


def configure_langsmith_project(client: Client) -> str:
    project_name = (
        os.getenv("LANGSMITH_PROJECT")
        or os.getenv("LANGCHAIN_PROJECT")
        or DEFAULT_LANGSMITH_PROJECT
    )
    os.environ["LANGSMITH_PROJECT"] = project_name
    os.environ["LANGCHAIN_PROJECT"] = project_name
    client.create_project(project_name=project_name, upsert=True)
    return project_name

async def _with_retry(coro_fn, *args, label: str = ""):
    for attempt in range(_MAX_RETRIES):
        try:
            return await coro_fn(*args)
        except Exception as e:
            if type(e).__name__ not in _RETRY_EXCEPTIONS or attempt == _MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"[retry:{label}] {type(e).__name__}, wait {wait}s ({attempt + 1}/{_MAX_RETRIES})")
            await asyncio.sleep(wait)


def _extract_supervisor_outputs(messages: list) -> tuple[str, dict]:
    """response + tool_outputs từ messages của supervisor."""
    response = messages[-1].content if messages else ""
    tool_outputs: dict = {}
    for msg in messages:
        tool_name = getattr(msg, "name", None)
        if tool_name and msg.content:
            try:
                tool_outputs[tool_name] = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                tool_outputs[tool_name] = msg.content
    return response, tool_outputs


def _make_target(supervisor, model_name: str):
    def target(inputs: dict) -> dict:
        question = inputs["question"]
        print(f"[eval:{model_name}] {question[:70]}...")

        async def _invoke() -> dict:
            sup_result = await _with_retry(
                supervisor.ainvoke,
                {"messages": [HumanMessage(content=question)]},
                {"configurable": {"thread_id": f"q_{abs(hash(question))}"}},
                label=f"supervisor/{model_name}",
            )
            response, tool_outputs = _extract_supervisor_outputs(
                sup_result.get("messages", [])
            )
            return {"response": response, "tool_outputs": tool_outputs}

        return asyncio.run(_invoke())

    return target


# Dataset
def upload_dataset(client: Client) -> str:
    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        print(f"[dataset] Dùng lại '{DATASET_NAME}' ({existing[0].id})")
        return existing[0].id
    dataset = client.create_dataset(DATASET_NAME)
    client.create_examples(
        inputs=[e["inputs"] for e in EXAMPLES],
        dataset_id=dataset.id,
    )
    print(f"[dataset] Đã tạo '{DATASET_NAME}' với {len(EXAMPLES)} examples")
    return dataset.id


# Report
def _avg(lst: list):
    return sum(lst) / len(lst) if lst else None


def _collect_results(results_iter) -> dict:
    overall = {m: [] for m in QUALITY_KEYS}
    for r in list(results_iter):
        feedbacks = getattr(getattr(r, "evaluation_results", None), "results", [])
        for fb in feedbacks:
            key = getattr(fb, "key", None)
            score = getattr(fb, "score", None)
            if score is None:
                continue
            if key in QUALITY_KEYS:
                overall[key].append(float(score))
    return overall


# Main
def run_model_eval(client: Client, model_name: str) -> dict:
    print(f"\n[startup] Eval model={model_name} ({len(EXAMPLES)} cases)...")
    supervisor = build_supervisor(model=model_name, checkpointer=MemorySaver())
    target = _make_target(supervisor, model_name)

    results_iter = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=QUALITY_EVALUATORS,
        experiment_prefix=f"quality_{model_name}",
        metadata={"model": model_name, "eval_type": "quality_strict"},
        max_concurrency=1,
        client=client,
    )

    overall = _collect_results(results_iter)
    all_scores = [s for lst in overall.values() for s in lst]
    return {
        "model": model_name,
        "quality_avg": (_avg(all_scores) or 0.0) * 5,
        "by_metric": {m: (_avg(overall[m]) or 0.0) * 5 for m in QUALITY_KEYS},
    }


def main(models: list[str] | None = None):
    models = models or get_eval_models()
    print(f"[startup] Models: {', '.join(models)}")

    client = Client()
    project_name = configure_langsmith_project(client)
    print(f"[startup] LangSmith project: {project_name}")
    upload_dataset(client)

    for m in models:
        run_model_eval(client, m)

    print("\nLangSmith: https://smith.langchain.com")


if __name__ == "__main__":
    main()
