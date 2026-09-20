import random
from datetime import datetime, timedelta
from typing import List
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType, TransactionCategory
from core.container import Container

class DataSeeder:
    @staticmethod
    def seed_dummy_data(deps):
        """
        Seeds the database with realistic dummy data for the last 90 days.
        """
        if not deps:
            return False
            
        # 1. Clear existing data first? (Optional, but usually better for a clean seed)
        deps.expense_repo.clear()
        deps.income_repo.clear()
        
        current_date = datetime.now()
        
        # 2. Seed Income (Last 3 months)
        income_sources = [
            ("Main Salary", 5000, 1), # Monthly
            ("Freelance Project", 1200, 2), # Monthly
            ("Dividends", 150, 1) # Monthly
        ]
        
        for i in range(3):
            seed_date = (current_date - timedelta(days=i*30)).replace(day=1)
            for source, base_amount, _ in income_sources:
                amount = base_amount + random.uniform(-100, 100)
                tx = Transaction(
                    amount=amount,
                    type=TransactionType.INCOME,
                    category=TransactionCategory.INCOME,
                    description=source,
                    date=seed_date + timedelta(days=random.randint(0, 5))
                )
                deps.income_repo.add(tx)
        
        # 3. Seed Expenses (Daily/Weekly/Monthly)
        expense_templates = [
            ("Housing Rent", 1800, TransactionCategory.OTHER, "monthly"),
            ("Electricity Bill", 120, TransactionCategory.UTILITIES, "monthly"),
            ("Internet Fiber", 80, TransactionCategory.UTILITIES, "monthly"),
            ("Grocery Store", 150, TransactionCategory.FOOD, "weekly"),
            ("Restaurant Dinner", 80, TransactionCategory.ENTERTAINMENT, "weekly"),
            ("Gas Station", 60, TransactionCategory.TRANSPORT, "weekly"),
            ("Streaming Services", 45, TransactionCategory.ENTERTAINMENT, "monthly"),
            ("Gym Membership", 60, TransactionCategory.HEALTHCARE, "monthly"),
            ("AWS Cloud Bill", 25, TransactionCategory.OTHER, "monthly"),
            ("New Headphones", 250, TransactionCategory.SHOPPING, "once"),
            ("Car Insurance", 150, TransactionCategory.TRANSPORT, "monthly"),
            ("Doctor Visit", 120, TransactionCategory.HEALTHCARE, "once"),
        ]
        
        for i in range(90): # Last 90 days
            seed_date = current_date - timedelta(days=i)
            
            for desc, base_amount, cat, freq in expense_templates:
                should_add = False
                if freq == "monthly" and seed_date.day == random.randint(1, 5):
                    should_add = True
                elif freq == "weekly" and seed_date.weekday() == random.randint(0, 6):
                    should_add = True
                elif freq == "once" and random.random() < 0.02: # 2% chance daily
                    should_add = True
                
                if should_add:
                    amount = base_amount + random.uniform(-base_amount*0.1, base_amount*0.1)
                    tx = Transaction(
                        amount=round(amount, 2),
                        type=TransactionType.EXPENSE,
                        category=cat,
                        description=desc,
                        date=seed_date
                    )
                    deps.expense_repo.add(tx)
        
        return True
