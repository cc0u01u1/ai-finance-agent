from typing import List, Optional
from datetime import datetime
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType, TransactionCategory
from finance.repositories.transaction_repository import TransactionRepository
from finance.ledger import Ledger

class LedgerService:
    def __init__(self, expense_repo: TransactionRepository, income_repo: TransactionRepository):
        self.expense_repo = expense_repo
        self.income_repo = income_repo
    
    def record_expense(self, amount: float, category: TransactionCategory, description: str) -> Transaction:
        """
        Record a new expense.
        """
        expense = Transaction(
            amount=amount, 
            category=category, 
            description=description, 
            type=TransactionType.EXPENSE, 
            date=datetime.now()
        )
        return self.expense_repo.add(expense)

    def record_income(self, amount: float, source: str, description: str = "") -> Transaction:
        """
        Record a new income.
        """
        # Combine source and description for the Transaction model if needed, 
        # or just use source as description.
        full_desc = f"{source}: {description}" if description else source
        income = Transaction(
            amount=amount,
            category=TransactionCategory.INCOME,
            description=full_desc,
            type=TransactionType.INCOME,
            date=datetime.now()
        )
        return self.income_repo.add(income)

    def get_transaction_history(self, category: Optional[TransactionCategory] = None) -> List[Transaction]:
        """
        Fetch combined history of income and expenses.
        """
        if category:
            if category == TransactionCategory.INCOME:
                return self.income_repo.list_all()
            return self.expense_repo.list_by_category(category)
        
        expenses = self.expense_repo.list_all()
        income = self.income_repo.list_all()
        
        all_tx = expenses + income
        all_tx.sort(key=lambda x: x.date, reverse=True)
        return all_tx

    def calculate_total_spending(self, transactions: List[Transaction]) -> float:
        """Sum of EXPENSES only from a list of transactions."""
        return sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)

    def calculate_total_income(self, transactions: List[Transaction]) -> float:
        """Sum of INCOME only from a list of transactions."""
        return sum(t.amount for t in transactions if t.type == TransactionType.INCOME)

    def format_history_report(self, category: Optional[TransactionCategory], transactions: List[Transaction]) -> str:
        if not transactions:
            cat_name = category.value if category else 'all categories'
            return f"No records found for {cat_name}."

        title = f"LEDGER REPORT: {category.value.upper() if category else 'ALL TRANSACTIONS'}"
        report = f"{'='*40}\n{title}\n{'='*40}\n"
        
        for t in transactions:
            date_str = t.date.strftime('%Y-%m-%d')
            prefix = "+" if t.type == TransactionType.INCOME else "-"
            cat_label = t.category.value if t.category else "N/A"
            report += f"[{date_str}] {prefix} ${t.amount:>8.2f} | {cat_label:12} | {t.description}\n"
            
        ledger = Ledger(transactions=transactions)
        total_spent = ledger.outflow
        total_income = ledger.inflow
        net_flow = ledger.net_cashflow
        
        report += f"{'-'*40}\n"
        report += f"TOTAL INCOME:   ${total_income:>10.2f}\n"
        report += f"TOTAL SPENDING: ${total_spent:>10.2f}\n"
        report += f"NET FLOW:       ${net_flow:>10.2f}\n"
        report += f"{'='*40}"
        return report
