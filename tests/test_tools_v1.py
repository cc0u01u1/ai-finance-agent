"""V1 new-tool logic tests.

Uses in-memory fake repositories: no network, no LLM calls.
Run: uv run python tests/test_tools_v1.py
"""
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType, TransactionCategory
from finance.models.budget import Budget
from core.dependencies import FinanceDependencies
from finance.services.analytics import AnalyticsService
from finance.services.anomaly import AnomalyService
from finance.services.budgets import BudgetService
from finance.services.insights import InsightService
from finance.utils.periods import resolve_period, previous_period
from pydantic_ai import DeferredToolRequests, ToolApproved, ToolDenied
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart
from finance.utils.hitl import (
    describe_tool_call,
    build_approval_results,
    format_pending_notification,
    run_with_auto_approval,
)
from prompts.persona import FINANCIAL_PERSONA


# ---------------------------------------------------------------------------
# Fakes
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

    def clear(self):
        self.transactions = []


class FakeIncomeRepository(FakeExpenseRepository):
    def add(self, transaction):
        self.transactions.append(transaction)
        return transaction

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


def make_tx(amount, category, description, dt, tx_type=TransactionType.EXPENSE):
    return Transaction(
        amount=amount,
        category=TransactionCategory(category),
        description=description,
        date=dt,
        type=TransactionType(tx_type)
    )


# ---------------------------------------------------------------------------
# Fixture data: August baseline + September current period with a spike
# ---------------------------------------------------------------------------

def build_fixture():
    expenses = []
    income = []

    # August: 12 food transactions around 25-35, 2 shopping of 100
    for i, amount in enumerate([25, 35] * 6):
        day = (i % 27) + 1
        expenses.append(make_tx(
            float(amount), "food", f"8月餐饮{i+1}",
            datetime(2026, 8, day, 12, 0)
        ))
    expenses.append(make_tx(100, "shopping", "8月购物1", datetime(2026, 8, 5)))
    expenses.append(make_tx(100, "shopping", "8月购物2", datetime(2026, 8, 20)))

    # September: 3 normal food + 1 spike (500); 2 shopping of 100
    for i, day in enumerate([2, 3, 4]):
        expenses.append(make_tx(
            [30, 28, 32][i], "food", f"9月餐饮{i+1}",
            datetime(2026, 9, day, 12, 0)
        ))
    expenses.append(make_tx(500, "food", "9月异常餐饮", datetime(2026, 9, 10, 20, 0)))
    expenses.append(make_tx(100, "shopping", "9月购物1", datetime(2026, 9, 8)))
    expenses.append(make_tx(100, "shopping", "9月购物2", datetime(2026, 9, 18)))

    # Income both months
    income.append(make_tx(
        2000, "income", "8月工资", datetime(2026, 8, 1), TransactionType.INCOME
    ))
    income.append(make_tx(
        2000, "income", "9月工资", datetime(2026, 9, 1), TransactionType.INCOME
    ))

    return expenses, income


failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"PASS: {name}")
    else:
        print(f"FAIL: {name} {detail}")
        failures.append(name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_periods():
    start, end, label = resolve_period("2026-09", now=datetime(2026, 9, 20))
    check("period explicit label", label == "2026-09", label)
    check("period start", start == datetime(2026, 9, 1), str(start))
    check("period end", end == datetime(2026, 10, 1), str(end))

    p_start, p_end, p_label = previous_period(start, end, label)
    check("previous period label", p_label == "2026-08", p_label)
    check("previous period start", p_start == datetime(2026, 8, 1), str(p_start))

    s2, _, l2 = resolve_period("本月", now=datetime(2026, 9, 20))
    check("chinese alias", l2 == "2026-09", l2)


def test_analytics_and_compare():
    expenses, income = build_fixture()
    transactions = expenses + income

    sep = AnalyticsService.summarize(
        transactions, datetime(2026, 9, 1), datetime(2026, 10, 1), "2026-09"
    )
    aug = AnalyticsService.summarize(
        transactions, datetime(2026, 8, 1), datetime(2026, 9, 1), "2026-08"
    )

    check("sep total expense", sep.total_expense == 790.0, str(sep.total_expense))
    check("sep total income", sep.total_income == 2000.0, str(sep.total_income))
    check("sep net", sep.net == 1210.0, str(sep.net))
    check("sep category count", len(sep.categories) == 2, str(len(sep.categories)))

    comparison = AnalyticsService.compare(sep, aug)
    check("compare delta", comparison.delta == 230.0, str(comparison.delta))
    check("compare pct", comparison.change_pct == 41.1, str(comparison.change_pct))
    check("compare food delta", comparison.categories[0].category == "food",
          comparison.categories[0].category)

    text = AnalyticsService.format_summary(sep)
    check("format summary", "消费分析" in text and "¥790.00" in text)
    text2 = AnalyticsService.format_comparison(comparison)
    check("format comparison", "消费对比" in text2 and "+41.1%" in text2)


def test_anomaly():
    expenses, _ = build_fixture()
    current = [t for t in expenses if datetime(2026, 9, 1) <= t.date < datetime(2026, 10, 1)]
    previous = [t for t in expenses if datetime(2026, 8, 1) <= t.date < datetime(2026, 9, 1)]

    anomalies = AnomalyService.detect(current, previous)
    kinds = {a.kind for a in anomalies}
    check("anomaly spike present", "category_spike" in kinds, str(kinds))
    check("anomaly outlier present", "category_outlier" in kinds, str(kinds))

    outlier = next(a for a in anomalies if a.kind == "category_outlier")
    check("anomaly amount", outlier.amount == 500.0, str(outlier.amount))

    text = AnomalyService.format_anomalies(anomalies, "2026-09")
    check("format anomalies", "异常检测" in text)

    none_text = AnomalyService.format_anomalies([], "2026-09")
    check("format no anomalies", "未发现明显异常" in none_text)


def test_budget():
    repo = FakeBudgetRepository()
    budget = BudgetService.create(
        repo=repo,
        period="2026-09",
        monthly_income=2000.0,
        allocations={"food": 100.0, "shopping": 250.0},
        history_expenses=[]
    )
    check("budget saved", repo.get_for_period("2026-09") is budget)
    check("budget total", budget.total_allocated == 350.0, str(budget.total_allocated))

    expenses, _ = build_fixture()
    current = [t for t in expenses if datetime(2026, 9, 1) <= t.date < datetime(2026, 10, 1)]
    status_rows = BudgetService.budget_status(budget, current)
    food_row = next(r for r in status_rows if r["category"] == "food")
    check("budget status food overrun", food_row["spent"] == 590.0 and food_row["usage_pct"] == 5.9,
          str(food_row))

    # Derivation from history
    derived = BudgetService.derive_allocations(expenses, 2000.0)
    check("derived non empty", len(derived) >= 2 and sum(derived.values()) <= 2000.0 * 0.9 + 1,
          str(derived))

    text = BudgetService.format_budget(budget)
    check("format budget", "预算已创建" in text)


def test_insight_pipeline():
    expenses, income = build_fixture()
    deps = FinanceDependencies(
        expense_repo=FakeExpenseRepository(expenses),
        income_repo=FakeIncomeRepository(income),
        budget_repo=FakeBudgetRepository()
    )
    deps.budget_repo.upsert(Budget(
        period="2026-09",
        monthly_income=2000.0,
        allocations={"food": 100.0, "shopping": 250.0}
    ))

    report = InsightService.generate(deps, "2026-09", now=datetime(2026, 9, 20))
    codes = {i.code for i in report.insights}

    expected = {
        "BUDGET_OVERRUN",       # food 590 vs 100
        "BUDGET_NEAR",          # shopping 200 vs 250 = 80%
        "ANOMALY_CATEGORY_OUTLIER",
        "ANOMALY_CATEGORY_SPIKE",
        "SPENDING_SURGE",       # +41%
        "CONCENTRATION"         # food dominates
    }
    missing = expected - codes
    check("insight codes complete", not missing, f"missing={missing}")
    check("insight critical exists", report.critical_count >= 1,
          str(report.critical_count))

    overrun = next(i for i in report.insights if i.code == "BUDGET_OVERRUN")
    check("overrun category", overrun.category == "food", overrun.category)
    check("overrun suggestion present", bool(overrun.suggestion))

    text = InsightService.format_report(report)
    check("format insight", "财务洞察" in text and "预算超支" in text)

    # Stable fallback when no rules fire
    deps2 = FinanceDependencies(
        expense_repo=FakeExpenseRepository([
            make_tx(50, "food", "平稳消费", datetime(2026, 9, 5))
        ]),
        income_repo=FakeIncomeRepository([
            make_tx(2000, "income", "工资", datetime(2026, 9, 1), TransactionType.INCOME)
        ]),
        budget_repo=None
    )
    report2 = InsightService.generate(deps2, "2026-09", now=datetime(2026, 9, 20))
    codes2 = {i.code for i in report2.insights}
    check("fallback or positive insight",
          "ALL_STABLE" in codes2 or "GOOD_SAVINGS" in codes2, str(codes2))


def test_tool_registration():
    # agents.finance declares a hardcoded openai default at import time;
    # a dummy key suffices because no real model call is made.
    os.environ.setdefault("OPENAI_API_KEY", "test-dummy-key")
    from agents.finance import finance_agent

    tool_keys = set(finance_agent._function_toolset.tools.keys())
    expected = {
        "query_transactions",
        "analyze_spending",
        "compare_period",
        "create_budget",
        "detect_anomaly",
        "generate_insight",
    }
    missing = expected - tool_keys
    check("all six tools registered", not missing, f"missing={missing}, keys={tool_keys}")

    # Original tools must remain
    original = {"add_expense", "add_income", "view_history",
                "get_financial_advice", "get_budget_plan"}
    missing_original = original - tool_keys
    check("original tools preserved", not missing_original, str(missing_original))


# ---------------------------------------------------------------------------
# HITL behavior tests
# ---------------------------------------------------------------------------

def _make_approval_model(tool_name, tool_args, final_text):
    """A FunctionModel that first requests a tool call, then returns text."""
    def function(messages, info):
        already_called = any(
            isinstance(m, ModelResponse)
            and any(isinstance(p, ToolCallPart) for p in m.parts)
            for m in messages
        )
        if not already_called:
            return ModelResponse(parts=[
                ToolCallPart(tool_name, tool_args, tool_call_id="call_1")
            ])
        return ModelResponse(parts=[TextPart(final_text)])

    return FunctionModel(function)


async def _hitl_approve_flow():
    from agents.finance import finance_agent

    deps = FinanceDependencies(
        expense_repo=FakeExpenseRepository([]),
        income_repo=FakeIncomeRepository([]),
        budget_repo=None
    )
    args = {"amount": 32.5, "category": "lunch", "description": "外卖"}
    model = _make_approval_model("add_expense", args, "✅ 已记下，餐饮预算还剩340元。")

    # First run: must suspend with an approval request
    result = await finance_agent.run("刚外卖花了32.5", model=model, deps=deps)
    check("hitl first run suspends", isinstance(result.output, DeferredToolRequests),
          str(type(result.output)))

    requests = result.output
    check("hitl one pending call", len(requests.approvals) == 1,
          str(len(requests.approvals)))
    check("hitl pending tool name",
          requests.approvals[0].tool_name == "add_expense")
    check("hitl description text", "32.50" in describe_tool_call(requests.approvals[0]))

    # Approve and resume
    approval_results = build_approval_results(
        requests, {"call_1": ToolApproved()}
    )
    result = await finance_agent.run(
        None,
        model=model,
        deps=deps,
        message_history=result.all_messages(),
        deferred_tool_results=approval_results
    )
    check("hitl approved final output",
          result.output == "✅ 已记下，餐饮预算还剩340元。", str(result.output))
    check("hitl approved data persisted",
          len(deps.expense_repo.transactions) == 1
          and deps.expense_repo.transactions[0].amount == 32.5,
          str(deps.expense_repo.transactions))


async def _hitl_deny_flow():
    from agents.finance import finance_agent

    deps = FinanceDependencies(
        expense_repo=FakeExpenseRepository([]),
        income_repo=FakeIncomeRepository([]),
        budget_repo=None
    )
    args = {"amount": 1999.0, "category": "shopping", "description": "冲动消费"}
    model = _make_approval_model("add_expense", args, "好的，这笔先不记。")

    result = await finance_agent.run("买了个1999的耳机", model=model, deps=deps)
    check("hitl deny first suspends", isinstance(result.output, DeferredToolRequests))

    requests = result.output
    approval_results = build_approval_results(
        requests,
        {"call_1": ToolDenied("用户取消了这笔记录。")}
    )
    result = await finance_agent.run(
        None,
        model=model,
        deps=deps,
        message_history=result.all_messages(),
        deferred_tool_results=approval_results
    )
    check("hitl denied final output", result.output == "好的，这笔先不记。", str(result.output))
    check("hitl denied no data persisted",
          len(deps.expense_repo.transactions) == 0,
          str(deps.expense_repo.transactions))


async def _hitl_readonly_flow():
    from agents.finance import finance_agent

    deps = FinanceDependencies(
        expense_repo=FakeExpenseRepository([
            make_tx(30, "food", "餐饮", datetime(2026, 9, 5))
        ]),
        income_repo=FakeIncomeRepository([]),
        budget_repo=None
    )

    def function(messages, info):
        already_called = any(
            isinstance(m, ModelResponse)
            and any(isinstance(p, ToolCallPart) for p in m.parts)
            for m in messages
        )
        if not already_called:
            return ModelResponse(parts=[
                ToolCallPart("query_transactions",
                             {"period": "this_month", "category": "", "tx_type": ""},
                             tool_call_id="call_ro")
            ])
        return ModelResponse(parts=[TextPart("以上是本月账单")])

    model = FunctionModel(function)
    result = await finance_agent.run("看看本月账单", model=model, deps=deps)
    check("hitl readonly not suspended", isinstance(result.output, str),
          str(type(result.output)))
    # Tool ran and the model produced its final wrap-up text (no suspension)
    check("hitl readonly content", result.output == "以上是本月账单",
          result.output[:80])


async def _hitl_auto_approval_flow():
    from agents.finance import finance_agent

    deps = FinanceDependencies(
        expense_repo=FakeExpenseRepository([]),
        income_repo=FakeIncomeRepository([]),
        budget_repo=None
    )
    args = {"amount": 88.0, "category": "dinner", "description": "聚餐"}
    model = _make_approval_model("add_expense", args, "done")

    result = await run_with_auto_approval(
        finance_agent, "晚饭聚餐88", deps=deps, model=model
    )
    check("auto approval final output", result.output == "done", str(result.output))
    check("auto approval persisted",
          len(deps.expense_repo.transactions) == 1
          and deps.expense_repo.transactions[0].amount == 88.0)


def test_hitl():
    asyncio.run(_hitl_approve_flow())
    asyncio.run(_hitl_deny_flow())
    asyncio.run(_hitl_readonly_flow())
    asyncio.run(_hitl_auto_approval_flow())

    # Sub-agent notification text
    deps = FinanceDependencies(
        expense_repo=FakeExpenseRepository([]),
        income_repo=FakeIncomeRepository([]),
        budget_repo=None
    )
    args = {"amount": 50, "category": "food", "description": ""}

    class _Single:
        async def run(self):
            from agents.finance import finance_agent
            model = _make_approval_model("add_expense", args, "x")
            return await finance_agent.run("test", model=model, deps=deps)

    result = asyncio.run(_Single().run())
    notice = format_pending_notification(result.output)
    check("subagent notification", "需要你确认" in notice and "50.00" in notice,
          notice[:100])


# ---------------------------------------------------------------------------
# Agent Workflow tests
# ---------------------------------------------------------------------------

def test_agent_workflow():
    # 1. Persona must define all six workflow steps
    for keyword in [
        "意图识别（Intent）",
        "规划（Planning）",
        "工具选择（Tool Selection）",
        "工具执行（Tool Execution）",
        "结果（Result）",
        "回复（Response）",
    ]:
        check(f"persona step: {keyword}", keyword in FINANCIAL_PERSONA)

    # 2. Persona must contain the write -> confirm -> execute branch
    check("persona hitl pause", "暂停" in FINANCIAL_PERSONA
          and "等待确认" in FINANCIAL_PERSONA)
    check("persona no write without approval", "严禁未经确认直接写入" in FINANCIAL_PERSONA)

    # 3. Truthfulness discipline
    check("persona truth source", "唯一事实来源" in FINANCIAL_PERSONA)
    check("persona no fabricated numbers", "禁止凭记忆或想象编造数字" in FINANCIAL_PERSONA)

    # 4. Live catalog content
    os.environ.setdefault("OPENAI_API_KEY", "test-dummy-key")
    from agents.finance import inject_tool_catalog
    catalog = inject_tool_catalog()

    check("catalog header", "当前可用工具清单" in catalog)

    all_tools = {
        "add_expense", "add_income", "view_history", "get_financial_advice",
        "get_budget_plan", "query_transactions", "analyze_spending",
        "compare_period", "create_budget", "detect_anomaly", "generate_insight",
        "get_proactive_insights"
    }
    for name in all_tools:
        check(f"catalog lists: {name}", f"- {name}（" in catalog)

    # 5. Exactly the three write tools are marked as needing approval
    for name in ("add_expense", "add_income", "create_budget"):
        line = next((ln for ln in catalog.splitlines() if ln.startswith(f"- {name}（")), "")
        check(f"catalog approval mark: {name}", "写操作·需确认" in line, line)

    for name in ("query_transactions", "analyze_spending", "compare_period",
                 "detect_anomaly", "generate_insight"):
        line = next((ln for ln in catalog.splitlines() if ln.startswith(f"- {name}（")), "")
        check(f"catalog readonly mark: {name}", "只读" in line and "需确认" not in line, line)


# ---------------------------------------------------------------------------
# Proactive insights tests
# ---------------------------------------------------------------------------

REF_NOW = datetime(2026, 9, 20, 12, 0)


def _deps(expenses, budget=None):
    budget_repo = FakeBudgetRepository()
    if budget is not None:
        budget_repo.upsert(budget)
    return FinanceDependencies(
        expense_repo=FakeExpenseRepository(expenses),
        income_repo=FakeIncomeRepository([]),
        budget_repo=budget_repo if budget is not None else None
    )


def test_proactive_insights():
    from finance.services.proactive import ProactiveInsightService

    # -- Scenario A: all three rules fire ---------------------------------
    expenses = []
    # August history: 30 food transactions of 30
    for day in range(1, 31):
        expenses.append(make_tx(30.0, "food", f"8月餐饮{day}",
                                datetime(2026, 8, day, 12, 0)))
    # September: 10 food transactions of 60 (days 1-10) + one 200 on day 15
    for day in range(1, 11):
        expenses.append(make_tx(60.0, "food", f"9月餐饮{day}",
                                datetime(2026, 9, day, 12, 0)))
    expenses.append(make_tx(200.0, "food", "9月大额餐饮",
                            datetime(2026, 9, 15, 12, 0)))

    # hist daily 900/31 = 29.03; current daily 800/20 = 40 -> +37.8%
    # burn projection: 40/day * 30 days = 1200 vs budget 1000
    budget = Budget(period="2026-09", monthly_income=5000.0,
                    allocations={"food": 1000.0})
    deps = _deps(expenses, budget)

    insights = ProactiveInsightService.generate(deps, now=REF_NOW)
    check("proactive three insights", len(insights) == 3,
          f"{[i.code for i in insights]}")

    codes = {i.code for i in insights}
    check("proactive codes", codes == {
        "PROACTIVE_SPENDING_GROWTH",
        "PROACTIVE_BUDGET_RISK",
        "PROACTIVE_POSSIBLE_ANOMALY"
    }, str(codes))

    by_code = {i.code: i for i in insights}

    growth_msg = by_code["PROACTIVE_SPENDING_GROWTH"].message
    check("growth wording", growth_msg == "餐饮美食消费比历史平均增加 38%。",
          growth_msg)
    check("growth data", 37.0 <= by_code["PROACTIVE_SPENDING_GROWTH"].data["change_pct"] <= 39.0)

    risk_msg = by_code["PROACTIVE_BUDGET_RISK"].message
    check("budget risk main sentence", "按目前消费速度，本月可能超过预算" in risk_msg,
          risk_msg)
    check("budget risk numbers", "1,200" in risk_msg and "1,000" in risk_msg, risk_msg)

    anomaly_msg = by_code["PROACTIVE_POSSIBLE_ANOMALY"].message
    check("anomaly main sentence", "发现一笔明显高于历史平均水平的消费" in anomaly_msg,
          anomaly_msg)
    check("anomaly cautious wording", "可能异常" in anomaly_msg, anomaly_msg)
    check("anomaly numbers", "200" in anomaly_msg and "30" in anomaly_msg, anomaly_msg)

    # Safety: no fraud judgments anywhere
    all_text = " ".join(i.message for i in insights)
    check("no fraud wording", not any(w in all_text for w in ("欺诈", "盗刷", "欺骗")),
          all_text)

    # Rendered card
    card = ProactiveInsightService.format_insights(insights)
    check("card title", "### 🔔 主动提醒" in card)
    check("card lines", card.count("🟠") == 3, card)

    # -- Scenario B: calm month, nothing fires ----------------------------
    calm = []
    for day in range(1, 21):
        calm.append(make_tx(30.0, "food", f"8月餐饮{day}",
                            datetime(2026, 8, day, 12, 0)))
    for day in range(1, 11):
        calm.append(make_tx(30.0, "food", f"9月餐饮{day}",
                            datetime(2026, 9, day, 12, 0)))
    calm_insights = ProactiveInsightService.generate(_deps(calm), now=REF_NOW)
    check("calm no insights", calm_insights == [], f"{[i.code for i in calm_insights]}")
    calm_card = ProactiveInsightService.format_insights(calm_insights)
    check("calm card", "没有需要提醒你的事项" in calm_card, calm_card)

    # -- Tool registration: readonly, visible in live catalog -------------
    os.environ.setdefault("OPENAI_API_KEY", "test-dummy-key")
    from agents.finance import finance_agent
    tool = finance_agent._function_toolset.tools.get("get_proactive_insights")
    check("proactive tool registered", tool is not None)
    check("proactive tool no approval",
          tool is not None and not getattr(tool, "requires_approval", False))


# ---------------------------------------------------------------------------
# Timezone normalization regression: Supabase rows -> naive local datetimes
# ---------------------------------------------------------------------------

def test_supabase_date_normalization():
    from data.database import BaseSupabaseRepository

    repo = BaseSupabaseRepository.__new__(BaseSupabaseRepository)
    row = {
        "id": 1, "amount": 50.0, "description": "UTC 测试",
        "category": "food", "type": "expense",
        "date": "2026-09-20T16:00:00Z"
    }
    tx = repo._map_to_domain(row, TransactionType.EXPENSE)

    check("mapped date is naive", tx.date.tzinfo is None, str(tx.date))
    expected = (
        datetime.fromisoformat("2026-09-20T16:00:00+00:00")
        .astimezone().replace(tzinfo=None)
    )
    check("mapped date equals local time", tx.date == expected,
          f"{tx.date} vs {expected}")

    # Already-naive timestamps pass through unchanged
    row_naive = dict(row, date="2026-09-20T12:00:00")
    tx_naive = repo._map_to_domain(row_naive, TransactionType.EXPENSE)
    check("naive date unchanged",
          tx_naive.date == datetime(2026, 9, 20, 12, 0), str(tx_naive.date))

    # Comparable with a naive window (the original crash raised TypeError)
    start, end, _ = resolve_period("this_month", datetime.now())
    in_range = start <= tx.date < end
    check("naive comparison works", isinstance(in_range, bool))


if __name__ == "__main__":
    test_periods()
    test_analytics_and_compare()
    test_anomaly()
    test_budget()
    test_insight_pipeline()
    test_tool_registration()
    test_hitl()
    test_agent_workflow()
    test_proactive_insights()
    test_supabase_date_normalization()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All V1 tool tests passed.")
