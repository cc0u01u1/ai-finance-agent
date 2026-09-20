# Troubleshooting Guide

## Common Issues

### Database Connection Errors

**Error:** `Supabase is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY`

**Fix:**
1. Copy `.env.example` to `.env`: `cp .env.example .env`
2. Fill in your Supabase URL and service role key
3. Restart the application

**Error:** `Connection refused` or `timeout`

**Fix:**
- Verify your Supabase project is active (not paused)
- Check that `SUPABASE_URL` is the REST API URL (not the database URL)
- Ensure `SUPABASE_SERVICE_ROLE_KEY` is the service role key (not the anon key)

### LLM Provider Errors

**Error:** `Model provider not found` or connection refused to Ollama

**Fix:**
- Verify Ollama is running: `ollama list`
- Check `OLLAMA_BASE_URL` points to the correct endpoint
- For local Ollama: `http://localhost:11434/v1`
- For remote Ollama: ensure the URL is publicly accessible (localhost won't work on Streamlit Cloud)

**Error:** `Invalid API key` for Gemini or OpenAI

**Fix:**
- Verify the API key is correct and active
- Check provider dashboard for key status and usage limits
- Ensure `MODEL_PROVIDER` matches the configured key

**Error:** Ollama model not found

**Fix:**
- Pull the model: `ollama pull llama3.2`
- Or change `OLLAMA_MODEL` in `.env` to an available model

### Agent Errors

**Error:** Agent responds with incorrect categories

**Fix:**
- Check `CategoryService.map_to_category()` mappings in `finance/services/categories.py`
- Add missing keywords to the mappings dictionary
- Or switch to a more capable LLM model

**Error:** Agent doesn't record transactions

**Fix:**
- Verify database connection is working
- Check that the agent has the correct `deps` injected
- Review MLflow traces for tool call failures

**Error:** Strategy Agent returns raw JSON instead of formatted output

**Fix:**
- This is expected behavior — the Strategy Agent outputs structured `StrategyResponse`
- The Director CLI (`run_director.py`) handles formatting automatically
- If using the web API, you'll receive the raw JSON

### Streamlit UI Issues

**Error:** `Critical System Error` on startup

**Fix:**
- Check database configuration in System Security tab
- Verify environment variables are set
- Restart the Streamlit server

**Error:** Currency selector not persisting

**Fix:**
- Currency is stored in `st.session_state`
- Resetting the session clears it
- Select the currency again after reset

**Error:** Charts not rendering

**Fix:**
- Ensure there is transaction data in the database
- Use the Data Seeder to generate test data
- Check that Plotly is installed: `uv sync`

### MLflow Issues

**Error:** MLflow UI not starting

**Fix:**
- Check port 5001 is not in use: `lsof -i :5001`
- Try a different port: `uv run mlflow ui --port 5002`
- Verify `mlflow` is installed: `uv sync`

**Error:** Traces not appearing

**Fix:**
- Check `MLFLOW_TRACKING_URI` is correct
- Verify the `track_agent_run` context manager is being used
- Check MLflow experiment name matches

### Dependency Issues

**Error:** `ModuleNotFoundError`

**Fix:**
- Run `uv sync` to install dependencies
- Ensure you're using `uv run` to execute commands (not bare `python`)
- Check `.python-version` matches your installed Python

**Error:** `ImportError` after refactoring

**Fix:**
- Run `python tests/check_structure_final.py` to verify all imports
- Clear Python cache: `make clean`
- Ensure `__init__.py` files exist in all packages

### Deployment Issues (Streamlit Cloud)

**Error:** App fails to deploy

**Fix:**
- Verify `streamlit_app.py` is the entry point
- Ensure all dependencies are in `pyproject.toml`
- Check Streamlit Cloud can access your repository

**Error:** Secrets not loading

**Fix:**
- Go to Settings → Secrets in Streamlit dashboard
- Paste `.env` values in TOML format (see DEPLOYMENT.md)
- Redeploy after updating secrets

**Error:** Ollama doesn't work on Streamlit Cloud

**Fix:**
- Ollama must be accessible via a public URL
- Switch to Gemini or OpenAI for cloud deployments
- Set `MODEL_PROVIDER=gemini` in secrets

## Debug Mode

Enable verbose logging:

```python
# In core/observability.py, change logging level:
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
```

## Getting Help

1. Check MLflow traces for detailed error information
2. Review the test suite output: `make test`
3. Verify environment configuration: `ENVIRONMENT.md`
4. Check database connectivity with Data Engineer Agent
