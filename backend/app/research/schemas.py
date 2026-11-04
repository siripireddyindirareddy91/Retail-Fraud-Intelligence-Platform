from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ..schemas import Input

SCENARIOS = ["high_value", "rapid_purchases", "short_window_burst", "device_change", "address_mismatch", "unusual_hour", "frequency_anomaly", "purchasing_pattern", "distribution_shift", "novel_combination"]


class Generation(Input):
    name: str = Field(default="Retail transactions", min_length=1, max_length=120)
    method: Literal["statistical", "rule_based", "ctgan", "tvae"] = "statistical"
    rows: int = Field(default=10000, ge=100, le=100000)
    fraud_rate: float = Field(default=.02, ge=0, le=.5)
    seed: int = Field(default=42, ge=0, le=2**32-1)
    distribution: Literal["lognormal", "normal", "uniform"] = "lognormal"
    categories: list[str] = Field(default=["grocery", "electronics", "clothing"], min_length=1, max_length=20)
    payment_methods: list[str] = Field(default=["card", "wallet"], min_length=1, max_length=10)
    device_types: list[str] = Field(default=["mobile", "desktop"], min_length=1, max_length=10)
    regions: list[str] = Field(default=["region_a", "region_b"], min_length=1, max_length=20)
    start_at: datetime = datetime(2026, 1, 1)
    end_at: datetime = datetime(2026, 2, 1)
    generative_model_id: UUID | None = None
    conditions: dict[str, str | int] = Field(default_factory=dict, max_length=3)

    @model_validator(mode="after")
    def compatible(self):
        self.start_at = self.start_at.replace(tzinfo=timezone.utc) if self.start_at.tzinfo is None else self.start_at.astimezone(timezone.utc)
        self.end_at = self.end_at.replace(tzinfo=timezone.utc) if self.end_at.tzinfo is None else self.end_at.astimezone(timezone.utc)
        if self.end_at <= self.start_at:
            raise ValueError("End date must follow start date")
        if self.method in {"ctgan", "tvae"} and not self.generative_model_id:
            raise ValueError("Select a fitted generative model")
        if "is_fraud" in self.conditions:
            raise ValueError("Use fraud_rate for label quotas; conditions may constrain other fitted columns")
        if any(len(value) > 50 or not value.strip() for values in (self.categories, self.payment_methods, self.device_types, self.regions) for value in values):
            raise ValueError("Category values must contain 1–50 characters")
        return self


class GenerativeTraining(Input):
    dataset_id: UUID
    method: Literal["ctgan", "tvae"]
    name: str = Field(default="Retail synthesizer", min_length=1, max_length=120)
    epochs: int = Field(default=10, ge=1, le=200)
    seed: int = Field(default=42, ge=0, le=2**32-1)


class Scenario(Input):
    dataset_id: UUID
    scenario: Literal["high_value", "rapid_purchases", "short_window_burst", "device_change", "address_mismatch", "unusual_hour", "frequency_anomaly", "purchasing_pattern", "distribution_shift", "novel_combination"]
    fraction: float = Field(default=.05, gt=0, le=.5)
    severity: float = Field(default=1, ge=.1, le=3)
    seed: int = Field(default=42, ge=0, le=2**32-1)


class Training(Input):
    dataset_id: UUID
    algorithm: Literal["logistic_regression", "random_forest", "xgboost", "isolation_forest"] = "random_forest"
    name: str = Field(default="Fraud detector", min_length=1, max_length=120)
    seed: int = Field(default=42, ge=0, le=2**32-1)
    split: Literal["chronological", "customer_grouped"] = "chronological"
    trials: int = Field(default=1, ge=1, le=5)


class Analysis(Input):
    dataset_id: UUID | None = None
    reference_dataset_id: UUID | None = None
    model_id: UUID | None = None
    analysis: Literal["quality", "validation", "patterns", "risk", "drift", "imbalance", "noise", "unseen", "performance", "shap", "importance", "permutation"] = "quality"
    samples: int = Field(default=40, ge=1, le=200)
    seed: int = Field(default=42, ge=0, le=2**32-1)
    prediction_id: UUID | None = None
    background_samples: int = Field(default=20, ge=1, le=100)
    levels: list[float] = Field(default_factory=list, max_length=10)
    noise_mode: Literal["all", "numeric_noise", "missingness", "category_corruption", "behavior_shift", "frequency_shift"] = "all"
    source: Literal["ground_truth", "predictions"] = "ground_truth"
    group_by: Literal["product_category", "device_type", "hour", "location_region", "scenario_type"] = "product_category"
    threshold: float | None = Field(default=None, ge=0, le=1)
    target_fpr: float = Field(default=.01, gt=0, lt=1)
    unseen_scenario: Literal["novel_combination", "device_change", "purchasing_pattern"] = "novel_combination"

    @model_validator(mode="after")
    def level_bounds(self):
        if any(not 0 <= level <= 1 for level in self.levels):
            raise ValueError("Stress levels must be in [0,1]")
        return self


class Robustness(Input):
    name: str = Field(default="Augmentation robustness study", min_length=1, max_length=120)
    dataset_id: UUID
    algorithm: Literal["logistic_regression", "random_forest", "xgboost"] = "random_forest"
    augmentation: Literal["statistical", "rule_based", "ctgan", "tvae"] = "statistical"
    ratio: float = Field(default=1, ge=.1, le=2)
    seeds: list[int] = Field(default=[42, 43, 44], min_length=1, max_length=5)
    epochs: int = Field(default=5, ge=1, le=50)


class BatchPrediction(Input):
    dataset_id: UUID
    model_id: UUID


class SinglePrediction(Input):
    model_id: UUID
    features: dict = Field(max_length=30)


class Report(Input):
    run_id: UUID
    format: Literal["pdf", "csv"] = "pdf"


class StreamConfig(Input):
    model_id: UUID | None = None
    fraud_rate: float = Field(default=.02, ge=0, le=.5)
    interval_seconds: float = Field(default=2, ge=1, le=10)
    max_transactions: int = Field(default=100, ge=1, le=500)
    seed: int = Field(default=42, ge=0, le=2**32-1)
