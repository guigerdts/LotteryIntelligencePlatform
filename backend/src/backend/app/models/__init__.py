"""SQLAlchemy ORM entities (schema introduced in Fase 1).

Re-exports are the source of ``Base.metadata`` for alembic ``target_metadata``
(REQ-09): importing this package registers every table on the declarative base.
"""

from backend.app.models.dataset import Dataset
from backend.app.models.dataset_draw import DatasetDraw
from backend.app.models.draw import Draw
from backend.app.models.draw_number import DrawNumber
from backend.app.models.feature_snapshot import FeatureSnapshot
from backend.app.models.feature_value import FeatureValue
from backend.app.models.graph_snapshot import GraphSnapshot
from backend.app.models.graph_value import GraphValue
from backend.app.models.import_error import ImportError
from backend.app.models.import_job import ImportJob
from backend.app.models.lottery import Lottery
from backend.app.models.ml_metric import MlMetric
from backend.app.models.ml_snapshot import MlSnapshot
from backend.app.models.prob_snapshot import ProbSnapshot
from backend.app.models.prob_value import ProbValue
from backend.app.models.stat_average import StatAverage
from backend.app.models.stat_frequency import StatFrequency
from backend.app.models.stat_frequency_position import StatFrequencyPosition
from backend.app.models.stat_gap import StatGap
from backend.app.models.stat_scalar import StatScalar
from backend.app.models.stat_snapshot import StatSnapshot
from backend.app.models.super_number import SuperNumber
from backend.app.repositories.base import Base

__all__ = [
    "Base",
    "Dataset",
    "DatasetDraw",
    "Draw",
    "DrawNumber",
    "FeatureSnapshot",
    "FeatureValue",
    "GraphSnapshot",
    "GraphValue",
    "ImportError",
    "ImportJob",
    "Lottery",
    "MlMetric",
    "MlSnapshot",
    "ProbSnapshot",
    "ProbValue",
    "StatAverage",
    "StatFrequency",
    "StatFrequencyPosition",
    "StatGap",
    "StatScalar",
    "StatSnapshot",
    "SuperNumber",
]
