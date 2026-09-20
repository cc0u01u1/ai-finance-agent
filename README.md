# Personal Finance Assistant (Domain-Driven Edition)

A professional AI-powered expense tracking and financial insights agent built with **Pydantic AI** and **Supabase**. This agent leverages modern LLMs (**Ollama (Recommended)**, **Google Gemini**, **OpenAI**) to provide precise financial management through a natural language interface.

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Multi-agent system design, DDD layers, dependency injection |
| [API Reference](docs/API.md) | Web API endpoints, agent tools, request/response formats |
| [CLI Reference](docs/CLI.md) | Finance Clerk and Wealth Director CLI commands |
| [Database](docs/DATABASE.md) | Schema reference, repository layer, indexing |
| [Environment](docs/ENVIRONMENT.md) | Complete environment variable reference |
| [Security](docs/SECURITY.md) | Credential management, data privacy, deployment security |
| [Testing](docs/TESTING.md) | Test suite, evaluation, adding tests |
| [Observability](docs/OBSERVABILITY.md) | MLflow integration, tracing, evaluation workflow |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues, debug mode, getting help |
| [Contributing](docs/CONTRIBUTING.md) | DDD conventions, coding standards, PR process |
| [Improvements](docs/IMPROVEMENTS.md) | Best practice recommendations, tool upgrades, priority matrix |
| [Deployment](DEPLOYMENT.md) | Streamlit Cloud deployment guide |
| [Changelog](CHANGELOG.md) | Version history |

## Project Architecture

The project follows a Domain-Driven Design (DDD) approach to ensure maintainability and scalability.

```txt
personal-finance-assistant/
├── agents/             # Agent definitions (Finance, Strategy, Data Engineer)
├── core/               # Core configurations and observability (Settings, MLflow)
├── data/               # Data layer (Supabase Repositories, Migrations)
├── finance/            # Central Finance Package
│   ├── models/         # Domain Models (Transaction, Reports)
│   ├── services/       # Domain Services (Ledger, Advisor, Categories)
│   └── repositories/   # Repository Protocols
├── prompts/            # Professional financial personas & templates
├── tests/              # Test suite (E2E, Evaluation, Structural)
├── docs/               # Documentation
├── app.py              # Main Pydantic AI Web Application
├── run_clerk.py        # CLI Entry point for Finance Clerk
├── run_director.py     # CLI Entry point for Wealth Director
└── start_ui.sh         # Script to launch the Web UI
```

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Recommended)
- Python 3.12+
- A Supabase account and project
- API Keys for cloud LLM providers (Optional, Ollama recommended for local-first)

### Environment Setup

```bash
git clone <repo-url>
cd personal-finance-assistant
uv sync
```

### Database Configuration

1. Create a new project in [Supabase](https://supabase.com/).
2. Run the SQL provided in `data/setup.sql` in the Supabase SQL Editor to create the `expenses` and `income` tables.
3. Obtain your `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from the project settings.

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

See [Environment Reference](docs/ENVIRONMENT.md) for all available variables.

## Usage

Launch the agents using the provided `Makefile` shortcuts (powered by `uv`):

### Web Interface (Pydantic AI)

The built-in web interface with API documentation.

```bash
make ui
```

- **API/Swagger UI**: `http://localhost:8000/docs`

### Streamlit UI (Wealth OS Terminal)

Full analytics dashboard with visualizations.

```bash
make ui  # Note: same command, uses streamlit_app.py
```

### Finance Clerk (CLI)

Natural language expense and income tracking.

```bash
make clerk
```

### Wealth Director (CLI)

Long-term financial planning and strategy.

```bash
make director
```

See [CLI Reference](docs/CLI.md) for all commands and options.

## Example Queries

- **Record Expenses**: "I spent $15 on a burger today", "Paid $1200 for rent"
- **Record Income**: "My salary of $5000 arrived today", "Received a bonus of $500"
- **View History**: "Show my recent expenses", "How much did I spend on food?"
- **Financial Analysis**: "Analyze my spending habits"
- **Budgeting**: "Create a budget for a $6000 monthly income"

## Agent Capabilities

| Feature | Description |
|---|---|
| **Smart Ledger** | Automatically maps natural language to categories |
| **Income Tracking** | Record salary, bonuses, and deposits with source attribution |
| **History Views** | Filter and view transaction records directly from Supabase |
| **Spending Insights** | Identifies top spending categories and provides actionable advice |
| **Budget Planning** | Generates professional allocation plans based on income (50/30/20) |
| **Multi-Model Support** | Switch between local (Ollama) and cloud (Gemini, OpenAI) models |
| **Observability** | Full MLflow integration for tracing agent thoughts and evaluating performance |
| **Data Integrity** | SQL-level validation and schema management via Data Engineer Agent |

## Categories

The assistant automatically maps spending to these standard financial categories:

`food`, `transport`, `entertainment`, `utilities`, `healthcare`, `shopping`, `education`, `other`

## Observability & Evaluation (MLflow)

This project integrates **MLflow** for end-to-end tracing and agent evaluation.

```bash
# Run evaluations
make test

# View traces
make mlflow
# Open http://127.0.0.1:5001
```

See [Observability Guide](docs/OBSERVABILITY.md) for details.

## Testing

```bash
# Run test suite
make test

# Run E2E tests
python tests/e2e_test.py
```

See [Testing Guide](docs/TESTING.md) for the full test strategy.

## License

MIT. See [LICENSE](LICENSE) for details.
