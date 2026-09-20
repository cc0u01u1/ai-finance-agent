# Contributing Guide

## Project Structure

```
personal-finance-assistant/
├── agents/              # AI agent definitions
├── core/                # Configuration, DI container, observability
├── data/                # Database setup and repository implementations
├── finance/             # Domain layer (models, services, repositories)
├── prompts/             # Agent system prompts and personas
├── application/         # DTOs and application-layer types
├── tests/               # Test suite
├── docs/                # Documentation
├── app.py               # Pydantic AI web application
├── run_clerk.py         # Finance Clerk CLI entry point
├── run_director.py      # Wealth Director CLI entry point
└── streamlit_app.py     # Streamlit UI entry point
```

## Domain-Driven Design Conventions

This project follows DDD principles. Understanding these conventions is essential for contributing:

### Layered Architecture

1. **Domain Layer** (`finance/`) — Pure business logic, no external dependencies
   - Models are immutable Pydantic models (`ConfigDict(frozen=True)`)
   - Services contain business rules and calculations
   - Repositories define Protocol interfaces

2. **Infrastructure Layer** (`data/`) — External system implementations
   - Supabase implementations of repository protocols
   - Database connection management

3. **Application Layer** (`application/`) — Use cases and DTOs
   - Data transfer objects for agent outputs
   - Orchestrates domain services

4. **Interface Layer** (`agents/`, `app.py`, `streamlit_app.py`) — User-facing entry points
   - Agent definitions with tool bindings
   - Web and CLI interfaces

### Naming Conventions

| Layer | Convention | Example |
|---|---|---|
| Domain Models | PascalCase | `Transaction`, `FinancialReport` |
| Enums | PascalCase | `TransactionType`, `TransactionCategory` |
| Services | PascalCase + `Service` suffix | `LedgerService`, `AdvisorService` |
| Repositories | PascalCase + `Repository` suffix | `SupabaseExpenseRepository` |
| Agents | snake_case + `_agent` suffix | `finance_agent`, `strategy_agent` |
| Tools | snake_case | `add_expense`, `view_history` |
| DTOs | PascalCase | `StrategyResponse` |

### Immutability

All domain models should be immutable:

```python
class Transaction(BaseModel):
    model_config = ConfigDict(frozen=True)
    # ... fields
```

Use `model_copy(update={...})` for modifications instead of direct attribute assignment.

### Repository Protocol

New repository implementations must satisfy the `TransactionRepository` protocol:

```python
class TransactionRepository(Protocol):
    def add(self, transaction: Transaction) -> Transaction: ...
    def list_all(self) -> List[Transaction]: ...
    def list_by_type(self, transaction_type: TransactionType) -> List[Transaction]: ...
    def list_by_category(self, category: TransactionCategory) -> List[Transaction]: ...
    def list_by_date_range(self, start_date, end_date) -> List[Transaction]: ...
    def total_amount(self, transaction_type) -> float: ...
    def clear(self) -> None: ...
```

## Adding a New Agent

1. Create agent definition in `agents/`:

```python
# agents/my_agent.py
from pydantic_ai import Agent, RunContext
from core.dependencies import FinanceDependencies
from core.settings import settings

my_agent = Agent(
    model=settings.get_model(),
    deps_type=FinanceDependencies,
    system_prompt="Your system prompt here..."
)

@my_agent.tool
@log_and_handle_error
def my_tool(ctx: RunContext[FinanceDependencies], param: str) -> str:
    """Tool description for the LLM."""
    # Implementation
    return result
```

2. Register with the router (if needed) in `app.py`:

```python
@router_agent_web.tool
async def ask_my_agent(ctx: RunContext[None], query: str) -> str:
    async with track_agent_run("My Agent", str(settings.get_model()), {"query": query}):
        result = await my_agent.run(query, deps=deps)
        return result.output
```

3. Update `ARCHITECTURE.md` with the new agent's role.

## Adding a New Domain Model

1. Create model in `finance/models/`:

```python
# finance/models/my_model.py
from pydantic import BaseModel, ConfigDict

class MyModel(BaseModel):
    model_config = ConfigDict(frozen=True)
    field_one: str
    field_two: float
```

2. Export from `finance/models/__init__.py`

3. Add any associated services or repositories

## Adding a New Tool to an Agent

1. Add tool function with decorator in the agent file:

```python
@finance_agent.tool
@log_and_handle_error
def new_tool(ctx: RunContext[FinanceDependencies], param: str) -> str:
    """
    Clear description of what this tool does.
    The LLM reads this to decide when to call it.
    Args:
        param: Description of the parameter.
    """
    # Implementation
    return result
```

2. The tool description must be clear enough for the LLM to understand when to use it.

## Testing

```bash
# Run all tests
make test

# Run E2E tests
python tests/e2e_test.py

# Run evaluation
python tests/evaluate_agents.py

# Run structure check
python tests/check_structure_final.py
```

### Writing Tests

- E2E tests go in `tests/e2e_test.py`
- Unit tests for domain logic go in dedicated test files
- Use `TestModel` from `pydantic_ai.models.test` for mocking LLM responses
- Tests should not require real API keys

## Code Style

- No comments unless required for complex business logic
- Type hints on all function signatures
- Docstrings on public methods and tool functions
- Use `log_and_handle_error` decorator on agent tools
- Follow existing import ordering: stdlib → third-party → local

## Dependency Management

```bash
# Add a new dependency
uv add <package>

# Update dependencies
uv sync --upgrade

# Remove a dependency
uv remove <package>
```

All dependencies are managed via `pyproject.toml` and `uv.lock`.

## Pull Request Process

1. Create a feature branch from `main`
2. Implement changes following DDD conventions
3. Run `make lint` to verify syntax
4. Run `make test` to verify tests pass
5. Update documentation if adding new features
6. Submit PR with description of changes

## Commit Messages

Use conventional commits:

```
feat: add investment tracking agent
fix: correct budget calculation for negative income
docs: update architecture diagram
test: add E2E test for income recording
refactor: extract category mapping to service
```
