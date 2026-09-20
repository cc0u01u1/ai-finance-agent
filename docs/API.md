# API Reference

The Personal Finance Assistant exposes a web API via Pydantic AI's built-in web interface.

## Base URL

```
http://localhost:8000
```

## Interactive Documentation

Swagger UI is available at:

```
http://localhost:8000/docs
```

## Starting the API Server

```bash
make ui
# or
uv run uvicorn app:app --reload --port 8000
```

## Endpoints

### POST `/`

Main chat endpoint. Sends a user message to the router agent which delegates to the appropriate sub-agent (Finance or Strategy).

**Request Body:**

```json
{
  "message": "I spent $15 on lunch today"
}
```

**Response:**

```json
{
  "output": "Transaction recorded successfully..."
}
```

### GET `/`

Returns the web UI chat interface.

## Agent Routing

The router agent (`app.py:router_agent_web`) inspects user intent and delegates:

| User Intent | Target Agent | Tool Called |
|---|---|---|
| Expense tracking | Finance Agent | `ask_finance_global` |
| Income recording | Finance Agent | `ask_finance_global` |
| Transaction history | Finance Agent | `ask_finance_global` |
| Budget planning | Finance Agent | `ask_finance_global` |
| Financial advice | Strategy Agent | `ask_strategy_global` |
| Goal planning | Strategy Agent | `ask_strategy_global` |
| Ambiguous intent | Router asks for clarification | None |

## Finance Agent Tools

| Tool | Description | Parameters |
|---|---|---|
| `add_expense` | Record an expense | `amount` (float), `category` (str), `description` (str) |
| `add_income` | Record income | `amount` (float), `source` (str), `description` (str, optional) |
| `view_history` | Get transaction history | `category_name` (str, default: "all") |
| `get_financial_advice` | Analyze spending patterns | None |
| `get_budget_plan` | Generate budget from income | `monthly_income` (float) |

## Strategy Agent Tools

| Tool | Description | Parameters |
|---|---|---|
| `query_finance_assistant` | Delegate to Finance Agent for data | `query` (str) |
| `evaluate_goal_feasibility` | Assess financial goal viability | `goal_name` (str), `amount` (float) |

## Strategy Response Schema

The Strategy Agent returns structured output:

```json
{
  "analysis": "string - detailed analysis of the situation",
  "steps": ["string - array of actionable steps"],
  "confidence_score": "float - confidence between 0.0 and 1.0"
}
```

## Data Engineer Agent Tools

Available through the Director CLI (`run_director.py`), not the web API:

| Tool | Description | Parameters |
|---|---|---|
| `run_sql_query` | Execute read-only SQL | `query` (str) |
| `execute_ddl` | Execute schema changes | `query` (str), `justification` (str) |
| `execute_dml` | Execute data modifications | `query` (str) |
| `inspect_table_schema` | Get table column details | `table_name` (str) |
| `validate_financial_integrity` | Run data health checks | None |

## Error Responses

Errors are returned as plain text with a description:

```
Error: Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
```

Common error patterns:
- Database connection failures
- Missing environment variables
- LLM provider errors
- Invalid category mappings
