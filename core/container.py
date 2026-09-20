from typing import Optional
from core.settings import settings
from core.dependencies import FinanceDependencies, DataEngineDependencies
import asyncpg
import asyncio
import os
from data.database import (
    SupabaseExpenseRepository,
    SupabaseIncomeRepository,
    SupabaseBudgetRepository,
)
from pydantic_ai import Agent

class Container:
    _finance_deps: Optional[FinanceDependencies] = None
    _db_pool: Optional[asyncpg.Pool] = None

    @classmethod
    def get_finance_dependencies(cls) -> FinanceDependencies:
        """
        Factory to get the configured dependencies.
        """
        if not cls._finance_deps:
            cls._finance_deps = FinanceDependencies(
                expense_repo=SupabaseExpenseRepository(),
                income_repo=SupabaseIncomeRepository(),
                budget_repo=SupabaseBudgetRepository()
            )
        return cls._finance_deps

    @classmethod
    def reset_dependencies(cls):
        """
        Clear the cached dependencies to force re-initialization.
        """
        cls._finance_deps = None

    @classmethod
    async def get_db_pool(cls):
        if not cls._db_pool:
            # Requires native connection string (not REST URL)
            db_url = os.getenv("SUPABASE_DB_URL") 
            if not db_url:
                raise ValueError("SUPABASE_DB_URL is required for Data Engineer Agent.")
            
            cls._db_pool = await asyncpg.create_pool(db_url)
        return cls._db_pool
    
    @classmethod
    async def get_data_dependencies(cls) -> DataEngineDependencies:
        pool = await cls.get_db_pool()
        return DataEngineDependencies(pool=pool)
        
    @classmethod
    async def close(cls):
        if cls._db_pool:
            await cls._db_pool.close()
            cls._db_pool = None

def create_finance_agent(model_override: str = None) -> Agent:
    """
    Factory to create a configured Finance Agent.
    """
    from agents.finance import finance_agent
    
    # Configure the model from settings
    model = settings.get_model(model_override)
    finance_agent.model = model
    
    return finance_agent
