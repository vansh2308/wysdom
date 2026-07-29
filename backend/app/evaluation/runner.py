from __future__ import annotations

import logging
import uuid
from enum import Enum

from langsmith import aevaluate

from app.core.config import get_settings
from app.evaluation.metrics.agent_metrics import agent_evaluators
from app.evaluation.metrics.answer_quality_metrics import answer_quality_evaluators
from app.evaluation.metrics.compression_metrics import compression_evaluators
from app.evaluation.metrics.retrieval_metrics import retrieval_evaluators
from app.evaluation.targets import agent_target, answer_quality_target, compression_target, dense_retrieval_target
from app.infrastructure.observability.langsmith_client import get_langsmith_client

logger = logging.getLogger(__name__)


class EvalSuite(str, Enum):
    RETRIEVAL_DENSE = "retrieval_dense"
    COMPRESSION = "compression"
    AGENT = "agent"
    ANSWER_QUALITY = "answer_quality"


_SUITES = {
    EvalSuite.RETRIEVAL_DENSE: (dense_retrieval_target, lambda: retrieval_evaluators(ks=get_settings().EVAL_RETRIEVAL_K_VALUES)),
    EvalSuite.COMPRESSION: (compression_target, compression_evaluators),
    EvalSuite.AGENT: (agent_target, agent_evaluators),
    EvalSuite.ANSWER_QUALITY: (answer_quality_target, answer_quality_evaluators),
}


async def run_eval_suite(suite: EvalSuite, dataset_name: str, max_concurrency: int, experiment_prefix: str) -> None:
    """Runs as a FastAPI background task — exceptions here won't propagate
    to any HTTP response, so they're caught and logged explicitly rather
    than silently lost."""
    try:
        target, evaluators_factory = _SUITES[suite]
        await aevaluate(
            target,
            data=dataset_name,
            evaluators=evaluators_factory(),
            experiment_prefix=experiment_prefix,
            max_concurrency=max_concurrency,
            client=get_langsmith_client(),
        )
        logger.info("Eval suite %s completed: %s", suite.value, experiment_prefix)
    except Exception:
        logger.exception("Eval suite %s (%s) failed", suite.value, experiment_prefix)