from pydantic_ai import Agent, RunContext, DeferredToolRequests
from core.container import Container, create_finance_agent
from agents.strategy import strategy_agent
from core.dependencies import FinanceDependencies
from core.settings import settings
from core.observability import track_agent_run, log_agent_result
from finance.utils.hitl import format_pending_notification

# Initialize the database
# Initialize the dependencies
try:
    deps = Container.get_finance_dependencies()
except Exception as e:
    print(f"Failed to initialize database: {e}")
    # Fallback to None or exit if critical, but for now we proceed/log
    deps = None

# Router Agent
# This agent's sole purpose is to route the user's request to the correct sub-agent.
# We give it a system prompt to help it decide or ask the user.
ROUTER_SYSTEM_PROMPT = """
You are the **Personal Finance Hub**, a professional and concierge-like assistant.
Your goal is to seamlessly connect the user to the right specialist.

You have access to two elite specialists:
1. **Finance Assistant** 📊: Handles transaction recording, history, and budget tracking.
2. **Strategy Agent** 🧠: Provides high-level wealth strategy, goal feasibility, and long-term planning.

**CRITICAL PROTOCOL:**
- You do not have direct database access. **ALWAYS** delegate actionable requests (recording, viewing history) to the specialists via tools.
- If the user says "I spent $10", delegate to **Finance Assistant**.
- If the user says "Record income", delegate to **Finance Assistant**.
- If the user asks for advice, delegate to **Strategy Agent**.

**TONE & STYLE:**
- Be crisp, professional, and welcoming.
- Use a helpful tone.
- If the user's intent is ambiguous, politely ask: "Would you like me to access your *Transaction Ledger* 📊 or consult the *Wealth Strategist* 🧠?"

If the intent is clear, call the tool immediately.
"""

router_agent = Agent(
    model=settings.get_model(),
    system_prompt=ROUTER_SYSTEM_PROMPT,
    deps_type=FinanceDependencies
)

# Re-define router agent to not require deps in signature for this web layer
router_agent_web = Agent(
    model=settings.get_model(),
    system_prompt=ROUTER_SYSTEM_PROMPT,
)

@router_agent_web.tool
async def ask_finance_global(ctx: RunContext[None], query: str) -> str:
    """
    Pass the user's query to the Finance Assistant. 
    Use this for: expense tracking, income recording, viewing cursor/transaction history, and reports.
    """
    async with track_agent_run("Finance Agent", str(settings.get_model()), {"query": query}):
        finance_agent = create_finance_agent()
        result = await finance_agent.run(query, deps=deps)
        # Sub-agent calls cannot bypass HITL: return a confirmation notice.
        if isinstance(result.output, DeferredToolRequests):
            return format_pending_notification(result.output)
        log_agent_result(result.output)
        return result.output

@router_agent_web.tool
async def ask_strategy_global(ctx: RunContext[None], query: str) -> str:
    """
    Pass the user's query to the Strategy Agent.
    Use this for: financial advice, investment strategy, and goal planning.
    """
    async with track_agent_run("Strategy Agent", str(settings.get_model()), {"query": query}):
        res = await strategy_agent.run(query, deps=deps)
        log_agent_result(str(res.data))
        return str(res.data)

app = router_agent_web.to_web()
