from pydantic_ai import Agent, RunContext, DeferredToolRequests
from agents.finance import finance_agent
from core.dependencies import FinanceDependencies
from prompts.persona import STRATEGY_PERSONA
from core.settings import settings
from application.dtos.strategy_response import StrategyResponse
from finance.utils.hitl import format_pending_notification

# Initialize the High-Level Wealth Strategy Agent
strategy_agent = Agent(
    model=settings.get_model(),
    deps_type=FinanceDependencies,
    system_prompt=STRATEGY_PERSONA,
    output_type=StrategyResponse,
    retries=3
)

@strategy_agent.tool
async def query_finance_assistant(ctx: RunContext[FinanceDependencies], query: str) -> str:
    """
    Delegates a query to the Finance Assistant for data retrieval or expense recording.
    Use this for:
    - Recording new expenses
    - Viewing history
    - Getting basic spending analysis
    - Generating budget plans
    """
    # We pass the same database dependency to the sub-agent
    # And we must pass the model to ensure we don't fall back to default OpenAI
    result = await finance_agent.run(query, deps=ctx.deps, model=ctx.model)
    # Sub-agent calls cannot bypass HITL: return a confirmation notice.
    if isinstance(result.output, DeferredToolRequests):
        return format_pending_notification(result.output)
    return result.output

@strategy_agent.tool
def evaluate_goal_feasibility(ctx: RunContext[FinanceDependencies], goal_name: str, amount: float) -> str:
    """
    Analyze if a specific financial goal is feasible based on current data.
    """
    # This is a placeholder for more complex logic
    # In a real scenario, it might fetch historical savings rate
    return f"Goal '{goal_name}' for ${amount} is under review. Please ask the Finance Assistant for my savings history first."
