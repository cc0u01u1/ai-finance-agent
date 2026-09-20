from typing import List, Optional
from pydantic_ai import Agent, RunContext, DeferredToolRequests
from finance.repositories.transaction_repository import TransactionRepository
from core.dependencies import FinanceDependencies
from finance.services.ledger import LedgerService
from finance.services.advisor import AdvisorService
from finance.services.categories import CategoryService
from core.observability import log_and_handle_error
from prompts.persona import FINANCIAL_PERSONA, SUMMARY_TEMPLATE
from core.settings import settings
from finance.services.analytics import AnalyticsService
from finance.services.anomaly import AnomalyService
from finance.services.budgets import BudgetService
from finance.services.insights import InsightService
from finance.services.proactive import ProactiveInsightService
from finance.services.categories import category_label
from finance.models.enums import TransactionType
from finance.utils.periods import resolve_period, previous_period

# Initialize the Professional Financial Assistant
# We don't define the model here anymore to allow injection
finance_agent = Agent(
    'openai:gpt-4o', # Default, will be overridden by container
    deps_type=FinanceDependencies,
    system_prompt=FINANCIAL_PERSONA,
    # Write tools require human approval; the run ends with DeferredToolRequests.
    output_type=[str, DeferredToolRequests]
)

@finance_agent.tool(requires_approval=True)
@log_and_handle_error
def add_expense(ctx: RunContext[FinanceDependencies], amount: float, category: str, description: str) -> str:
    """
    Record a new expense transaction.
    Args:
        amount: The dollar amount spent (positive number).
        category: Category of expense (food, transport, entertainment, etc.)
        description: Brief details of the purchase.
    """
    ledger = LedgerService(ctx.deps.expense_repo, ctx.deps.income_repo)
    # Use CategoryService for robust mapping
    expense_cat = CategoryService.map_to_category(category)
    expense = ledger.record_expense(amount, expense_cat, description)
    return SUMMARY_TEMPLATE.format(
        category=expense.category.value,
        amount=expense.amount,
        description=expense.description
    )

@finance_agent.tool(requires_approval=True)
@log_and_handle_error
def add_income(ctx: RunContext[FinanceDependencies], amount: float, source: str, description: str = "") -> str:
    """
    Record a new income (deposit, salary, etc.).
    Args:
        amount: The dollar amount earned (positive number).
        source: Source of income (Salary, Freelance, Gift, etc.)
        description: Optional details.
    """
    ledger = LedgerService(ctx.deps.expense_repo, ctx.deps.income_repo)
    income = ledger.record_income(amount, source, description)
    return f"💰 Income Recorded: +${income.amount:.2f} from {source}"

@finance_agent.tool
@log_and_handle_error
def view_history(ctx: RunContext[FinanceDependencies], category_name: str = "all") -> str:
    """
    Retrieve and format the transaction history (Income and Expenses).
    Args:
        category_name: Optional category to filter by (or 'all').
    """
    ledger = LedgerService(ctx.deps.expense_repo, ctx.deps.income_repo)
    category = None
    if category_name and category_name.lower() != 'all':
        category = CategoryService.map_to_category(category_name)
    
    expenses = ledger.get_transaction_history(category)
    return ledger.format_history_report(category, expenses)

@finance_agent.tool
@log_and_handle_error
def get_financial_advice(ctx: RunContext[FinanceDependencies]) -> str:
    """
    Analyze spending patterns and provide actionable financial advice.
    """
    advisor = AdvisorService()
    ledger = LedgerService(ctx.deps.expense_repo, ctx.deps.income_repo)
    expenses = ledger.get_transaction_history()
    analysis = advisor.analyze_spending(expenses)
    
    res = f"FINANCIAL ANALYSIS\n{'='*20}\n"
    res += f"Total Spending: ${analysis.total_spent:.2f}\n"
    res += f"Top Category: {analysis.top_category}\n\n"
    res += "Recommendations:\n"
    for rec in analysis.recommendations:
        res += f"- {rec}\n"
    return res

@finance_agent.tool
@log_and_handle_error
def get_budget_plan(ctx: RunContext[FinanceDependencies], monthly_income: float) -> str:
    """
    Generate a professional budget plan based on monthly income.
    Args:
        monthly_income: Your total monthly earnings.
    """
    advisor = AdvisorService()
    plan = advisor.get_budget_advice(monthly_income)
    
    res = f"BUDGET PLAN FOR INCOME: ${monthly_income:.2f}\n{'='*40}\n"
    res += f"- Needs (50%):    ${plan.needs:>10.2f}\n"
    res += f"- Wants (30%):    ${plan.wants:>10.2f}\n"
    res += f"- Savings (20%):  ${plan.savings:>10.2f}\n"
    res += f"{'-'*40}\nExpert Suggestions:\n"
    for s in plan.advice:
        res += f"• {s}\n"
    return res


# ---------------------------------------------------------------------------
# V1 new Agent Tools (AI 财务管家 Agent)
# ---------------------------------------------------------------------------

def _load_all_transactions(ctx) -> List:
    expenses = ctx.deps.expense_repo.list_all()
    income = ctx.deps.income_repo.list_all()
    transactions = expenses + income
    transactions.sort(key=lambda t: t.date, reverse=True)
    return transactions


@finance_agent.tool
@log_and_handle_error
def query_transactions(
    ctx: RunContext[FinanceDependencies],
    period: str = "this_month",
    category: str = "",
    tx_type: str = "",
    limit: int = 50
) -> str:
    """
    查询交易流水。按周期、类别、收支类型筛选。
    Args:
        period: 周期，如 this_month(本月)、last_month(上月)、this_week(本周)、last_30d(近30天) 或 '2026-09'。
        category: 类别，如 food/餐饮、transport/交通、shopping/购物；留空或 all 表示全部。
        tx_type: 收支类型，expense(支出) 或 income(收入)；留空表示全部。
        limit: 最多返回条数，默认 50。
    """
    start, end, label = resolve_period(period)

    wanted_category = None
    if category and category.lower() not in ("all", "全部"):
        wanted_category = CategoryService.map_to_category(category)

    wanted_type = None
    if tx_type:
        low = tx_type.lower()
        if "支出" in tx_type or low == "expense":
            wanted_type = TransactionType.EXPENSE
        elif "收入" in tx_type or low == "income":
            wanted_type = TransactionType.INCOME

    matched = []
    for tx in _load_all_transactions(ctx):
        if not (start <= tx.date < end):
            continue
        if wanted_type is not None and tx.type != wanted_type:
            continue
        if wanted_category is not None and tx.category != wanted_category:
            continue
        matched.append(tx)

    matched.sort(key=lambda t: t.date, reverse=True)
    shown = matched[:limit]

    lines = [f"## 🔎 {label} 交易查询", "", f"共 {len(matched)} 笔，展示 {len(shown)} 笔：", ""]
    if not shown:
        lines.append("_没有符合条件的记录。_")
        return "\n".join(lines)

    total_expense = sum(t.amount for t in matched if t.type == TransactionType.EXPENSE)
    total_income = sum(t.amount for t in matched if t.type == TransactionType.INCOME)

    for t in shown:
        sign = "+" if t.type == TransactionType.INCOME else "-"
        cat = category_label(t.category.value if t.category else None)
        lines.append(
            f"- [{t.date:%Y-%m-%d}] {sign}¥{t.amount:,.2f} "
            f"｜{cat}｜{t.description}"
        )
    lines.append("")
    lines.append(f"合计：收入 ¥{total_income:,.2f}　支出 ¥{total_expense:,.2f}")
    return "\n".join(lines)


@finance_agent.tool
@log_and_handle_error
def analyze_spending(
    ctx: RunContext[FinanceDependencies],
    period: str = "this_month"
) -> str:
    """
    消费分析：汇总指定周期的总支出、净结余、日均支出、储蓄率与分类占比。
    Args:
        period: 周期，如 this_month(本月)、last_month(上月)、this_week(本周) 或 '2026-09'。
    """
    start, end, label = resolve_period(period)
    summary = AnalyticsService.summarize(
        _load_all_transactions(ctx), start, end, label
    )
    return AnalyticsService.format_summary(summary)


@finance_agent.tool
@log_and_handle_error
def compare_period(
    ctx: RunContext[FinanceDependencies],
    period: str = "this_month",
    base_period: str = ""
) -> str:
    """
    消费对比：比较两个周期的总支出与各类别变化。不传 base_period 时自动对比上一周期。
    Args:
        period: 当前周期，如 this_month(本月)、this_week(本周) 或 '2026-09'。
        base_period: 基准周期，如 last_month(上月)；留空则自动取等长的上一周期。
    """
    start, end, label = resolve_period(period)
    if base_period:
        b_start, b_end, b_label = resolve_period(base_period)
    else:
        b_start, b_end, b_label = previous_period(start, end, label)

    transactions = _load_all_transactions(ctx)
    current = AnalyticsService.summarize(transactions, start, end, label)
    previous = AnalyticsService.summarize(transactions, b_start, b_end, b_label)
    comparison = AnalyticsService.compare(current, previous)
    return AnalyticsService.format_comparison(comparison)


@finance_agent.tool(requires_approval=True)
@log_and_handle_error
def create_budget(
    ctx: RunContext[FinanceDependencies],
    monthly_income: float,
    period: str = "",
    allocations: Optional[dict] = None
) -> str:
    """
    创建（或更新）指定周期的 AI 预算。不传 allocations 时，基于历史支出自动生成可执行预算。
    Args:
        monthly_income: 月收入金额（正数）。
        period: 预算周期，如 this_month(本月) 或 '2026-10'；留空默认本月。
        allocations: 可选，类别到金额的映射，如 {'food': 1400, 'transport': 300}。
    """
    if ctx.deps.budget_repo is None:
        return "❌ 预算服务未初始化，请确认 SUPABASE_URL 与 SUPABASE_SERVICE_ROLE_KEY 已配置。"

    start, _, label = resolve_period(period or None)
    history_expenses = [
        t for t in ctx.deps.expense_repo.list_all() if t.date < start
    ]

    try:
        budget = BudgetService.create(
            repo=ctx.deps.budget_repo,
            period=label,
            monthly_income=monthly_income,
            allocations=allocations,
            history_expenses=history_expenses
        )
    except Exception as e:
        return (
            f"❌ 预算保存失败：{e}。"
            "如果是首次使用，请先在 Supabase 执行 data/setup.sql 中 budgets 表的建表语句。"
        )
    return BudgetService.format_budget(budget)


@finance_agent.tool
@log_and_handle_error
def detect_anomaly(
    ctx: RunContext[FinanceDependencies],
    period: str = "this_month"
) -> str:
    """
    异常消费检测：识别大额离群消费、类别内异常与类别环比激增。
    Args:
        period: 周期，如 this_month(本月)、last_month(上月) 或 '2026-09'。
    """
    start, end, label = resolve_period(period)
    p_start, p_end, _ = previous_period(start, end, label)

    current_expenses = [
        t for t in ctx.deps.expense_repo.list_all() if start <= t.date < end
    ]
    previous_expenses = [
        t for t in ctx.deps.expense_repo.list_all() if p_start <= t.date < p_end
    ]
    anomalies = AnomalyService.detect(current_expenses, previous_expenses)
    return AnomalyService.format_anomalies(anomalies, label)


@finance_agent.tool
@log_and_handle_error
def generate_insight(
    ctx: RunContext[FinanceDependencies],
    period: str = "this_month"
) -> str:
    """
    生成财务洞察（核心能力）。综合预算、异常、趋势、储蓄率与消费集中度规则，
    给出按严重程度排序的中文洞察与行动建议。
    Pipeline: 财务数据 → 规则/分析 → Insight → Agent → 用户。
    Args:
        period: 周期，如 this_month(本月)、last_month(上月) 或 '2026-09'。
    """
    report = InsightService.generate(ctx.deps, period)
    return InsightService.format_report(report)


@finance_agent.tool
@log_and_handle_error
def get_proactive_insights(ctx: RunContext[FinanceDependencies]) -> str:
    """
    主动提醒：检测消费增长、预算风险与可能异常，每类最多一条，共最多三条。
    用于首页或记账后主动推送给用户的轻量洞察。
    """
    insights = ProactiveInsightService.generate(ctx.deps)
    return ProactiveInsightService.format_insights(insights)


# ---------------------------------------------------------------------------
# Dynamic system prompt: live tool catalog for the Planning step.
# Read at run time from the registered toolset, so it never drifts from the
# tools actually available (single source of truth).
# ---------------------------------------------------------------------------

@finance_agent.system_prompt
def inject_tool_catalog() -> str:
    tools = finance_agent._function_toolset.tools
    lines = ["【当前可用工具清单】"]
    for name in sorted(tools):
        tool = tools[name]
        description = (getattr(tool, "description", "") or "").strip()
        first_line = description.splitlines()[0] if description else ""
        kind = "写操作·需确认" if getattr(tool, "requires_approval", False) else "只读"
        lines.append(f"- {name}（{kind}）：{first_line}")
    return "\n".join(lines)

