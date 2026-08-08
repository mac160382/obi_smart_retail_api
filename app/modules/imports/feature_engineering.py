import logging

logger = logging.getLogger(__name__)


def run_feature_engineering(rows: list[dict]) -> None:
    """Mock temporal del proceso de feature engineering."""
    logger.info(
        "Feature engineering mock completed",
        extra={"row_count": len(rows)},
    )
