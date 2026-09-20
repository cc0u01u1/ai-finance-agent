# CLI Reference

The project provides two CLI entry points for different financial management roles.

## Finance Clerk (`run_clerk.py`)

Natural language expense and income tracking with a conversational interface.

### Starting

```bash
make clerk
# or
uv run python run_clerk.py
```

### Options

| Flag | Description | Example |
|---|---|---|
| `--model` | Override LLM provider | `--model gemini` |

**Valid providers:** `ollama`, `openai`, `gemini`, `google`

### Supported Commands

Speak naturally — the agent interprets your intent:

| User Input | Action |
|---|---|
| "I spent $15 on lunch" | Records $15 expense in food category |
| "Paid $1200 for rent" | Records $1200 expense in utilities |
| "My salary of $5000 arrived" | Records $5000 income |
| "Show my recent expenses" | Displays transaction history |
| "How much did I spend on food?" | Shows food category spending |
| "Analyze my spending habits" | Provides spending analysis |
| "Create a budget for $6000 income" | Generates 50/30/20 budget plan |

### Exit

Type `quit`, `exit`, or `bye` to end the session.

## Wealth Director (`run_director.py`)

Strategic financial planning with multi-agent coordination. Routes requests between the Strategy Agent (planning) and Data Engineer Agent (database operations).

### Starting

```bash
make director
# or
uv run python run_director.py
```

### Options

| Flag | Description | Example |
|---|---|---|
| `--model` | Override LLM provider | `--model openai` |
| `command` | Single command execution (non-interactive) | `run_director.py "Can I buy a house?"` |

### Routing Logic

The Director uses keyword-based routing:

| Keywords in Query | Routes To |
|---|---|
| `sql`, `schema`, `table`, `database`, `migration` | Data Engineer Agent |
| Everything else | Strategy Agent |

### Strategy Agent Capabilities

- Financial goal planning
- Debt reduction strategies
- Investment advice
- Large purchase feasibility
- Long-term wealth planning

**Output format:** Structured analysis with actionable steps and confidence score.

### Data Engineer Agent Capabilities

- Execute read-only SQL queries
- Inspect table schemas
- Execute DDL (schema changes) with justification
- Execute DML (data modifications)
- Validate financial data integrity

### Exit

Type `quit` or `exit` to end the session.

## Makefile Commands

| Command | Description |
|---|---|
| `make help` | Show all available commands |
| `make install` | Install dependencies via `uv sync` |
| `make clean` | Remove cache and build artifacts |
| `make ui` | Launch Streamlit UI |
| `make clerk` | Launch Finance Clerk CLI |
| `make director` | Launch Wealth Director CLI |
| `make mlflow` | Launch MLflow tracking UI (port 5001) |
| `make test` | Run test suite via pytest |
| `make lint` | Run syntax and static analysis |
| `make docker-build` | Build Docker image |

## Shell Script

| Script | Description |
|---|---|
| `start_ui.sh` | Launch Pydantic AI web UI via uvicorn on port 8000 |

## Examples

### Start Finance Clerk with Gemini

```bash
make clerk -- --model gemini
```

### Run Director with a single command

```bash
uv run python run_director.py "Should I invest $500 in index funds?"
```

### Start web UI on custom port

```bash
uv run uvicorn app:app --reload --port 9000
```

### View API documentation

```bash
make ui
# Then open http://localhost:8000/docs
```
