# Environment Variables Reference

Complete reference for all environment variables used by the project.

## Required Variables

| Variable | Description | Example |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | `https://abc123.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (admin access) | `eyJ...` |

## Model Provider

| Variable | Description | Default | Options |
|---|---|---|---|
| `MODEL_PROVIDER` | Default LLM provider | `ollama` | `ollama`, `gemini`, `openai` |

## Ollama (Local LLM)

| Variable | Description | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | Model name to use | `llama3.2` |
| `OLLAMA_API_KEY` | API key for Ollama (optional) | — |

**Note:** When using Ollama Cloud (`ollama.com`), ensure the URL ends with `/v1`:
```
OLLAMA_BASE_URL=https://ollama.com/v1
```

## Google Gemini

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key | — |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.0-flash` |

`GOOGLE_API_KEY` is also accepted as an alternative to `GEMINI_API_KEY`.

## OpenAI

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o` |

## MLflow (Observability)

| Variable | Description | Default |
|---|---|---|
| `MLFLOW_TRACKING_URI` | MLflow tracking backend URI | `sqlite:///mlflow.db` |
| `MLFLOW_EXPERIMENT_NAME` | Experiment name for tracking | `Personal Finance Assistant` |

## Data Engineer (Native PostgreSQL)

| Variable | Description | Required For |
|---|---|---|
| `SUPABASE_DB_URL` | Native PostgreSQL connection string | Data Engineer Agent |

**Format:**
```
postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

Obtain this from Supabase Dashboard → Settings → Database → Connection string → Direct connection.

## Complete `.env` Example

```env
# Model Provider
MODEL_PROVIDER=ollama

# Ollama (local development)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2
OLLAMA_API_KEY=

# Google Gemini (cloud)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash

# OpenAI (cloud)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o

# Supabase (required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Supabase native connection (for Data Engineer)
SUPABASE_DB_URL=postgresql://postgres.xxx:password@aws-0-xx.pooler.supabase.com:6543/postgres

# MLflow
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MLFLOW_EXPERIMENT_NAME=Personal Finance Assistant
```

## Model Provider Priority

The system resolves the model provider in this order:

1. CLI `--model` flag (highest priority)
2. `MODEL_PROVIDER` environment variable
3. Defaults to `ollama`

## Switching Providers at Runtime

```bash
# Use Gemini
MODEL_PROVIDER=gemini make clerk

# Use OpenAI
MODEL_PROVIDER=openai make director

# Override via CLI flag
make clerk -- --model gemini
```
