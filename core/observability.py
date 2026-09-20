
import mlflow
import time
import asyncio
from typing import Any, Optional, Dict
from contextlib import asynccontextmanager
from core.settings import settings

import logging
import traceback
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLflowTracker:
    _initialized = False

    @classmethod
    def initialize(cls):
        if not cls._initialized:
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
            cls._initialized = True

@asynccontextmanager
async def track_agent_run(
    run_name: str, 
    model_name: str, 
    inputs: Dict[str, Any]
):
    """
    Async context manager to track an agent run in MLflow.
    """
    MLflowTracker.initialize()
    
    with mlflow.start_run(run_name=run_name) as run:
        # Log basic params
        mlflow.log_param("model", model_name)
        for k, v in inputs.items():
            mlflow.log_param(f"input_{k}", v)
        
        start_time = time.time()
        try:
            yield run
            # If successful, we can log success metadada if needed here
        except Exception as e:
            mlflow.log_param("error", str(e))
            mlflow.log_metric("success", 0)
            raise e
        finally:
            duration = time.time() - start_time
            mlflow.log_metric("latency", duration)

def log_agent_result(output: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Helper to log result and additional metadata within an active run.
    """
    if mlflow.active_run():
        mlflow.log_text(output, "output.txt")
        if metadata:
            for k, v in metadata.items():
                mlflow.log_param(f"meta_{k}", v)

def log_and_handle_error(func):
    """
    Decorator to log exceptions with stack trace.
    It re-raises the exception after logging to avoid breaking data contracts
    (e.g., returning a string when a list is expected).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise e
    
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise e

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return wrapper
