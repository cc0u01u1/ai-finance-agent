"""Human-in-the-loop (HITL) helpers.

Bridges Pydantic AI's deferred tool approval mechanism with our user
interfaces:
    tool call -> DeferredToolRequests -> user decision -> DeferredToolResults

Also provides an auto-approval runner for automated tests and evaluations.
"""
from typing import Any, Dict, Optional, Union
from pydantic_ai import (
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)
from pydantic_ai.messages import ToolCallPart
from finance.services.categories import category_label, CategoryService
from finance.utils.periods import resolve_period

ApprovalDecision = Union[bool, ToolApproved, ToolDenied]

# Safety cap on approval rounds to avoid endless loops if a model keeps
# requesting new write-tool calls.
MAX_APPROVAL_ROUNDS = 10


def describe_tool_call(call: ToolCallPart) -> str:
    """Return a one-line Chinese description of a pending tool call."""
    args = call.args
    name = call.tool_name

    if name == "add_expense":
        amount = float(args.get("amount", 0))
        category = CategoryService.map_to_category(str(args.get("category", "")))
        label = category_label(category.value if category else None)
        description = str(args.get("description", "")).strip()
        extra = f"（{description}）" if description else ""
        return f"记一笔支出：**¥{amount:,.2f}**｜{label}{extra}"

    if name == "add_income":
        amount = float(args.get("amount", 0))
        source = str(args.get("source", "")).strip() or "未注明来源"
        description = str(args.get("description", "")).strip()
        extra = f"（{description}）" if description else ""
        return f"记一笔收入：**¥{amount:,.2f}**｜{source}{extra}"

    if name == "create_budget":
        income = float(args.get("monthly_income", 0))
        period = str(args.get("period", "")).strip()
        if period:
            _, _, label = resolve_period(period)
        else:
            _, _, label = resolve_period(None)
        return f"创建 **{label}** 预算（月收入 ¥{income:,.2f}）"

    # Generic fallback
    return f"执行操作「{name}」，参数：{dict(args)}"


def format_pending_notification(requests: DeferredToolRequests) -> str:
    """Short notification used when a sub-agent call hits the approval gate.

    Sub-agents cannot approve on the user's behalf, so they return this text
    and guide the user to confirm through the financial assistant.
    """
    pending = requests.approvals
    lines = [
        "⚠️ **该操作需要你确认后才能执行**：",
        ""
    ]
    for index, call in enumerate(pending, start=1):
        lines.append(f"{index}. {describe_tool_call(call)}")
    lines.append("")
    lines.append("请在财务助手对话中确认上述操作，确认后即可继续。")
    return "\n".join(lines)


def format_pending_requests(requests: DeferredToolRequests) -> str:
    """Render all pending approvals as a Chinese markdown prompt."""
    pending = requests.approvals
    lines = [
        "## 📋 需要你确认",
        "",
        f"管家准备执行 **{len(pending)}** 个操作，请确认：",
        ""
    ]
    for index, call in enumerate(pending, start=1):
        lines.append(f"{index}. {describe_tool_call(call)}")
    lines.append("")
    lines.append("回复 **y** 全部确认，**n** 全部拒绝；")
    lines.append("也可以逐个回复，例如 `y n y`，或回复要修改的序号。")
    return "\n".join(lines)


def build_approval_results(
    requests: DeferredToolRequests,
    decisions: Dict[str, ApprovalDecision]
) -> DeferredToolResults:
    """Construct DeferredToolResults from per-call decisions."""
    results = DeferredToolResults()
    for call in requests.approvals:
        decision = decisions.get(call.tool_call_id, False)
        if decision is True:
            results.approvals[call.tool_call_id] = ToolApproved()
        elif decision is False:
            results.approvals[call.tool_call_id] = ToolDenied(
                "用户拒绝了该操作。"
            )
        else:
            results.approvals[call.tool_call_id] = decision
    return results


def auto_approve_all(requests: DeferredToolRequests) -> DeferredToolResults:
    """Approve every pending call (for tests and offline evaluation only)."""
    results = DeferredToolResults()
    for call in requests.approvals:
        results.approvals[call.tool_call_id] = ToolApproved()
    return results


async def run_with_auto_approval(
    agent: Any,
    user_input: str,
    deps: Any,
    model: Any = None,
    model_settings: Optional[Dict[str, Any]] = None,
    message_history: Optional[list] = None
) -> Any:
    """Run an agent, automatically approving all write-tool calls.

    Intended for automated tests and evaluations; must never be used on a
    real user entry point.
    """
    result = await agent.run(
        user_input,
        deps=deps,
        model=model,
        model_settings=model_settings or {},
        message_history=message_history
    )

    rounds = 0
    while isinstance(result.output, DeferredToolRequests):
        rounds += 1
        if rounds > MAX_APPROVAL_ROUNDS:
            raise RuntimeError(
                "Auto approval exceeded the maximum number of rounds; "
                "the model may be stuck requesting write operations."
            )
        history = result.all_messages()
        approval_results = auto_approve_all(result.output)
        # No new user prompt: resume exactly where the run was suspended.
        result = await agent.run(
            None,
            deps=deps,
            model=model,
            model_settings=model_settings or {},
            message_history=history,
            deferred_tool_results=approval_results
        )

    return result
