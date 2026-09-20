import asyncio
import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project imports
from agents.data_engineer import data_engineer_agent
from core.container import Container
from core.dependencies import FinanceDependencies, DataEngineDependencies
from agents.strategy import strategy_agent
from core.settings import settings

async def main():
    parser = argparse.ArgumentParser(description='Wealth Strategy Advisor')
    parser.add_argument('--model', type=str, choices=['ollama', 'openai', 'gemini', 'google'],
                      help='Model provider to use (overrides MODEL_PROVIDER env var)')
    parser.add_argument('command', type=str, nargs='?', help='Optional command to execute directly')
    args = parser.parse_args()

    # Resolve Model
    provider = args.model or settings.MODEL_PROVIDER
    model = settings.get_model(provider)

    print("=" * 60)
    print("📈 Wealth Strategy Director (Multi-Agent Edition)")
    print("=" * 60)
    print(f"\n🧠 Director Provider: {provider.capitalize()}")
    print("\nI oversee your long-term wealth. I can:\n"
          "  • Plan large purchases     (e.g., 'Can I buy a Tesla? Check my history')\n"
          "  • Debt strategies          (e.g., 'How do I pay off my credit card?')\n"
          "  • Investment advice        (e.g., 'Where should I put my extra $500?')\n"
          "  • Complex Goal Planning    (e.g., 'Save $100k for a house in 5 years')\n")
    print("Type 'quit' or 'exit' to end the session.\n")

    # Initialize Director
    class Director:
        async def route_request(self, user_input: str):
            # Simple keyword routing
            if any(k in user_input.lower() for k in ["sql", "schema", "table", "database", "migration"]):
                print("🔧 Director: Routing to Data Engineer...")
                try:
                    deps = await Container.get_data_dependencies()
                    return await data_engineer_agent.run(user_input, deps=deps)
                except Exception as e:
                    return f"❌ Data Agent Error: {str(e)}"
            
            else:
                print("💼 Director: Routing to Strategy Boardroom...")
                # Strategy agent needs basic deps
                deps = Container.get_finance_dependencies()
                return await strategy_agent.run(user_input, deps=deps)

    director = Director()

    if args.command:
        result = await director.route_request(args.command)
        if hasattr(result, 'data'):
            print(f"\n🚀 Output:\n{result.data}")
        elif hasattr(result, 'output'): # StrategyResponse
             print(f"\n🚀 Output:\n{result.output}")
        else:
             print(f"\n🚀 Output:\n{result}")
        
    else:
        # Interactive mode
        print("👔 Director Online. Type 'quit' to exit.")
        while True:
            user_input = input("\nExplain your goal: ")
            if user_input.lower() in ['quit', 'exit']:
                break
            
            try:
                result = await director.route_request(user_input)
                # Handle different output types from different agents
                if hasattr(result, 'data'):
                    print(f"\n🔧 Data Engineer Report:\n{result.data}")
                elif hasattr(result, 'output'):
                     # StrategyResponse object
                     output = result.output 
                     if hasattr(output, 'analysis'):
                        print(f"\n🏆 STRATEGIC ANALYSIS")
                        print(f"{'-'*20}")
                        print(f"{output.analysis}")
                        print(f"\n✅ ACTION STEPS:")
                        for i, step in enumerate(output.steps, 1):
                            print(f"  {i}. {step}")
                        print(f"\n📊 Confidence: {output.confidence_score * 100:.1f}%")
                     else:
                        print(f"\n🚀 Output:\n{output}")
                else:
                    print(f"\n🚀 Output:\n{result}")

            except Exception as e:
                print(f"❌ Error during execution: {e}")
                import traceback
                traceback.print_exc()

    await Container.close()

if __name__ == "__main__":
    asyncio.run(main())
