import asyncio
import os
from core.container import Container
from agents.finance import finance_agent
from finance.models.enums import TransactionCategory
from datetime import datetime
from core.settings import settings
from finance.utils.hitl import run_with_auto_approval

async def test_end_to_end():
    print("🚀 Starting End-to-End Agent Test (Domain-Driven)...")
    
    # 1. Setup Model
    env_provider = os.getenv('MODEL_PROVIDER')
    if env_provider:
        provider = env_provider
    elif os.getenv('GEMINI_API_KEY'):
        provider = 'gemini'
    elif os.getenv('OPENAI_API_KEY'):
        provider = 'openai'
    else:
        provider = 'ollama'
    
    model = settings.get_model(provider)
    print(f"🤖 Testing with provider: {provider}")

    deps = Container.get_finance_dependencies()
    
    # 2. Test Add Expense
    test_desc = f"Agent Test {datetime.now().strftime('%H:%M:%S')}"
    user_input = f"I spent $12.34 on {test_desc} in shopping category"
    
    print(f"🗣️ User: {user_input}")
    
    result = await run_with_auto_approval(
        finance_agent,
        user_input,
        model=model,
        deps=deps,
        model_settings={'temperature': 0.0}
    )

    print(f"🤖 Assistant: {result.output}")
    
    # Verify in DB
    expenses = deps.expense_repo.list_by_category(TransactionCategory.SHOPPING)
    found = any(e.description == test_desc and e.amount == 12.34 for e in expenses)
    
    if found:
        print("✅ Success: Expense recorded in Supabase by Agent!")
    else:
        print("❌ Failure: Expense not found in Supabase.")

    # 3. Test View History
    print("\n🗣️ User: Show my shopping expenses")
    result = await run_with_auto_approval(
        finance_agent,
        "Show my shopping expenses",
        model=model,
        deps=deps,
        model_settings={'temperature': 0.0}
    )
    print(f"🤖 Assistant: {result.output}")
    
    if str(12.34) in result.output and test_desc in result.output:
        print("✅ Success: Assistant correctly retrieved history from Supabase!")
    else:
        print("❌ Failure: Assistant failed to show the recorded expense.")

if __name__ == "__main__":
    asyncio.run(test_end_to_end())
