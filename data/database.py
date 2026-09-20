import os
from typing import List, Optional
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from finance.models.transaction import Transaction 
from finance.models.enums import TransactionType, TransactionCategory
from finance.repositories.transaction_repository import TransactionRepository
from core.observability import log_and_handle_error
from postgrest.exceptions import APIError
from finance.models.budget import Budget
from finance.repositories.budget_repository import BudgetRepository

load_dotenv()


def _is_missing_relation_error(error: Exception) -> bool:
    if getattr(error, 'code', None) == 'PGRST205':
        return True
    text = str(error).lower()
    return 'pgrst205' in text or 'could not find the table' in text


class SupabaseBudgetRepository(BudgetRepository):
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not self.url or not self.key:
            self.supabase = None
        else:
            self.supabase: Client = create_client(self.url, self.key)

    def _check_client(self):
        if not self.supabase:
            raise ValueError("Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")

    @staticmethod
    def _map_to_domain(row: dict) -> Budget:
        allocations = row.get("allocations") or {}
        return Budget(
            id=row["id"],
            period=row["period"],
            monthly_income=float(row.get("monthly_income", 0) or 0),
            allocations={str(k): float(v) for k, v in allocations.items()},
            created_at=(
                datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                if row.get("created_at") else None
            )
        )

    @log_and_handle_error
    def get_for_period(self, period: str) -> Optional[Budget]:
        self._check_client()
        try:
            response = (
                self.supabase.table("budgets")
                .select("*")
                .eq("period", period)
                .limit(1)
                .execute()
            )
        except APIError as e:
            if _is_missing_relation_error(e):
                return None
            raise
        if not response.data:
            return None
        return self._map_to_domain(response.data[0])

    @log_and_handle_error
    def upsert(self, budget: Budget) -> Budget:
        self._check_client()
        data = {
            "period": budget.period,
            "monthly_income": budget.monthly_income,
            "allocations": budget.allocations,
        }
        response = (
            self.supabase.table("budgets")
            .upsert(data, on_conflict="period")
            .execute()
        )
        if response.data:
            return self._map_to_domain(response.data[0])
        return budget

    @log_and_handle_error
    def list_all(self) -> List[Budget]:
        self._check_client()
        response = (
            self.supabase.table("budgets")
            .select("*")
            .order("period", desc=True)
            .execute()
        )
        return [self._map_to_domain(item) for item in response.data]


class BaseSupabaseRepository:
    def __init__(self, table: str):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.table = table
        if not self.url or not self.key:
            self.supabase = None
        else:
            self.supabase: Client = create_client(self.url, self.key)
    
    def _check_client(self):
        if not self.supabase:
            raise ValueError("Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")

    def _map_to_domain(self, row: dict, default_type: TransactionType) -> Transaction:
        # Map source to description for income if present
        description = row.get("description", "")
        if "source" in row and row["source"]:
            description = row["source"]
            
        # Robustly handle missing 'type' or 'category' columns
        tx_type = default_type
        if "type" in row and row["type"]:
            try:
                tx_type = TransactionType(row["type"])
            except ValueError:
                pass
                
        tx_category = None
        if "category" in row and row["category"]:
            try:
                tx_category = TransactionCategory(row["category"])
            except ValueError:
                pass
        elif default_type == TransactionType.INCOME:
            tx_category = TransactionCategory.INCOME

        parsed_date = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
        # Normalize tz-aware (UTC) timestamps to naive local time so they are
        # comparable with the naive local datetimes used across the domain.
        if parsed_date.tzinfo is not None:
            parsed_date = parsed_date.astimezone().replace(tzinfo=None)

        return Transaction(
            id=row["id"],
            amount=row["amount"],
            type=tx_type,
            category=tx_category,
            description=description,
            date=parsed_date
    )

class SupabaseExpenseRepository(BaseSupabaseRepository, TransactionRepository):
    def __init__(self):
        super().__init__(table="expenses")

    @log_and_handle_error
    def add(self, tx: Transaction) -> Transaction:
        self._check_client()
        data = {
            "amount": tx.amount,
            "category": tx.category.value if tx.category else TransactionCategory.OTHER.value,
            "description": tx.description,
            "date": tx.date.isoformat()
        }
        response = self.supabase.table(self.table).insert(data).execute()
        if response.data:
            tx = tx.model_copy(update={"id": response.data[0]["id"]})
        return tx

    @log_and_handle_error
    def list_all(self) -> List[Transaction]:
        self._check_client()
        response = self.supabase.table(self.table).select("*").order("date", desc=True).execute()
        return [self._map_to_domain(item, TransactionType.EXPENSE) for item in response.data]

    @log_and_handle_error
    def list_by_type(self, transaction_type: TransactionType) -> List[Transaction]:
        if transaction_type != TransactionType.EXPENSE:
            return []
        return self.list_all()

    @log_and_handle_error
    def list_by_category(self, category: TransactionCategory) -> List[Transaction]:
        self._check_client()
        response = self.supabase.table(self.table).select("*").eq("category", category.value).order("date", desc=True).execute()
        return [self._map_to_domain(item, TransactionType.EXPENSE) for item in response.data]

    @log_and_handle_error
    def list_by_date_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Transaction]:
        self._check_client()
        query = self.supabase.table(self.table).select("*")
        if start_date:
            query = query.gte("date", start_date.isoformat())
        if end_date:
            query = query.lte("date", end_date.isoformat())
        response = query.order("date", desc=True).execute()
        return [self._map_to_domain(item, TransactionType.EXPENSE) for item in response.data]

    def total_amount(self, transaction_type: Optional[TransactionType] = None) -> float:
        if transaction_type and transaction_type != TransactionType.EXPENSE:
            return 0.0
        self._check_client()
        response = self.supabase.table(self.table).select("amount").execute()
        return sum(item["amount"] for item in response.data)

    def clear(self) -> None:
        self._check_client()
        self.supabase.table(self.table).delete().neq("id", 0).execute()

class SupabaseIncomeRepository(BaseSupabaseRepository, TransactionRepository):
    def __init__(self):
        super().__init__(table="income")

    @log_and_handle_error
    def add(self, tx: Transaction) -> Transaction:
        self._check_client()
        data = {
            "amount": tx.amount,
            "source": tx.description, # Map description to source for backwards compatibility/schema
            "description": tx.description,
            "date": tx.date.isoformat()
        }
        response = self.supabase.table(self.table).insert(data).execute()
        if response.data:
            tx = tx.model_copy(update={"id": response.data[0]["id"]})
        return tx

    @log_and_handle_error
    def list_all(self) -> List[Transaction]:
        self._check_client()
        response = self.supabase.table(self.table).select("*").order("date", desc=True).execute()
        return [self._map_to_domain(item, TransactionType.INCOME) for item in response.data]

    @log_and_handle_error
    def list_by_type(self, transaction_type: TransactionType) -> List[Transaction]:
        if transaction_type != TransactionType.INCOME:
            return []
        return self.list_all()

    @log_and_handle_error
    def list_by_category(self, category: TransactionCategory) -> List[Transaction]:
        if category != TransactionCategory.INCOME:
            return []
        return self.list_all()

    @log_and_handle_error
    def list_by_date_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Transaction]:
        self._check_client()
        query = self.supabase.table(self.table).select("*")
        if start_date:
            query = query.gte("date", start_date.isoformat())
        if end_date:
            query = query.lte("date", end_date.isoformat())
        response = query.order("date", desc=True).execute()
        return [self._map_to_domain(item, TransactionType.INCOME) for item in response.data]

    def total_amount(self, transaction_type: Optional[TransactionType] = None) -> float:
        if transaction_type and transaction_type != TransactionType.INCOME:
            return 0.0
        self._check_client()
        response = self.supabase.table(self.table).select("amount").execute()
        return sum(item["amount"] for item in response.data)

    def clear(self) -> None:
        self._check_client()
        self.supabase.table(self.table).delete().neq("id", 0).execute()

# Backwards compatibility alias if needed, though we should prefer the specific ones
class SupabaseTransactionRepository(SupabaseExpenseRepository):
    pass
