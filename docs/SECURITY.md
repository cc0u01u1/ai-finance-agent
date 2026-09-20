# Security Guide

## Credential Management

### Supabase Service Role Key

The `SUPABASE_SERVICE_ROLE_KEY` provides **full administrative access** to your Supabase database, bypassing Row Level Security (RLS).

**Risks:**
- Anyone with this key can read, modify, or delete all data
- If exposed, an attacker has complete database control
- The key is used directly in the application (not proxied)

**Mitigations:**
- Never commit `.env` files to version control (already in `.gitignore`)
- Rotate keys periodically via Supabase Dashboard → Settings → API
- Use environment-specific keys (separate dev/prod projects)
- Consider implementing RLS policies even with service role key for defense in depth

### LLM API Keys

| Provider | Key | Exposure Risk |
|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | Low — rate-limited, no data access |
| OpenAI | `OPENAI_API_KEY` | Low — rate-limited, no data access |
| Ollama | `OLLAMA_API_KEY` | None when running locally |

**Best practices:**
- Use the minimum required API key scope
- Set usage limits in provider dashboards
- Monitor API usage for anomalous patterns

## Data Privacy

### Financial Data Storage

All financial data is stored in your own Supabase project. The project does not send financial data to any third party except:

1. **Supabase** — your chosen database provider
2. **LLM Provider** — user queries are sent to the configured LLM (Ollama/Gemini/OpenAI)

### Local-First Option

For maximum privacy, use Ollama locally:

```env
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
```

This ensures all LLM inference happens on your machine with no external API calls.

### Self-Hosted Database

For complete data sovereignty:
- Run a local PostgreSQL instance instead of Supabase
- Modify `data/database.py` to use a direct PostgreSQL connection
- Keep all data on-premises

## Input Validation

### Category Mapping

The `CategoryService` maps natural language to predefined categories. This prevents arbitrary category injection but relies on keyword matching, not LLM classification.

### SQL Injection Protection

The Data Engineer Agent has built-in safeguards:

1. **Read-only mode** — `run_sql_query` tool blocks DDL/DML statements
2. **Hardcoded safety rails** — prevents `DROP TABLE expenses` and `DROP TABLE income`
3. **Justification requirement** — DDL operations require a `justification` parameter

**Limitation:** These are string-based checks, not a full SQL parser. A determined user could bypass them.

## Deployment Security

### Streamlit Cloud

When deploying to Streamlit Cloud:
- Use Streamlit Secrets (Settings → Secrets) instead of `.env` files
- Never expose secrets in the repository
- Use a separate Supabase project for production

### Environment Exposure

The Streamlit System Security view (`streamlit_app.py:289-316`) allows runtime configuration of credentials. This is appropriate for single-user deployments but should be disabled or protected for multi-user scenarios.

## Key Rotation Procedure

1. Generate new key in provider dashboard
2. Update `.env` file with new key
3. Restart application
4. Delete old key from provider dashboard
5. Verify application functionality

### Supabase Key Rotation

1. Go to Supabase Dashboard → Settings → API
2. Generate new service role key
3. Update `SUPABASE_SERVICE_ROLE_KEY` in `.env`
4. Restart application
5. Revoke old key

## Audit Trail

MLflow tracks all agent runs including:
- Input queries
- Latency
- Errors

This provides a basic audit trail for debugging and compliance review. For production auditing, consider:
- Logging all database mutations to a separate audit table
- Using Supabase Realtime for change notifications
- Implementing immutable append-only ledger patterns

## Recommended Production Hardening

1. Enable Supabase Row Level Security (RLS)
2. Use a separate Supabase project for production
3. Implement API rate limiting on the web interface
4. Add authentication to the Streamlit app
5. Use HTTPS for all Ollama endpoints if remote
6. Regular dependency updates (`uv sync --upgrade`)
7. Database backups via Supabase automatic backups
