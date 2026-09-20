# Observability Guide

## MLflow Integration

The project uses MLflow for end-to-end agent run tracking, providing visibility into agent behavior, performance, and errors.

## What Is Tracked

### Per-Run Metrics

| Metric | Description |
|---|---|
| `latency` | Total agent run duration in seconds |
| `success` | 1 for success, 0 for failure (logged on error) |

### Per-Run Parameters

| Parameter | Description |
|---|---|
| `model` | Model provider and name (e.g., `google:gemini-2.0-flash`) |
| `input_<key>` | Input parameters (e.g., `input_query`) |
| `error` | Error message (logged on failure) |

### Artifacts

| Artifact | Description |
|---|---|
| `output.txt` | Full agent response text |
| `evaluation_results.json` | Table of evaluation run results |

## How Tracking Works

### Context Manager

Agent runs are wrapped in `track_agent_run`:

```python
async with track_agent_run("Finance Agent", str(settings.get_model()), {"query": query}):
    finance_agent = create_finance_agent()
    result = await finance_agent.run(query, deps=deps)
    log_agent_result(result.output)
```

This automatically:
1. Starts an MLflow run with the given name
2. Logs the model and input parameters
3. Measures latency
4. Logs the output as `output.txt`
5. Captures and logs any errors

### Error Logging

The `log_and_handle_error` decorator logs exceptions with full stack traces:

```python
@finance_agent.tool
@log_and_handle_error
def add_expense(ctx: RunContext[FinanceDependencies], amount: float, category: str, description: str) -> str:
    ...
```

This ensures errors are both:
- Logged to the console via Python logging
- Tracked in MLflow via the context manager

## Running MLflow

```bash
# Start MLflow UI
make mlflow
# Opens at http://127.0.0.1:5001

# Or manually
uv run mlflow ui --port 5001
```

## MLflow Configuration

| Variable | Default | Description |
|---|---|---|
| `MLFLOW_TRACKING_URI` | `sqlite:///mlflow.db` | Backend URI for MLflow |
| `MLFLOW_EXPERIMENT_NAME` | `Personal Finance Assistant` | Experiment name |

### Using Remote MLflow

For team tracking, use a remote MLflow server:

```env
MLFLOW_TRACKING_URI=http://mlflow-server:5000
MLFLOW_EXPERIMENT_NAME=finance-agent-prod
```

## Interpreting Traces

### Successful Run

```
Run Name: Finance Agent
Model: google:gemini-2.0-flash
Latency: 2.34s
Params: input_query="I spent $15 on lunch"
Artifacts: output.txt
```

### Failed Run

```
Run Name: Finance Agent
Model: google:gemini-2.0-flash
Latency: 1.12s
Params: input_query="...", error="Supabase is not configured"
Success: 0
```

## Evaluation Workflow

1. Run evaluation: `python tests/evaluate_agents.py`
2. Open MLflow UI: `make mlflow`
3. Navigate to the `manual_evaluation_script` run
4. View `evaluation_results.json` artifact
5. Review input/output pairs for accuracy

## What Is Not Tracked

- Individual tool calls within an agent run
- Intermediate agent reasoning steps
- Database query execution details
- LLM token usage or cost

For deeper tracing, consider integrating with:
- **LangSmith** — for LLM-specific tracing
- **OpenTelemetry** — for distributed tracing
- **Supabase logs** — for database query tracking

## Cleanup

MLflow data accumulates over time. Clean up old runs:

```python
import mlflow
from core.settings import settings

mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
client = mlflow.tracking.MlflowClient()
experiment = client.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)

# Delete old runs
for run in client.search_runs(experiment.experiment_id):
    if run.info.start_time < some_timestamp:
        client.delete_run(run.info.run_id)
```

Or remove the SQLite file for a fresh start:

```bash
rm mlflow.db
```
