import time
import ollama

from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass

from utils.logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# ---------------------------------------------------------
# Retry Metrics
# ---------------------------------------------------------

@dataclass
class RetryMetrics:
    model_name: str
    attempts: int = 0
    succeeded: bool = False
    last_error: Optional[str] = None


# ---------------------------------------------------------
# LLM Integration Class
# ---------------------------------------------------------

class LLMIntegration:
    """
    Centralized LLM handler with:
    - Retry & exponential backoff
    - Error handling
    - Structured response
    """

    MAX_RETRIES = 3
    INITIAL_DELAY = 2  # seconds

    # ---------------------------------------------------------
    # Core Retry Executor
    # ---------------------------------------------------------

    @staticmethod
    def _execute_stream_with_retry(
        fn: Callable[[], Dict[str, Any]],
        *,
        metrics: RetryMetrics
    ) -> Dict[str, Any]:

        delay = LLMIntegration.INITIAL_DELAY

        for attempt in range(1, LLMIntegration.MAX_RETRIES + 1):
            metrics.attempts = attempt

            try:
                result = fn()

                metrics.succeeded = True

                logger.info(
                    "LLM response: %s. Retry Metrics: %s",
                    result,
                    metrics.__dict__
                    )


                return {
                    "data": result,
                    "retry_metrics": metrics.__dict__
                }

            except ollama.ResponseError as e:
                metrics.last_error = str(e)
                logger.error(f"Ollama ResponseError (attempt {attempt}): {e}")

            except Exception as e:
                metrics.last_error = str(e)
                logger.error(f"Unexpected Error (attempt {attempt}): {e}")

            # Retry logic
            if attempt < LLMIntegration.MAX_RETRIES:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # exponential backoff

        # Final failure
        return {
            "data": None,
            "retry_metrics": metrics.__dict__
        }

    # ---------------------------------------------------------
    # Ollama Model Call
    # ---------------------------------------------------------

    @staticmethod
    def call_ollama_model(
        *,
        ollama_model_name: str,
        system_prompt: str,
        user_message: str,
        max_output_tokens: int = 1000,
        temperature: float = 0.0
    ) -> Dict[str, Any]:

        metrics = RetryMetrics(model_name=ollama_model_name)

        def _call() -> Dict[str, Any]:

            response = ollama.chat(
                model=ollama_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                options={
                    "num_predict": max_output_tokens,
                    "temperature": temperature
                }
            )

            content = response["message"]["content"]


            return {
                "content": content
            }

        return LLMIntegration._execute_stream_with_retry(
            _call,
            metrics=metrics
        )
