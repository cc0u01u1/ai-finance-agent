# Testing Guide

## Test Suite Overview

The project has four categories of tests:

| Test File | Purpose | Requires DB | Requires LLM |
|---|---|---|---|
| `check_structure_final.py` | Import verification and basic domain logic | No | No |
| `e2e_test.py` | End-to-end agent interaction testing | Yes | Yes |
| `evaluate_agents.py` | Agent evaluation with MLflow logging | Yes | Yes |
| `strategy_test.py` | Architecture verification | Yes | No (uses TestModel) |

## Running Tests

```bash
# Run full test suite
make test

# Run individual tests
python tests/e2e_test.py
python tests/evaluate_agents.py
python tests/check_structure_final.py
python tests/strategy_test.py

# Run MLflow UI to view results
make mlflow
# Open http://127.0.0.1:5001
```

## Test Categories

### Structure Tests (`check_structure_final.py`)

Validates that all imports resolve correctly and basic domain logic works:

- All finance package imports succeed
- Ledger model calculations produce correct results
- No runtime dependencies are missing

**Run these when:** You've refactored imports, moved files, or added new modules.

### End-to-End Tests (`e2e_test.py`)

Tests the full agent pipeline from user input to database persistence:

1. Configures the model provider
2. Sends a natural language expense to the Finance Agent
3. Verifies the expense was recorded in Supabase
4. Requests transaction history
5. Verifies the recorded expense appears in the output

**Prerequisites:**
- Supabase connection configured
- LLM provider accessible (Ollama, Gemini, or OpenAI)

**Run these when:** You've changed agent behavior, tool definitions, or database operations.

### Evaluation Tests (`tests/evaluate_agents.py`)

Runs a predefined set of queries against the Finance Agent and logs results to MLflow:

- Category mapping accuracy (e.g., "gas" → transport)
- Income recognition (e.g., "salary arrived" → income)
- Query handling (e.g., "How much spent on food?")

Results are logged as a table in MLflow for review.

**Prerequisites:**
- MLflow configured (default: SQLite)
- Supabase connection (optional, tests work with or without)
- LLM provider accessible

**Run these when:** You've modified system prompts, category mappings, or agent tools.

### Strategy Tests (`strategy_test.py`)

Verifies that the Strategy Agent architecture is sound:

- Module imports resolve
- Agent configuration is valid
- Dependencies inject correctly

Uses `TestModel` from Pydantic AI to avoid real LLM calls.

## Adding Tests

### Unit Tests for Domain Logic

Create test files alongside the module being tested:

```python
# finance/test_ledger.py
from finance.ledger import Ledger
from finance.models.transaction import Transaction
from finance.models.enums import TransactionType, TransactionCategory
from datetime import datetime

def test_net_cashflow():
    transactions = [
        Transaction(amount=5000, type=TransactionType.INCOME, description="Salary", date=datetime.now()),
        Transaction(amount=1500, type=TransactionType.EXPENSE, category=TransactionCategory.FOOD, description="Rent", date=datetime.now()),
    ]
    ledger = Ledger(transactions=transactions)
    assert ledger.net_cashflow == 3500.0
```

### Agent Tool Tests

Test individual tools without a real LLM using Pydantic AI's TestModel:

```python
from pydantic_ai.models.test import TestModel
from agents.finance import finance_agent
from core.container import Container

async def test_add_expense_tool():
    deps = Container.get_finance_dependencies()
    # TestModel handles tool invocation logic
    finance_agent.model = TestModel()
    result = await finance_agent.run("test query", deps=deps)
    # Assert expected behavior
```

### E2E Test Scenarios

Add new scenarios to `tests/e2e_test.py`:

```python
# Test income recording
user_input = "I received a salary of $5000"
result = await finance_agent.run(user_input, model=model, deps=deps)
incomes = deps.income_repo.list_all()
assert any(i.amount == 5000 for i in incomes)
```

## Test Data

### Seeding Data for Tests

```python
from finance.utils.seeder import DataSeeder

# Seed 90 days of realistic data
DataSeeder.seed_dummy_data(deps)
```

### Clearing Test Data

```python
deps.expense_repo.clear()
deps.income_repo.clear()
```

## Continuous Testing

Run `make lint` before committing to verify syntax:

```bash
make lint
# Checks: app.py, run_clerk.py, run_director.py, core/*.py, finance/*.py
```

## Test Environment

| Environment | Configuration |
|---|---|
| Local Development | `MODEL_PROVIDER=ollama` |
| CI/CD | Use `TestModel` to avoid real API calls |
| Staging | `MODEL_PROVIDER=gemini` with test Supabase project |
| Production | `MODEL_PROVIDER=gemini` or `openai` with production Supabase |

## Evaluation Metrics

When running evaluations, track:

- **Category accuracy** — Does "gas" map to transport?
- **Amount extraction** — Is $12.34 correctly parsed?
- **Intent classification** — Does the agent record vs. query appropriately?
- **Latency** — How long does each agent run take?
- **Error rate** — How often do agent runs fail?

All metrics are logged to MLflow automatically via the `track_agent_run` context manager.
