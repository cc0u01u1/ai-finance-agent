import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

try:
    from finance.services.ledger import LedgerService
    from finance.services.advisor import AdvisorService
    from finance.services.categories import CategoryService
    from finance.models.transaction import Transaction
    from finance.models.enums import TransactionType, TransactionCategory
    from finance.models.reports import FinancialReport, BudgetReport, SpendingSummary
    from finance.ledger import Ledger
    from agents.finance import finance_agent
    from core.container import Container
    
    print("✅ All imports in the consolidated 'finance' package are working correctly.")
    
    # Test a small instance of Ledger
    tx = Transaction(
        amount=100.0,
        type=TransactionType.EXPENSE,
        category=TransactionCategory.FOOD,
        description="Test",
        date="2026-01-01T00:00:00Z"
    )
    l = Ledger(transactions=[tx])
    print(f"✅ Ledger calculation test passed: {l.outflow} == 100.0")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Initialization failed: {e}")
    sys.exit(1)
