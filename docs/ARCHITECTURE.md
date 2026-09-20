# Architecture Guide

## Overview

This project follows Domain-Driven Design (DDD) principles with a multi-agent architecture. Three specialized AI agents coordinate to provide comprehensive financial management capabilities, all backed by Supabase for persistent storage.

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Streamlit│  │ Pydantic │  │   CLI    │              │
│  │   App    │  │  AI Web  │  │ (Clerk/  │              │
│  │          │  │          │  │ Director)│              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │              │              │                   │
│  ┌────┴──────────────┴──────────────┴─────┐             │
│  │          Agent Layer                    │             │
│  │                                         │             │
│  │  ┌──────────┐    ┌──────────────────┐  │             │
│  │  │  Router  │───▶│ Finance Agent    │  │             │
│  │  │  Agent   │    │ (expense/income/ │  │             │
│  │  │          │    │  budget/history) │  │             │
│  │  └────┬─────┘    └──────────────────┘  │             │
│  │       │                                 │             │
│  │       │    ┌──────────────────┐         │             │
│  │       └───▶│ Strategy Agent   │         │             │
│  │            │ (planning/goals/ │         │             │
│  │            │  analysis)       │         │             │
│  │            └────────┬─────────┘         │             │
│  │                     │                   │             │
│  │            ┌────────┴─────────┐         │             │
│  │            │ Data Engineer    │         │             │
│  │            │ (SQL/schema/DDL) │         │             │
│  │            └──────────────────┘         │             │
│  └─────────────────────────────────────────┘             │
│                           │                               │
│  ┌────────────────────────┴─────────────────────┐        │
│  │              Core Services                    │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │        │
│  │  │ Settings │ │Container │ │Observability │ │        │
│  │  │ (Model   │ │(Dep.     │ │(MLflow       │ │        │
│  │  │  Config) │ │ Inject)  │ │ Tracking)    │ │        │
│  │  └──────────┘ └──────────┘ └──────────────┘ │        │
│  └──────────────────────────────────────────────┘        │
│                           │                               │
│  ┌────────────────────────┴─────────────────────┐        │
│  │           Finance Domain                      │        │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │        │
│  │  │  Models  │ │ Services │ │ Repositories │ │        │
│  │  │(Txn,     │ │(Ledger,  │ │(Protocol     │ │        │
│  │  │ Reports) │ │ Advisor) │ │ + Supabase)  │ │        │
│  │  └──────────┘ └──────────┘ └──────────────┘ │        │
│  └──────────────────────────────────────────────┘        │
└───────────────────────────┬──────────────────────────────┘
                            │
                    ┌───────┴───────┐
                    │   Supabase    │
                    │  (PostgreSQL) │
                    └───────────────┘
```

## Agent Architecture

### 1. Router Agent (`app.py`)

**Role:** Intent classifier and dispatcher

**Responsibility:** Determines whether a user request should go to the Finance Agent (transactions, history, budgets) or Strategy Agent (advice, planning, goals).

**Tools:**
- `ask_finance_global` → delegates to Finance Agent
- `ask_strategy_global` → delegates to Strategy Agent

### 2. Finance Agent (`agents/finance.py`)

**Role:** Transaction recording and financial data operations

**Responsibility:** Handles all CRUD operations on the financial ledger, spending analysis, and budget generation.

**Tools:**
- `add_expense` — records expense with category mapping
- `add_income` — records income with source attribution
- `view_history` — retrieves formatted transaction history
- `get_financial_advice` — analyzes spending patterns
- `get_budget_plan` — generates 50/30/20 budget allocation

**Dependencies:** `FinanceDependencies` (expense_repo, income_repo)

### 3. Strategy Agent (`agents/strategy.py`)

**Role:** High-level financial planning and analysis

**Responsibility:** Provides strategic financial advice, goal feasibility assessment, and coordinates with the Finance Agent for underlying data.

**Tools:**
- `query_finance_assistant` — delegates to Finance Agent for data
- `evaluate_goal_feasibility` — assesses financial goal viability

**Output:** Structured `StrategyResponse` (analysis, steps, confidence_score)

**Dependencies:** `FinanceDependencies` (expense_repo, income_repo)

### 4. Data Engineer Agent (`agents/data_engineer.py`)

**Role:** Database administration and schema management

**Responsibility:** Safe SQL query execution, DDL/DML operations, schema inspection, and data integrity validation.

**Tools:**
- `run_sql_query` — read-only SELECT queries
- `execute_ddl` — schema modifications (CREATE, ALTER, DROP)
- `execute_dml` — data modifications (INSERT, UPDATE, DELETE)
- `inspect_table_schema` — table column inspection
- `validate_financial_integrity` — data health checks

**Dependencies:** `DataEngineDependencies` (asyncpg connection pool)

**Safety:** Blocks destructive queries against core tables; separates read/write operations.

## Dependency Injection

The project uses a container-based dependency injection pattern:

```python
# Container manages singleton dependencies
class Container:
    _finance_deps: Optional[FinanceDependencies] = None
    _db_pool: Optional[asyncpg.Pool] = None

    @classmethod
    def get_finance_dependencies(cls) -> FinanceDependencies:
        # Returns cached or newly created deps
        ...

    @classmethod
    async def get_data_dependencies(cls) -> DataEngineDependencies:
        # Returns asyncpg pool for Data Engineer
        ...
```

**FinanceDependencies:**
- `expense_repo: TransactionRepository` — SupabaseExpenseRepository
- `income_repo: TransactionRepository` — SupabaseIncomeRepository

**DataEngineDependencies:**
- `pool: asyncpg.Pool` — native PostgreSQL connection pool

## Domain Layer (`finance/`)

### Models
- `Transaction` — immutable Pydantic model for income/expense records
- `TransactionType` — enum (INCOME, EXPENSE)
- `TransactionCategory` — enum (food, transport, entertainment, etc.)
- `FinancialReport` — spending analysis output
- `BudgetReport` — 50/30/20 budget allocation
- `SpendingSummary` — per-category summary
- `FinancialGoal` — goal tracking model

### Services
- `LedgerService` — transaction recording and history formatting
- `AdvisorService` — spending analysis and budget advice
- `CategoryService` — keyword-based category mapping

### Repositories
- `TransactionRepository` — Protocol defining the repository interface
- `SupabaseExpenseRepository` — Supabase implementation for expenses
- `SupabaseIncomeRepository` — Supabase implementation for income

### Domain Utilities
- `Ledger` — aggregate cash flow calculations (inflow, outflow, burn rate, runway)
- `CashFlow` — simple inflow/outflow model
- `budget_drift()` — planned vs actual variance calculation
- `spending_volatility()` — standard deviation of spending amounts
- `concentration_hhi()` — Herfindahl-Hirschman Index for spending concentration

## Observability

All agent runs are tracked via MLflow:
- Latency metrics
- Input parameters
- Error tracking
- Output logging

See [OBSERVABILITY.md](./OBSERVABILITY.md) for details.

## Communication Patterns

### Agent-to-Agent Delegation

```
User → Router Agent → Finance Agent → Supabase → Response
                  ↘ Strategy Agent → Finance Agent → Supabase → Response
                  ↘ Data Engineer → PostgreSQL (direct) → Response
```

### Dependency Flow

```
Container → FinanceDependencies → Finance/Strategy Agents
Container → DataEngineDependencies → Data Engineer Agent
```

### Strategy Agent → Finance Agent

The Strategy Agent calls `query_finance_assistant` which invokes the Finance Agent with the same `deps` and `model`, ensuring consistent behavior and shared database context.
