import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

sys.path.append(str(Path(__file__).resolve().parents[2]))

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
from langsmith.schemas import Run, Example

from src.agents.Supervisor_agent import build_supervisor
from src.agents.Analyst_agent import create_analyst_agent
from src.agents.Finance_agent import create_finance_agent
from src.agents.Recommendation_Agent import create_Recommendation_agent
from evaluation.end_to_end.dataset_e2e import DATASET_NAME, EXAMPLES
from evaluation.evaluators import (
    eval_groundedness,
    eval_relevance,
    eval_completeness,
    eval_clarity,
)

DEFAULT_EVAL_MODELS = ["gpt-4.1-mini", "o4-mini"]
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



def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    """expected phải là subsequence của actual (thứ tự đúng, cho phép xen giữa)."""
    i = 0
    for tool in actual:
        if i < len(expected) and tool == expected[i]:
            i += 1
    return i == len(expected)


def eval_workflow_accuracy(run: Run, example: Example) -> dict:
    """
    Workflow accuracy = routing đúng AND tool sequence đúng.
    Multi-agent cases (expected_tool_sequence=None): chỉ check routing.
    """
    outputs = run.outputs or {}
    ex_outputs = example.outputs or {}

    tools_called: list[str] = outputs.get("tools_called", [])
    tool_sequence: list[str] = outputs.get("tool_sequence", [])
    expected_agent = ex_outputs.get("expected_agent")
    expected_seq = ex_outputs.get("expected_tool_sequence")

    # Routing check
    if expected_agent is None:
        return {"key": "workflow_accuracy", "score": None, "comment": "no expected_agent"}

    if isinstance(expected_agent, list):
        routing_ok = all(a in tools_called for a in expected_agent)
    else:
        routing_ok = expected_agent in tools_called

    # Tool sequence check (bỏ qua nếu None hoặc rỗng)
    if not expected_seq:
        score = 1.0 if routing_ok else 0.0
        comment = "routing OK (no seq check)" if routing_ok else f"routing FAIL: expected={expected_agent} got={tools_called}"
        return {"key": "workflow_accuracy", "score": score, "comment": comment}

    seq_ok = _is_subsequence(expected_seq, tool_sequence)
    score = 1.0 if (routing_ok and seq_ok) else 0.0

    if not routing_ok:
        comment = f"routing FAIL: expected={expected_agent} got={tools_called}"
    elif not seq_ok:
        comment = f"seq FAIL: expected={expected_seq} got={tool_sequence}"
    else:
        comment = "OK"

    return {"key": "workflow_accuracy", "score": score, "comment": comment}


ALL_EVALUATORS = [
    eval_workflow_accuracy,   # accuracy: routing + tool sequence
    eval_groundedness,        # quality
    eval_relevance,           # quality
    eval_completeness,        # quality
    eval_clarity,             # quality
]


def upload_dataset(client: Client) -> str:
    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        print(f"[dataset] Dung lai '{DATASET_NAME}' ({existing[0].id})")
        return existing[0].id
    dataset = client.create_dataset(DATASET_NAME)
    client.create_examples(
        inputs=[e["inputs"] for e in EXAMPLES],
        outputs=[e["outputs"] for e in EXAMPLES],
        dataset_id=dataset.id,
    )
    print(f"[dataset] Da tao '{DATASET_NAME}' voi {len(EXAMPLES)} examples")
    return dataset.id

def _extract_tool_sequence(messages: list) -> list[str]:
    """Lấy tên các tool được gọi theo thứ tự từ danh sách messages của agent."""
    seq: list[str] = []
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                seq.append(name)
    return seq


_SUPERVISOR_META_TOOLS = {"save_preferences", "save_profile", "recall_memory"}


def _extract_supervisor_outputs(messages: list) -> tuple[str, dict, list[str]]:
    """Trích xuất response, tool_outputs và tools_called từ messages của supervisor.

    tools_called chỉ chứa sub-agent names (analyst/finance/recommendation),
    loại bỏ supervisor meta-tools (save_preferences, save_profile, recall_memory)
    để không gây nhiễu cho routing accuracy check.
    """
    response = messages[-1].content if messages else ""
    tool_outputs: dict = {}
    for msg in messages:
        tool_name = getattr(msg, "name", None)
        if tool_name and msg.content:
            try:
                tool_outputs[tool_name] = json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                tool_outputs[tool_name] = msg.content
    tools_called = [k for k in tool_outputs if k not in _SUPERVISOR_META_TOOLS]
    return response, tool_outputs, tools_called


async def _with_retry(coro_fn, *args, label: str = "") -> any:
    for attempt in range(_MAX_RETRIES):
        try:
            return await coro_fn(*args)
        except Exception as e:
            if type(e).__name__ not in _RETRY_EXCEPTIONS or attempt == _MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"[retry:{label}] {type(e).__name__}, wait {wait}s ({attempt + 1}/{_MAX_RETRIES})")
            await asyncio.sleep(wait)



def _make_target(supervisor, agents: dict[str, any], model_name: str):
    """
    agents = {
        "analyst_agent":        analyst_agent_instance,
        "finance_agent":        finance_agent_instance,
        "recommendation_agent": recommendation_agent_instance,
    }
    """

    def target(inputs: dict) -> dict:
        question = inputs["question"]
        print(f"[eval:{model_name}] {question[:70]}...")

        async def _invoke() -> dict:
            # 1. Chạy supervisor → routing + response + tool_outputs
            sup_result = await _with_retry(
                supervisor.ainvoke,
                {"messages": [HumanMessage(content=question)]},
                {"configurable": {"thread_id": f"e2e_{abs(hash(question))}"}},
                label=f"supervisor/{model_name}",
            )
            response, tool_outputs, tools_called = _extract_supervisor_outputs(
                sup_result.get("messages", [])
            )

            # 2. Chạy sub-agent trực tiếp → tool sequence bên trong
            tool_sequence: list[str] = []
            called_agent = None
            for agent_key in ["analyst_agent", "finance_agent", "recommendation_agent"]:
                if agent_key in tools_called:
                    called_agent = agent_key
                    break

            if called_agent and called_agent in agents:
                ag = agents[called_agent]
                ag_result = await _with_retry(
                    ag.ainvoke,
                    {"messages": [HumanMessage(content=question)]},
                    label=f"{called_agent}/{model_name}",
                )
                tool_sequence = _extract_tool_sequence(ag_result.get("messages", []))

            return {
                "response": response,
                "tool_outputs": tool_outputs,
                "tools_called": tools_called,
                "tool_sequence": tool_sequence,
            }

        return asyncio.run(_invoke())

    return target


_AGENT_LABELS = {
    "analyst_agent":        "Analyst Agent       ",
    "finance_agent":        "Finance Agent       ",
    "recommendation_agent": "Recommendation Agent",
    "multi":                "Multi-agent         ",
}


def _collect_results(results_iter) -> tuple[dict, dict]:
    by_bucket: dict = {}
    for agent_key in _AGENT_LABELS:
        diffs = ["multi"] if agent_key == "multi" else ["easy", "medium", "hard"]
        by_bucket[agent_key] = {d: {"workflow": [], "quality": {m: [] for m in QUALITY_KEYS}} for d in diffs}

    overall: dict = {"workflow": [], "quality": {m: [] for m in QUALITY_KEYS}}

    for r in list(results_iter):
        example = getattr(r, "example", None)
        ex_out = getattr(example, "outputs", {}) if example else {}
        expected_agent = ex_out.get("expected_agent", "analyst_agent")
        difficulty = ex_out.get("difficulty", "easy")

        agent_key = "multi" if isinstance(expected_agent, list) else expected_agent
        diff_key = "multi" if agent_key == "multi" else difficulty

        feedbacks = getattr(getattr(r, "evaluation_results", None), "results", [])
        for fb in feedbacks:
            key = getattr(fb, "key", None)
            score = getattr(fb, "score", None)
            if score is None:
                continue
            score_f = float(score)
            bucket = by_bucket.get(agent_key, {}).get(diff_key)
            if bucket is None:
                continue
            if key == "workflow_accuracy":
                overall["workflow"].append(score_f)
                bucket["workflow"].append(score_f)
            elif key in QUALITY_KEYS:
                overall["quality"][key].append(score_f)
                bucket["quality"][key].append(score_f)

    return by_bucket, overall


def _avg(lst: list) -> float | None:
    return sum(lst) / len(lst) if lst else None


def _fmt_pct(lst: list) -> str:
    v = _avg(lst)
    return f"{v * 100:.0f}%" if v is not None else "—"


def _fmt5(lst: list) -> str:
    v = _avg(lst)
    return f"{v * 5:.2f}" if v is not None else "—"


def _print_report(model_name: str, by_bucket: dict, overall: dict) -> None:
    W = 78
    print("\n" + "=" * W)
    print(f"KET QUA END-TO-END — {model_name}")
    print("=" * W)
    print(f"{'':32} {'Workflow':>9}  {'Ground':>7} {'Relev':>7} {'Compl':>7} {'Clarity':>7} {'QAvg':>7}")
    print("-" * W)

    def _row(label: str, bucket: dict):
        wf = _fmt_pct(bucket["workflow"])
        q = bucket["quality"]
        vals = [_fmt5(q.get(m, [])) for m in QUALITY_KEYS]
        avgs = [_avg(q.get(m, [])) for m in QUALITY_KEYS if _avg(q.get(m, [])) is not None]
        qavg = f"{sum(avgs) / len(avgs) * 5:.2f}" if avgs else "—"
        print(f"  {label:<30} {wf:>9}  " + "  ".join(f"{v:>7}" for v in vals) + f"  {qavg:>7}")

    for agent_key, label in _AGENT_LABELS.items():
        if agent_key == "multi":
            b = by_bucket["multi"].get("multi", {"workflow": [], "quality": {m: [] for m in QUALITY_KEYS}})
            _row(label, b)
            print()
            continue

        merged = {"workflow": [], "quality": {m: [] for m in QUALITY_KEYS}}
        for diff in ["easy", "medium", "hard"]:
            b = by_bucket[agent_key].get(diff, {"workflow": [], "quality": {m: [] for m in QUALITY_KEYS}})
            if b["workflow"] or any(b["quality"][m] for m in QUALITY_KEYS):
                _row(f"  {label} / {diff.capitalize():<6}", b)
            merged["workflow"].extend(b["workflow"])
            for m in QUALITY_KEYS:
                merged["quality"][m].extend(b["quality"][m])
        _row(f"  {label} TOTAL", merged)
        print()

    print("-" * W)
    _row("TONG", {"workflow": overall["workflow"], "quality": overall["quality"]})
    print()
    print("  Workflow: routing đúng AND tool sequence đúng (0/1, multi-agent: routing only)")
    print("  Quality : thang 1-5 | QAvg = trung binh 4 chi so")


def _build_compare_url(first_url, ids: list[str]):
    if not first_url or not ids:
        return None
    parsed = urlparse(first_url)
    q = parse_qs(parsed.query)
    q["selectedSessions"] = [",".join(ids)]
    return urlunparse(parsed._replace(query=urlencode(q, doseq=True)))


def run_model_eval(client: Client, model_name: str) -> dict:
    print(f"\n[startup] E2E eval model={model_name} ({len(EXAMPLES)} cases)...")
    supervisor = build_supervisor(model=model_name, checkpointer=MemorySaver())
    agents = {
        "analyst_agent":        create_analyst_agent(model=model_name),
        "finance_agent":        create_finance_agent(model=model_name),
        "recommendation_agent": create_Recommendation_agent(model=model_name),
    }
    target = _make_target(supervisor, agents, model_name)

    results_iter = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=ALL_EVALUATORS,
        experiment_prefix=f"e2e_{model_name}",
        metadata={"model": model_name, "eval_type": "end_to_end"},
        max_concurrency=1,
        client=client,
    )

    experiment_id = str(results_iter.experiment_id)
    comparison_url = results_iter.comparison_url
    by_bucket, overall = _collect_results(results_iter)
    _print_report(model_name, by_bucket, overall)

    wf_avg = _avg(overall["workflow"]) or 0.0
    q_avg = _avg([s for lst in overall["quality"].values() for s in lst]) or 0.0
    return {
        "model": model_name,
        "experiment_id": experiment_id,
        "comparison_url": comparison_url,
        "workflow_accuracy": wf_avg,
        "quality_avg": q_avg * 5,
        "by_metric": {m: (_avg(overall["quality"][m]) or 0.0) * 5 for m in QUALITY_KEYS},
    }


def main():
    models = get_eval_models()
    print(f"[startup] Models: {', '.join(models)}")

    client = Client()
    project_name = configure_langsmith_project(client)
    print(f"[startup] LangSmith project: {project_name}")
    upload_dataset(client)

    reports = [run_model_eval(client, m) for m in models]

    combined_url = _build_compare_url(
        reports[0].get("comparison_url") if reports else None,
        [r["experiment_id"] for r in reports if r.get("experiment_id")],
    )

    W = 78
    print("\n" + "=" * W)
    print("TONG HOP TAT CA MODELS")
    print("=" * W)
    print(f"{'Model':<16} {'Workflow':>10} {'Ground':>8} {'Relev':>8} {'Compl':>8} {'Clarity':>8} {'QAvg':>8}")
    print("-" * W)
    for r in reports:
        vals = [r["by_metric"].get(m, 0) for m in QUALITY_KEYS]
        print(
            f"  {r['model']:<14} {r['workflow_accuracy'] * 100:>9.1f}%"
            + "".join(f"{v:8.2f}" for v in vals)
            + f"{r['quality_avg']:8.2f}"
        )

    if combined_url:
        print(f"\nSo sanh: {combined_url}")
    print("LangSmith: https://smith.langchain.com")


if __name__ == "__main__":
    main()
