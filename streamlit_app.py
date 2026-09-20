import streamlit as st
import asyncio
import pandas as pd
import plotly.express as px
from datetime import datetime
from dotenv import load_dotenv

# Project imports
from core.container import Container, create_finance_agent
from core.settings import settings
from finance.models.enums import TransactionType
from finance.services.analytics import AnalyticsService
from finance.services.budgets import BudgetService
from finance.services.proactive import ProactiveInsightService
from finance.utils.hitl import describe_tool_call, build_approval_results
from finance.utils.periods import resolve_period, previous_period
from pydantic_ai import DeferredToolRequests

# Load environment
load_dotenv()

# --- Page Config (must be the first Streamlit call) ---
st.set_page_config(
    page_title="AI 财务管家",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Styling (dark modern theme, native Streamlit layout untouched) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp { background-color: #020617; }

    div[data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.5);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    div[data-testid="stMetricValue"] { font-size: 1.8rem !important; }

    div[data-testid="stSidebar"] {
        background-color: #020617;
        border-right: 1px solid #1e293b;
    }

    .insight-card {
        background: #0f172a;
        padding: 18px 20px;
        border-radius: 12px;
        border: 1px solid #1e293b;
        margin-bottom: 14px;
    }
    .stDataFrame {
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

PAGES = ["🏠 首页", "🤖 AI 助手", "💰 我的账单", "📊 消费分析", "🎯 AI预算", "🔔 AI提醒"]
WELCOME = "你好，我是你的 AI 财务管家 💰 记账、查账、分析、做预算，直接跟我说就好。"

# --- Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": WELCOME}]

if "pending_requests" not in st.session_state:
    st.session_state.pending_requests = None
if "pending_history" not in st.session_state:
    st.session_state.pending_history = None
if "budget_preview" not in st.session_state:
    st.session_state.budget_preview = None

if "deps" not in st.session_state:
    try:
        st.session_state.deps = Container.get_finance_dependencies()
    except Exception as e:
        st.error(f"系统初始化失败：{e}")
        st.session_state.deps = None


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def all_transactions():
    if not st.session_state.deps:
        return []
    expenses = st.session_state.deps.expense_repo.list_all()
    income = st.session_state.deps.income_repo.list_all()
    return list(expenses) + list(income)


def month_window(ref=None):
    ref = ref or datetime.now()
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    label = f"{start.year:04d}-{start.month:02d}"
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end, label


# ---------------------------------------------------------------------------
# Agent run + HITL resume (shared logic)
# ---------------------------------------------------------------------------

def send_message(prompt):
    """Run the finance agent with a new user message; handle HITL suspension."""
    st.session_state.messages.append({"role": "user", "content": prompt})
    model = settings.get_model()

    async def _run():
        agent = create_finance_agent()
        return await agent.run(prompt, model=model, deps=st.session_state.deps)

    try:
        with st.spinner("管家正在查账本、做分析…"):
            res = asyncio.run(_run())
        if isinstance(res.output, DeferredToolRequests):
            st.session_state.pending_requests = res.output
            st.session_state.pending_history = res.all_messages()
        else:
            st.session_state.messages.append(
                {"role": "assistant", "content": res.output}
            )
    except Exception as e:
        st.session_state.messages.append(
            {"role": "assistant", "content": f"抱歉，处理时遇到问题：{e}"}
        )
    st.rerun()


def resume_pending_agent(decisions):
    """Resume a suspended run after the user approved/denied write calls."""
    requests = st.session_state.pending_requests
    approval_results = build_approval_results(requests, decisions)
    model = settings.get_model()

    async def _resume():
        agent = create_finance_agent()
        return await agent.run(
            None,
            model=model,
            deps=st.session_state.deps,
            message_history=st.session_state.pending_history,
            deferred_tool_results=approval_results
        )

    result = asyncio.run(_resume())

    # The model may issue new write calls: surface another approval round.
    if isinstance(result.output, DeferredToolRequests):
        st.session_state.pending_requests = result.output
        st.session_state.pending_history = result.all_messages()
    else:
        st.session_state.pending_requests = None
        st.session_state.pending_history = None
        st.session_state.messages.append(
            {"role": "assistant", "content": result.output}
        )
    st.rerun()


def goto(page):
    """Callback: switch the sidebar radio page."""
    st.session_state.nav = page


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        "<h1 style='color:#10b981; margin-bottom:0;'>💰 AI 财务管家</h1>",
        unsafe_allow_html=True
    )
    st.caption("你的个人财务智能体")

    st.radio(
        "页面导航", PAGES, key="nav", label_visibility="collapsed"
    )

    if st.button("🔄 新开对话", width='stretch'):
        st.session_state.messages = [{"role": "assistant", "content": WELCOME}]
        st.session_state.pending_requests = None
        st.session_state.pending_history = None
        st.rerun()

    with st.expander("🔧 演示工具"):
        if st.button("🌱 生成演示数据", width='stretch'):
            from finance.utils.seeder import DataSeeder
            try:
                with st.spinner("生成中…"):
                    DataSeeder.seed_dummy_data(st.session_state.deps)
                st.success("演示数据已生成。")
            except Exception as e:
                st.error(f"生成失败：{e}")

        if st.button("🗑️ 清空所有数据", width='stretch'):
            if st.session_state.get("clear_confirm"):
                st.session_state.deps.expense_repo.clear()
                st.session_state.deps.income_repo.clear()
                st.session_state.clear_confirm = False
                st.success("已清空。")
            else:
                st.session_state.clear_confirm = True
                st.warning("再点一次确认清空。")

nav = st.session_state.nav


# ---------------------------------------------------------------------------
# 🏠 首页
# ---------------------------------------------------------------------------

if nav == "🏠 首页":
    st.title("🏠 首页")
    st.caption(datetime.now().strftime("%Y年%m月%d日"))

    txs = all_transactions()
    start, end, label = month_window()
    summary = AnalyticsService.summarize(txs, start, end, label)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("本月支出", f"¥{summary.total_expense:,.2f}")
    c2.metric("本月收入", f"¥{summary.total_income:,.2f}")
    net_delta = f"储蓄率 {summary.savings_rate * 100:.0f}%"
    c3.metric("本月结余", f"¥{summary.net:,.2f}", net_delta)
    c4.metric("日均支出", f"¥{summary.avg_daily_expense:,.2f}")

    st.divider()

    left, right = st.columns([3, 2])

    with left:
        st.subheader("🧾 最近交易")
        recent = sorted(txs, key=lambda t: t.date, reverse=True)[:5]
        if recent:
            df_recent = pd.DataFrame([{
                "日期": t.date.strftime("%m-%d"),
                "类型": "收入" if t.type == TransactionType.INCOME else "支出",
                "类别": t.category.value if t.category else "other",
                "备注": t.description,
                "金额": f"¥{t.amount:,.2f}"
            } for t in recent])
            st.dataframe(df_recent, hide_index=True, width='stretch')
        else:
            st.info("还没有记录，先让管家帮你记一笔吧。")

    with right:
        st.subheader("🔔 今日提醒")
        proactive = ProactiveInsightService.generate(st.session_state.deps)
        if proactive:
            for item in proactive[:3]:
                st.markdown(f"🟠 {item.message}")
            st.button("查看全部提醒", on_click=goto, args=("🔔 AI提醒",))
        else:
            st.markdown("✅ 近期没有需要提醒你的事项。")

    st.divider()
    st.markdown("#### 🤖 有问题，直接问管家")
    st.markdown('例如：**“为什么我这个月花这么多？”** —— 我会自己查账本、做对比、找原因。')
    st.button("去 AI 助手", type="primary", on_click=goto, args=("🤖 AI 助手",))


# ---------------------------------------------------------------------------
# 🤖 AI 助手（核心 Demo 页）
# ---------------------------------------------------------------------------

elif nav == "🤖 AI 助手":
    st.title("🤖 AI 助手")
    st.caption("直接用大白话问我。我会自己规划、调用工具查数据；涉及记账或预算，一定先请你确认。")

    # Example prompts: only while the conversation has not really started
    if len(st.session_state.messages) <= 1:
        examples = [
            "为什么我这个月花这么多？",
            "我上个月的钱都花哪了？",
            "帮我记一笔：午餐 35 元",
            "最近有没有异常消费？",
        ]
        cols = st.columns(len(examples))
        for col, text in zip(cols, examples):
            if col.button(text, key=f"example_{text}"):
                send_message(text)

    # Conversation history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # --- HITL approval card ---
    if st.session_state.pending_requests is not None:
        requests = st.session_state.pending_requests
        with st.chat_message("assistant"):
            st.markdown("### 📋 需要你确认")
            st.caption("以下操作会修改数据，管家不会替你做决定。")

            decisions = {}
            for index, call in enumerate(requests.approvals, start=1):
                col_desc, col_choice = st.columns([3, 1])
                col_desc.markdown(f"{index}. {describe_tool_call(call)}")
                choice = col_choice.radio(
                    "decision", ["确认", "拒绝"],
                    horizontal=True,
                    key=f"hitl_{call.tool_call_id}",
                    label_visibility="collapsed"
                )
                decisions[call.tool_call_id] = (choice == "确认")

            c_submit, c_approve_all, c_deny_all = st.columns(3)
            if c_submit.button("📨 提交决策", type="primary", width='stretch'):
                resume_pending_agent(decisions)
            if c_approve_all.button("✅ 全部确认", width='stretch'):
                resume_pending_agent(
                    {call.tool_call_id: True for call in requests.approvals}
                )
            if c_deny_all.button("❌ 全部拒绝", width='stretch'):
                resume_pending_agent(
                    {call.tool_call_id: False for call in requests.approvals}
                )

    # Free chat input: only while nothing is awaiting a decision
    if st.session_state.pending_requests is None:
        if prompt := st.chat_input("问问管家，比如：为什么我这个月花这么多？"):
            send_message(prompt)


# ---------------------------------------------------------------------------
# 💰 我的账单
# ---------------------------------------------------------------------------

elif nav == "💰 我的账单":
    st.title("💰 我的账单")

    f1, f2, f3 = st.columns(3)
    period_choice = f1.selectbox(
        "周期", ["本月", "上月", "近 30 天", "全部"], key="bill_period"
    )
    type_choice = f2.selectbox("收支类型", ["全部", "支出", "收入"], key="bill_type")

    txs = all_transactions()
    cats_present = sorted({
        (t.category.value if t.category else "other") for t in txs
    })
    cat_choice = f3.selectbox("类别", ["全部"] + cats_present, key="bill_cat")

    period_map = {
        "本月": "this_month",
        "上月": "last_month",
        "近 30 天": "last_30d",
        "全部": "all"
    }
    start, end, _ = resolve_period(period_map[period_choice], datetime.now())

    rows = []
    for t in txs:
        if not (start <= t.date < end):
            continue
        is_income = t.type == TransactionType.INCOME
        if type_choice == "支出" and is_income:
            continue
        if type_choice == "收入" and not is_income:
            continue
        cat = t.category.value if t.category else "other"
        if cat_choice != "全部" and cat != cat_choice:
            continue
        rows.append({
            "日期": t.date.strftime("%Y-%m-%d"),
            "类型": "收入" if is_income else "支出",
            "类别": cat,
            "备注": t.description,
            "金额": t.amount
        })

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("当前筛选条件下没有交易。")
    else:
        df = df.sort_values("日期", ascending=False)
        expense_total = df.loc[df["类型"] == "支出", "金额"].sum()
        income_total = df.loc[df["类型"] == "收入", "金额"].sum()
        st.markdown(
            f"共 **{len(df)}** 笔　支出 **¥{expense_total:,.2f}**"
            f"　收入 **¥{income_total:,.2f}**"
        )
        df["金额"] = df["金额"].map(lambda x: f"¥{x:,.2f}")
        st.dataframe(df, hide_index=True, width='stretch')


# ---------------------------------------------------------------------------
# 📊 消费分析
# ---------------------------------------------------------------------------

elif nav == "📊 消费分析":
    st.title("📊 消费分析")

    period_choice = st.radio(
        "分析周期", ["本月", "上月"], horizontal=True, label_visibility="collapsed"
    )
    expression = "this_month" if period_choice == "本月" else "last_month"
    start, end, label = resolve_period(expression, datetime.now())
    p_start, p_end, p_label = previous_period(start, end, label)

    txs = all_transactions()
    summary = AnalyticsService.summarize(txs, start, end, label)
    previous = AnalyticsService.summarize(txs, p_start, p_end, p_label)
    comparison = AnalyticsService.compare(summary, previous)

    change_text = (
        f"{comparison.change_pct:+.1f}%"
        if comparison.change_pct is not None else "无对比基数"
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("总支出", f"¥{summary.total_expense:,.2f}", change_text)
    c2.metric("日均支出", f"¥{summary.avg_daily_expense:,.2f}")
    c3.metric("储蓄率", f"{summary.savings_rate * 100:.1f}%")

    chart_left, chart_right = st.columns(2)

    with chart_left:
        st.subheader("类别占比")
        if summary.categories:
            df_cat = pd.DataFrame([{
                "类别": s.category,
                "金额": s.amount
            } for s in summary.categories])
            fig_pie = px.pie(
                df_cat, names="类别", values="金额", hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Prism,
                template="plotly_dark"
            )
            fig_pie.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_pie, width='stretch')
        else:
            st.info("本周期暂无支出。")

    with chart_right:
        st.subheader("月度支出趋势")
        expense_txs = [t for t in txs if t.type == TransactionType.EXPENSE]
        if expense_txs:
            df_trend = pd.DataFrame([{
                "月份": t.date.strftime("%Y-%m"),
                "金额": t.amount
            } for t in expense_txs])
            df_trend = df_trend.groupby("月份", as_index=False)["金额"].sum()
            fig_trend = px.bar(
                df_trend, x="月份", y="金额",
                color_discrete_sequence=["#10b981"],
                template="plotly_dark"
            )
            fig_trend.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_trend, width='stretch')
        else:
            st.info("暂无历史支出。")


# ---------------------------------------------------------------------------
# 🎯 AI预算
# ---------------------------------------------------------------------------

elif nav == "🎯 AI预算":
    st.title("🎯 AI预算")

    _, _, label = month_window()
    budget_repo = st.session_state.deps.budget_repo
    budget = budget_repo.get_for_period(label)

    if st.session_state.budget_preview is not None and budget is None:
        preview = st.session_state.budget_preview
        st.markdown(f"### ✨ {label} 预算预览")
        st.caption("基于你的历史支出和月收入生成，确认后才会生效。")
        st.markdown(f"月收入：**¥{preview['income']:,.2f}**")
        rows = [{"类别": cat, "金额": amt} for cat, amt in preview["allocations"].items()]
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, width='stretch'
        )
        st.markdown(f"计划总支出：**¥{sum(preview['allocations'].values()):,.2f}**")
        c_ok, c_cancel = st.columns(2)
        if c_ok.button("✅ 确认创建", type="primary", width='stretch'):
            BudgetService.create(
                budget_repo,
                period=label,
                monthly_income=preview["income"],
                allocations=preview["allocations"],
                history_expenses=all_transactions()
            )
            st.session_state.budget_preview = None
            st.rerun()
        if c_cancel.button("↩️ 取消", width='stretch'):
            st.session_state.budget_preview = None
            st.rerun()

    elif budget is not None:
        txs = all_transactions()
        start, end, _ = month_window()
        period_expenses = [
            t for t in txs
            if t.type == TransactionType.EXPENSE and start <= t.date < end
        ]
        status_rows = BudgetService.budget_status(budget, period_expenses)

        total_planned = budget.total_allocated
        total_spent = sum(r["spent"] for r in status_rows)
        overall = min(total_spent / total_planned, 1.0) if total_planned > 0 else 0.0
        st.markdown(
            f"**{label}**　预算 ¥{total_planned:,.2f}　已花 ¥{total_spent:,.2f}"
        )
        st.progress(overall)

        for row in status_rows:
            if row["planned"] <= 0:
                continue
            bar_ratio = min(max(row["usage_pct"], 0.0), 1.0)
            over = "　🔴 已超支" if row["usage_pct"] >= 1.0 else (
                "　🟠 接近上限" if row["usage_pct"] >= 0.8 else ""
            )
            st.markdown(
                f"**{row['category']}**　¥{row['spent']:,.0f} / ¥{row['planned']:,.0f}"
                f"（{row['usage_pct'] * 100:.0f}%）{over}"
            )
            st.progress(bar_ratio)

    else:
        st.info(f"你还没有 {label} 的预算。管家可以基于你的历史消费一键生成。")
        income = st.number_input(
            "本月收入（元）", min_value=0.0, value=0.0, step=500.0
        )
        if st.button("✨ 生成预算预览", type="primary"):
            history = [
                t for t in all_transactions() if t.type == TransactionType.EXPENSE
            ]
            allocations = BudgetService.derive_allocations(history, income)
            st.session_state.budget_preview = {
                "income": income, "allocations": allocations
            }
            st.rerun()


# ---------------------------------------------------------------------------
# 🔔 AI提醒
# ---------------------------------------------------------------------------

elif nav == "🔔 AI提醒":
    st.title("🔔 AI提醒")
    st.caption("管家主动发现的消费信号。异常只代表“可能”，不做任何定性判断。")

    insights = ProactiveInsightService.generate(st.session_state.deps)

    if not insights:
        st.markdown("### ✅ 一切平稳")
        st.markdown("近期没有发现消费增长、预算风险或异常消费，继续保持。")
    else:
        icon = {'critical': '🔴', 'warning': '🟠', 'info': '🔵'}
        for item in insights:
            st.markdown(
                f"""
                <div class="insight-card">
                    <div style="font-size:1.05rem; font-weight:700;">
                        {icon.get(item.severity, '🔵')} {item.title}
                    </div>
                    <div style="color:#cbd5e1; margin-top:6px;">{item.message}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if item.suggestion:
                st.markdown(f"> 建议：{item.suggestion}")

st.markdown("---")
st.caption("💰 AI 财务管家 · 让每一笔钱都花得明白")
