"""Agent evaluation: 30 questions × 6 dimensions.

评测维度:
  1. Intent Accuracy          意图识别准确率
  2. Tool Selection Accuracy  工具选择准确率
  3. Argument Accuracy         参数准确率
  4. Execution Success Rate    执行成功率
  5. Confirmation Accuracy     确认准确率(写操作是否正确触发 HITL)
  6. Response Quality          回复质量

设计说明:
  - 使用真实 LLM(openai 路径,经 OpenAIProvider 适配 Pydantic AI 1.39.0)
    驱动 Agent 推理,真实测量意图识别 / 工具选择 / 参数生成。
  - 数据层使用内存假仓储 + 固定 fixture(8 月基线 + 9 月含异常),
    保证数据确定性、不依赖 Supabase,可离线复现。
  - 自定义 runner:首轮捕获是否挂起(写操作应返回 DeferredToolRequests),
    随后 auto-approve 续跑拿到最终文本。
  - expected_tools 为「可接受工具集合」,容忍 LLM 合理变体;
    expected_args 为「可接受值列表」,做子集 + 模糊匹配。

Run: uv run python tests/evaluate_agents.py
     uv run python tests/evaluate_agents.py --no-mlflow   # 跳过 MLflow 记录
"""
import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Set

# Silence httpx INFO logs (they spam stderr and break PowerShell error detection)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load .env first (real key), then fall back to a placeholder so the
# Agent import (which initializes the OpenAI provider object) succeeds
# even offline. The real key is checked at run time in run_evaluation().
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "eval-dummy-key")
_PLACEHOLDER_KEY = "eval-dummy-key"

from pydantic_ai import DeferredToolRequests
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart

from agents.finance import finance_agent
from core.dependencies import FinanceDependencies
from core.settings import settings
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType, TransactionCategory
from finance.models.budget import Budget
from finance.utils.hitl import auto_approve_all, MAX_APPROVAL_ROUNDS


# ---------------------------------------------------------------------------
# In-memory fake repositories (no Supabase dependency)
# ---------------------------------------------------------------------------

class FakeExpenseRepository:
    def __init__(self, transactions=None):
        self.transactions = list(transactions or [])

    def add(self, transaction):
        self.transactions.append(transaction)
        return transaction

    def list_all(self):
        return sorted(self.transactions, key=lambda t: t.date, reverse=True)

    def list_by_type(self, transaction_type):
        if transaction_type != TransactionType.EXPENSE:
            return []
        return self.list_all()

    def list_by_category(self, category):
        return [t for t in self.list_all() if t.category == category]

    def list_by_date_range(self, start_date=None, end_date=None):
        result = self.list_all()
        if start_date:
            result = [t for t in result if t.date >= start_date]
        if end_date:
            result = [t for t in result if t.date <= end_date]
        return result

    def total_amount(self, transaction_type=None):
        return sum(t.amount for t in self.transactions)


class FakeIncomeRepository(FakeExpenseRepository):
    def list_by_type(self, transaction_type):
        if transaction_type != TransactionType.INCOME:
            return []
        return self.list_all()

    def list_by_category(self, category):
        if category != TransactionCategory.INCOME:
            return []
        return self.list_all()


class FakeBudgetRepository:
    def __init__(self):
        self.budgets = {}

    def get_for_period(self, period):
        return self.budgets.get(period)

    def upsert(self, budget):
        self.budgets[budget.period] = budget
        return budget

    def list_all(self):
        return list(self.budgets.values())


def _make_tx(amount, category, description, dt, tx_type=TransactionType.EXPENSE):
    return Transaction(
        amount=amount,
        category=TransactionCategory(category),
        description=description,
        date=dt,
        type=TransactionType(tx_type)
    )


def build_fixture():
    """August baseline + September with a food spike. Mirrors test_tools_v1."""
    expenses = []
    income = []

    # August: 12 food (25-35), 2 shopping (100)
    for i, amount in enumerate([25, 35] * 6):
        day = (i % 27) + 1
        expenses.append(_make_tx(
            float(amount), "food", f"8月餐饮{i+1}", datetime(2026, 8, day, 12, 0)
        ))
    expenses.append(_make_tx(100, "shopping", "8月购物1", datetime(2026, 8, 5)))
    expenses.append(_make_tx(100, "shopping", "8月购物2", datetime(2026, 8, 20)))

    # September: 3 normal food + 1 spike (500); 2 shopping (100)
    for i, day in enumerate([2, 3, 4]):
        expenses.append(_make_tx(
            [30, 28, 32][i], "food", f"9月餐饮{i+1}", datetime(2026, 9, day, 12, 0)
        ))
    expenses.append(_make_tx(500, "food", "9月异常餐饮", datetime(2026, 9, 10, 20, 0)))
    expenses.append(_make_tx(100, "shopping", "9月购物1", datetime(2026, 9, 8)))
    expenses.append(_make_tx(60, "transport", "9月打车", datetime(2026, 9, 6)))
    expenses.append(_make_tx(120, "entertainment", "9月电影", datetime(2026, 9, 14)))

    # Income both months
    income.append(_make_tx(2000, "income", "8月工资", datetime(2026, 8, 1), TransactionType.INCOME))
    income.append(_make_tx(2000, "income", "9月工资", datetime(2026, 9, 1), TransactionType.INCOME))

    return expenses, income


def build_deps():
    """Build in-memory deps with a budget so budget/anomaly/proactive tools fire."""
    expenses, income = build_fixture()
    budget_repo = FakeBudgetRepository()
    budget_repo.upsert(Budget(
        period="2026-09",
        monthly_income=2000.0,
        allocations={"food": 100.0, "shopping": 250.0}
    ))
    return FinanceDependencies(
        expense_repo=FakeExpenseRepository(expenses),
        income_repo=FakeIncomeRepository(income),
        budget_repo=budget_repo
    )


# ---------------------------------------------------------------------------
# Tool → Intent mapping (mirrors persona intent buckets)
# ---------------------------------------------------------------------------

TOOL_TO_INTENT: Dict[str, str] = {
    "add_expense": "记支出",
    "add_income": "记收入",
    "query_transactions": "查询流水",
    "view_history": "查询流水",
    "analyze_spending": "消费分析",
    "compare_period": "消费对比",
    "create_budget": "创建预算",
    "get_budget_plan": "创建预算",
    "detect_anomaly": "异常检测",
    "generate_insight": "财务洞察",
    "get_proactive_insights": "主动提醒",
    "get_financial_advice": "闲聊",
}

ERROR_MARKERS = ("❌", "访问你的账本时遇到技术问题", "执行失败", "Traceback")


# ---------------------------------------------------------------------------
# 30 evaluation cases
# ---------------------------------------------------------------------------

EVAL_CASES: List[Dict[str, Any]] = [
    # === 记支出 (add_expense) — write, HITL ===
    {"id": "E01", "input": "刚午饭花了 35 元",
     "intent": "记支出", "expected_tools": {"add_expense"},
     "expected_args": {"amount": 35.0, "category": ["food", "餐饮", "lunch", "午饭"]},
     "expected_hitl": True, "expected_keywords": ["35"], "allow_no_tool": False},
    {"id": "E02", "input": "打车 28 块",
     "intent": "记支出", "expected_tools": {"add_expense"},
     "expected_args": {"amount": 28.0, "category": ["transport", "交通", "打车", "taxi"]},
     "expected_hitl": True, "expected_keywords": ["28"], "allow_no_tool": False},
    {"id": "E03", "input": "买了件 299 的衣服",
     "intent": "记支出", "expected_tools": {"add_expense"},
     "expected_args": {"amount": 299.0, "category": ["shopping", "购物", "衣服", "clothing"]},
     "expected_hitl": True, "expected_keywords": ["299"], "allow_no_tool": False},
    {"id": "E04", "input": "充了 100 话费",
     "intent": "记支出", "expected_tools": {"add_expense"},
     "expected_args": {"amount": 100.0},
     "expected_hitl": True, "expected_keywords": ["100"], "allow_no_tool": False},
    {"id": "E05", "input": "看电影花了 80",
     "intent": "记支出", "expected_tools": {"add_expense"},
     "expected_args": {"amount": 80.0, "category": ["entertainment", "娱乐", "电影", "movie"]},
     "expected_hitl": True, "expected_keywords": ["80"], "allow_no_tool": False},

    # === 记收入 (add_income) — write, HITL ===
    {"id": "E06", "input": "工资到账 8000",
     "intent": "记收入", "expected_tools": {"add_income"},
     "expected_args": {"amount": 8000.0, "source": ["salary", "工资", "wage", "薪"]},
     "expected_hitl": True, "expected_keywords": ["8,000", "8000"], "allow_no_tool": False},
    {"id": "E07", "input": "接了个私活 2000 块",
     "intent": "记收入", "expected_tools": {"add_income"},
     "expected_args": {"amount": 2000.0},
     "expected_hitl": True, "expected_keywords": ["2,000", "2000"], "allow_no_tool": False},
    {"id": "E08", "input": "收到 200 红包",
     "intent": "记收入", "expected_tools": {"add_income"},
     "expected_args": {"amount": 200.0},
     "expected_hitl": True, "expected_keywords": ["200"], "allow_no_tool": False},

    # === 查询流水 (query_transactions) — read ===
    {"id": "E09", "input": "看看本月账单",
     "intent": "查询流水",
     "expected_tools": {"query_transactions", "view_history"},
     "expected_args": {"period": ["this_month", "本月", "2026-09"]},
     "expected_hitl": False, "expected_keywords": ["交易", "账单", "笔"], "allow_no_tool": False},
    {"id": "E10", "input": "上月餐饮花了多少",
     "intent": "查询流水",
     "expected_tools": {"query_transactions", "view_history", "analyze_spending"},
     "expected_args": {"period": ["last_month", "上月", "2026-08"]},
     "expected_hitl": False, "expected_keywords": ["餐饮"], "allow_no_tool": False},
    {"id": "E11", "input": "近30天的交通支出",
     "intent": "查询流水",
     "expected_tools": {"query_transactions", "view_history"},
     "expected_args": {"period": ["last_30d", "近30天", "30"]},
     "expected_hitl": False, "expected_keywords": ["交通"], "allow_no_tool": False},
    {"id": "E12", "input": "8月有哪些收入",
     "intent": "查询流水",
     "expected_tools": {"query_transactions", "view_history"},
     "expected_args": {"period": ["2026-08", "8月", "last_month"]},
     "expected_hitl": False, "expected_keywords": ["收入"], "allow_no_tool": False},

    # === 消费分析 (analyze_spending) — read ===
    {"id": "E13", "input": "这个月消费分析",
     "intent": "消费分析", "expected_tools": {"analyze_spending"},
     "expected_args": {"period": ["this_month", "本月", "2026-09"]},
     "expected_hitl": False, "expected_keywords": ["消费分析"], "allow_no_tool": False},
    {"id": "E14", "input": "上月消费情况怎么样",
     "intent": "消费分析", "expected_tools": {"analyze_spending"},
     "expected_args": {"period": ["last_month", "上月", "2026-08"]},
     "expected_hitl": False, "expected_keywords": ["消费分析"], "allow_no_tool": False},

    # === 消费对比 (compare_period) — read ===
    {"id": "E15", "input": "本月和上月消费对比",
     "intent": "消费对比", "expected_tools": {"compare_period"},
     "expected_args": {"period": ["this_month", "本月", "2026-09"]},
     "expected_hitl": False, "expected_keywords": ["对比"], "allow_no_tool": False},
    {"id": "E16", "input": "9月对比8月",
     "intent": "消费对比", "expected_tools": {"compare_period"},
     "expected_args": {"period": ["2026-09", "9月", "this_month"]},
     "expected_hitl": False, "expected_keywords": ["对比"], "allow_no_tool": False},

    # === 异常检测 (detect_anomaly) — read ===
    {"id": "E17", "input": "本月有异常消费吗",
     "intent": "异常检测", "expected_tools": {"detect_anomaly", "generate_insight"},
     "expected_args": {"period": ["this_month", "本月", "2026-09"]},
     "expected_hitl": False, "expected_keywords": ["异常"], "allow_no_tool": False},
    {"id": "E18", "input": "9月有没有大额支出",
     "intent": "异常检测", "expected_tools": {"detect_anomaly", "generate_insight"},
     "expected_args": {"period": ["2026-09", "9月", "this_month"]},
     "expected_hitl": False, "expected_keywords": ["异常", "大额"], "allow_no_tool": False},

    # === 财务洞察 (generate_insight) — read ===
    {"id": "E19", "input": "给我一份财务洞察",
     "intent": "财务洞察", "expected_tools": {"generate_insight"},
     "expected_args": {},
     "expected_hitl": False, "expected_keywords": ["洞察"], "allow_no_tool": False},
    {"id": "E20", "input": "本月财务健康怎么样",
     "intent": "财务洞察",
     "expected_tools": {"generate_insight", "analyze_spending"},
     "expected_args": {},
     "expected_hitl": False, "expected_keywords": [], "allow_no_tool": False},

    # === 主动提醒 (get_proactive_insights) — read ===
    {"id": "E21", "input": "有什么要提醒我的吗",
     "intent": "主动提醒", "expected_tools": {"get_proactive_insights"},
     "expected_args": {},
     "expected_hitl": False, "expected_keywords": ["提醒"], "allow_no_tool": False},
    {"id": "E22", "input": "帮我看看首页的提醒",
     "intent": "主动提醒", "expected_tools": {"get_proactive_insights"},
     "expected_args": {},
     "expected_hitl": False, "expected_keywords": ["提醒"], "allow_no_tool": False},

    # === 创建预算 (create_budget) — write, HITL ===
    {"id": "E23", "input": "帮我做个月收入8000的预算",
     "intent": "创建预算", "expected_tools": {"create_budget"},
     "expected_args": {"monthly_income": 8000.0},
     "expected_hitl": True, "expected_keywords": ["预算"], "allow_no_tool": False},
    {"id": "E24", "input": "创建10月预算，月收入5000",
     "intent": "创建预算", "expected_tools": {"create_budget"},
     "expected_args": {"monthly_income": 5000.0, "period": ["2026-10", "10月"]},
     "expected_hitl": True, "expected_keywords": ["预算"], "allow_no_tool": False},

    # === 信息缺失澄清 — no tool, ask clarifying question ===
    {"id": "E25", "input": "记一笔支出",
     "intent": "澄清", "expected_tools": set(),
     "expected_args": {},
     "expected_hitl": False,
     "expected_keywords": ["金额", "多少", "类别", "什么"], "allow_no_tool": True},
    {"id": "E26", "input": "我花了点钱",
     "intent": "澄清", "expected_tools": set(),
     "expected_args": {},
     "expected_hitl": False,
     "expected_keywords": ["多少", "金额", "什么", "类别"], "allow_no_tool": True},

    # === 闲聊 / 其他 ===
    {"id": "E27", "input": "你是谁",
     "intent": "闲聊", "expected_tools": set(),
     "expected_args": {},
     "expected_hitl": False,
     "expected_keywords": ["财务", "管家"], "allow_no_tool": True},
    {"id": "E28", "input": "怎么省钱",
     "intent": "闲聊",
     "expected_tools": {"get_financial_advice", "generate_insight", "get_proactive_insights"},
     "expected_args": {},
     "expected_hitl": False, "expected_keywords": [], "allow_no_tool": True},

    # === 多意图 / 多工具 ===
    {"id": "E29", "input": "这个月餐饮花了多少，比上月多吗",
     "intent": "消费对比",
     "expected_tools": {"compare_period", "query_transactions", "analyze_spending", "view_history"},
     "expected_args": {},
     "expected_hitl": False, "expected_keywords": ["餐饮", "对比"], "allow_no_tool": False},
    {"id": "E30", "input": "记一笔 50 餐饮，然后看看本月消费分析",
     "intent": "记支出",
     "expected_tools": {"add_expense", "analyze_spending"},
     "expected_args": {"amount": 50.0, "category": ["food", "餐饮"]},
     "expected_hitl": True, "expected_keywords": ["消费分析"], "allow_no_tool": False},
]


# ---------------------------------------------------------------------------
# Helpers: extract tool calls, lenient arg matching, scoring
# ---------------------------------------------------------------------------

def _coerce_args(raw: Any) -> Dict[str, Any]:
    """ToolCallPart.args may be a dict, a JSON string, or None.
    Normalize to a plain dict so scoring never crashes on real-model output."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        return dict(raw)
    except (ValueError, TypeError):
        pass
    if isinstance(raw, str):
        import json
        try:
            decoded = json.loads(raw)
            return decoded if isinstance(decoded, dict) else {"_raw": raw}
        except (json.JSONDecodeError, ValueError):
            return {"_raw": raw}
    return {"_raw": str(raw)}


def extract_tool_calls(messages) -> List[Dict[str, Any]]:
    """Pull every ToolCallPart from the message history."""
    calls = []
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    calls.append({"tool": part.tool_name, "args": _coerce_args(part.args)})
    return calls


def args_match(actual: Any, expected: Any) -> bool:
    """Lenient match: expected may be a single value or a list of acceptable values."""
    if isinstance(expected, list):
        return any(args_match(actual, e) for e in expected)
    if isinstance(expected, bool):
        return actual == expected
    if isinstance(expected, (int, float)):
        try:
            return abs(float(actual) - float(expected)) < 0.01
        except (ValueError, TypeError):
            return False
    a = str(actual).lower().strip()
    e = str(expected).lower().strip()
    return e == a or e in a or a in e


def score_intent(case: Dict, tool_calls: List[Dict]) -> bool:
    """Intent = 1 if the captured tool(s) map to the expected intent bucket,
    OR (intent is chitchat/clarify) and no tool was called."""
    if not tool_calls:
        return case["intent"] in ("闲聊", "澄清")
    actual_intents = {TOOL_TO_INTENT.get(tc["tool"], "unknown") for tc in tool_calls}
    return case["intent"] in actual_intents


def score_tool_selection(case: Dict, tool_calls: List[Dict]) -> bool:
    """Tool = 1 if every called tool is in the acceptable set,
    OR no tool was called and allow_no_tool is True."""
    actual: Set[str] = {tc["tool"] for tc in tool_calls}
    expected: Set[str] = set(case["expected_tools"])
    if not actual:
        return bool(case.get("allow_no_tool", False))
    return actual.issubset(expected)


def score_argument(case: Dict, tool_calls: List[Dict]) -> bool:
    """Args = 1 if every expected key appears in some captured call with a matching value."""
    expected_args: Dict = case.get("expected_args", {}) or {}
    if not expected_args:
        return True
    for key, expected_val in expected_args.items():
        found = False
        for tc in tool_calls:
            if key in tc["args"] and args_match(tc["args"][key], expected_val):
                found = True
                break
        if not found:
            return False
    return True


def score_execution(final_output: str) -> bool:
    """Execution = 1 if final output is a non-empty string with no error markers."""
    if not isinstance(final_output, str) or not final_output.strip():
        return False
    return not any(marker in final_output for marker in ERROR_MARKERS)


def score_confirmation(case: Dict, first_output: Any) -> bool:
    """Confirmation = 1 if the first-run output type matches expected HITL behavior."""
    if case["expected_hitl"]:
        return isinstance(first_output, DeferredToolRequests)
    return isinstance(first_output, str)


def score_response(case: Dict, final_output: str) -> bool:
    """Response = 1 if all expected keywords appear in the final output (case-insensitive)."""
    keywords = case.get("expected_keywords", []) or []
    if not keywords:
        return True
    text = (final_output or "").lower()
    return all(kw.lower() in text for kw in keywords)


# ---------------------------------------------------------------------------
# Runner: first run captures HITL suspension, then auto-approve to finish
# ---------------------------------------------------------------------------

async def evaluate_one(agent, case: Dict, deps, model) -> Dict[str, Any]:
    """Run one eval case, return per-dimension scores + captured artifacts."""
    record: Dict[str, Any] = {
        "id": case["id"], "input": case["input"], "intent": case["intent"],
        "intent_pass": False, "tool_pass": False, "arg_pass": False,
        "exec_pass": False, "confirm_pass": False, "resp_pass": False,
        "first_output_type": "", "actual_tools": [], "final_output": "",
        "error": None,
    }

    try:
        result = await agent.run(case["input"], deps=deps, model=model)
    except Exception as e:
        record["error"] = f"first-run: {e}"
        return record

    first_output = result.output
    record["first_output_type"] = type(first_output).__name__

    # Auto-approve loop: resume until the agent returns a final string
    rounds = 0
    while isinstance(result.output, DeferredToolRequests):
        rounds += 1
        if rounds > MAX_APPROVAL_ROUNDS:
            record["error"] = f"exceeded {MAX_APPROVAL_ROUNDS} approval rounds"
            break
        approval_results = auto_approve_all(result.output)
        try:
            result = await agent.run(
                None, deps=deps, model=model,
                message_history=result.all_messages(),
                deferred_tool_results=approval_results
            )
        except Exception as e:
            record["error"] = f"resume-run: {e}"
            break

    final_output = result.output if isinstance(result.output, str) else ""
    tool_calls = extract_tool_calls(result.all_messages())

    record["actual_tools"] = sorted({tc["tool"] for tc in tool_calls})
    record["final_output"] = final_output[:200]
    record["intent_pass"] = score_intent(case, tool_calls)
    record["tool_pass"] = score_tool_selection(case, tool_calls)
    record["arg_pass"] = score_argument(case, tool_calls)
    record["exec_pass"] = score_execution(final_output)
    record["confirm_pass"] = score_confirmation(case, first_output)
    record["resp_pass"] = score_response(case, final_output)
    return record


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

DIMENSIONS = [
    ("Intent Accuracy", "intent_pass"),
    ("Tool Selection", "tool_pass"),
    ("Argument Accuracy", "arg_pass"),
    ("Execution Success", "exec_pass"),
    ("Confirmation", "confirm_pass"),
    ("Response Quality", "resp_pass"),
]


def render_report(records: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append("=" * 92)
    lines.append("AI 财务管家 Agent · 评测报告")
    lines.append("=" * 92)
    lines.append(f"问题数: {len(records)}　|　维度: 6　|　数据: 内存 fixture(8月基线+9月含异常)")
    lines.append("模型: openai 路径(OpenAIProvider)　|　HITL: 首轮捕获挂起,后续 auto-approve")
    lines.append("-" * 92)

    # Per-case table
    header = f"{'ID':<5}{'Intent':<8}{'Tool':<8}{'Arg':<8}{'Exec':<8}{'Cnfm':<8}{'Resp':<8}{'Tools':<28}{'Input'}"
    lines.append(header)
    lines.append("-" * 92)
    for r in records:
        def mark(passed): return "✓" if passed else "✗"
        tools_str = ",".join(r["actual_tools"]) or "(none)"
        if len(tools_str) > 26:
            tools_str = tools_str[:24] + ".."
        input_str = r["input"]
        if len(input_str) > 30:
            input_str = input_str[:28] + ".."
        lines.append(
            f"{r['id']:<5}{mark(r['intent_pass']):<8}{mark(r['tool_pass']):<8}"
            f"{mark(r['arg_pass']):<8}{mark(r['exec_pass']):<8}"
            f"{mark(r['confirm_pass']):<8}{mark(r['resp_pass']):<8}"
            f"{tools_str:<28}{input_str}"
        )
        if r.get("error"):
            lines.append(f"     └ error: {r['error']}")

    # Summary
    lines.append("=" * 92)
    lines.append("维度汇总")
    lines.append("-" * 92)
    n = len(records)
    for label, key in DIMENSIONS:
        passed = sum(1 for r in records if r[key])
        pct = 100.0 * passed / n if n else 0.0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"{label:<22}{passed:>3}/{n:<3} {pct:5.1f}%  {bar}")

    overall = sum(1 for r in records for _, k in DIMENSIONS if r[k])
    total = n * len(DIMENSIONS)
    lines.append("-" * 92)
    lines.append(f"{'Overall':<22}{overall:>3}/{total:<3} {100.0*overall/total:5.1f}%")
    lines.append("=" * 92)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_evaluation(use_mlflow: bool = True):
    print("AI 财务管家 Agent · 评测启动")
    print(f"问题数: {len(EVAL_CASES)}　|　维度: 6")

    # Model: force openai path (avoids gemini incompatibility)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == _PLACEHOLDER_KEY:
        print("⚠ OPENAI_API_KEY 未设置(或仅为导入占位),无法进行真实 LLM 评测。")
        print("  请在 .env 或环境变量中设置真实 OPENAI_API_KEY 后重试。")
        print("  离线工具层测试可用:uv run python tests/test_tools_v1.py")
        return
    model = settings.get_model("openai")
    print(f"模型: openai 路径(OpenAIProvider) → {settings.OPENAI_MODEL}")

    deps = build_deps()
    print(f"数据: 内存 fixture(expense={len(deps.expense_repo.transactions)},"
          f" income={len(deps.income_repo.transactions)},"
          f" budget={'yes' if deps.budget_repo else 'no'})")
    print("-" * 60)

    records = []
    for i, case in enumerate(EVAL_CASES, 1):
        print(f"[{i:>2}/{len(EVAL_CASES)}] {case['id']} {case['input'][:40]}")
        record = await evaluate_one(finance_agent, case, deps, model)
        records.append(record)
        status = "✓" if all(record[k] for _, k in DIMENSIONS) else "✗"
        print(f"        → {status} tools={record['actual_tools']} "
              f"first={record['first_output_type']}")

    # Print report
    report = render_report(records)
    print()
    print(report)

    # MLflow logging (best-effort)
    if use_mlflow:
        try:
            import mlflow
            import pandas as pd
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
            with mlflow.start_run(run_name="agent_eval_30q_6dim") as run:
                df = pd.DataFrame(records)
                mlflow.log_table(df, "evaluation_results.json")
                for label, key in DIMENSIONS:
                    passed = sum(1 for r in records if r[key])
                    mlflow.log_metric(label.replace(" ", "_").lower(),
                                      passed / len(records))
                overall = sum(1 for r in records for _, k in DIMENSIONS if r[k])
                mlflow.log_metric("overall_accuracy",
                                  overall / (len(records) * len(DIMENSIONS)))
                with open("eval_report.txt", "w", encoding="utf-8") as f:
                    f.write(report)
                mlflow.log_artifact("eval_report.txt")
                print(f"\nMLflow 已记录: {mlflow.get_tracking_uri()}")
                print(f"  run_id={run.info.run_id}")
        except Exception as e:
            print(f"\n⚠ MLflow 记录跳过: {e}")
            # Still write local report
            try:
                with open("eval_report.txt", "w", encoding="utf-8") as f:
                    f.write(report)
                print(f"  本地报告已写入: eval_report.txt")
            except Exception:
                pass


if __name__ == "__main__":
    use_mlflow = "--no-mlflow" not in sys.argv
    asyncio.run(run_evaluation(use_mlflow=use_mlflow))
