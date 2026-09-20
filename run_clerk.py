import asyncio
import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project imports
from core.container import Container, create_finance_agent
from core.settings import settings
from core.observability import track_agent_run, log_agent_result
from pydantic_ai import DeferredToolRequests
from finance.utils.hitl import (
    describe_tool_call, build_approval_results, MAX_APPROVAL_ROUNDS
)


def _collect_approval_decisions(pending):
    """Interactively collect a y/n decision for every pending call."""
    print(f"\n📋 管家准备执行 {len(pending)} 个操作，请确认：")
    for index, call in enumerate(pending, start=1):
        print(f"   {index}. {describe_tool_call(call)}")
    print("   （提示：可先输入 a 全部确认，或 r 全部拒绝）")

    decisions = {}
    for call in pending:
        while True:
            choice = input(f"   操作确认 [{call.tool_name}] (y/n): ").strip().lower()
            if choice in ("y", "yes", "a"):
                decisions[call.tool_call_id] = True
                break
            if choice in ("n", "no", "r"):
                decisions[call.tool_call_id] = False
                break
            print("   请输入 y 或 n。")
    return decisions


async def main():
    parser = argparse.ArgumentParser(description='Personal Finance Assistant')
    parser.add_argument('--model', type=str, choices=['ollama', 'openai', 'gemini', 'google'],
                      help='Model provider to use (overrides MODEL_PROVIDER env var)')
    args = parser.parse_args()

    # Domain models and services
    try:
        deps = Container.get_finance_dependencies()
    except Exception as e:
        print(f"❌ Database Error: {str(e)}")
        sys.exit(1)

    # Resolve Model
    provider = args.model or settings.MODEL_PROVIDER
    model = settings.get_model(provider)

    print("=" * 60)
    print("💰 Personal Finance Assistant (Domain-Driven Edition)")
    print("=" * 60)
    print(f"\n🤖 Provider: {provider.capitalize()}")
    print("\nI can help you:\n"
          "  • Track expenses           (e.g., 'I spent $15 on lunch')\n"
          "  • Record income            (e.g., 'Salary $5000 received')\n"
          "  • View spending            (e.g., 'Show my food expenses')\n"
          "  • Get expert advice        (e.g., 'Analyze my spending')\n"
          "  • Budgeting plans          (e.g., 'Budget for $5000 income')\n")
    print("Type 'quit' or 'exit' to end the session.\n")

    history = []

    while True:
        try:
            user_input = input("🗣️  You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Stay financially healthy. Goodbye!")
                break

            # Execute Request
            # We pass the pre-resolved model object to ensure correctness
            async with track_agent_run("Finance Clerk CLI", str(provider), {"query": user_input}):
                finance_agent = create_finance_agent()
                result = await finance_agent.run(
                    user_input,
                    model=model,
                    deps=deps,
                    message_history=history,
                    model_settings={'temperature': 0.0}
                )

                # Human-in-the-loop: approve/deny write operations
                approval_rounds = 0
                while isinstance(result.output, DeferredToolRequests):
                    approval_rounds += 1
                    if approval_rounds > MAX_APPROVAL_ROUNDS:
                        raise RuntimeError("确认轮次超出上限，已中止以防死循环。")

                    decisions = _collect_approval_decisions(result.output.approvals)
                    approval_results = build_approval_results(result.output, decisions)
                    resume_history = result.all_messages()

                    # Resume the run with the user's decisions (no new prompt)
                    result = await finance_agent.run(
                        None,
                        model=model,
                        deps=deps,
                        message_history=resume_history,
                        deferred_tool_results=approval_results,
                        model_settings={'temperature': 0.0}
                    )

                log_agent_result(result.output)

            # Update conversation history
            history = result.all_messages()
            print(f"\n🤖 Assistant: {result.output}")

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Please try again or type 'quit' to exit.")

if __name__ == "__main__":
    asyncio.run(main())
