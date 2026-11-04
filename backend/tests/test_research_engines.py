import numpy as np
import pytest

from app.research.data import FEATURES, apply_scenario, generate, validation
from app.research.generative import fit_synthesizer, sample_synthesizer, sdv_quality
from app.research.ml import explain, metrics, scores, train
from app.research.robustness import run_study
from app.research.schemas import Generation, Robustness, SCENARIOS


def population(rows=1000):
    return generate(Generation(rows=rows, fraud_rate=.12, seed=44))


def test_generation_reproducibility_and_temporal_features():
    a, b = population(), population()
    assert a.equals(b)
    assert validation(a)["valid"] and int(a.is_fraud.sum()) == 120
    for _, group in a.groupby("customer_id"):
        assert group.previous_transaction_amount.tolist() == [0] + group.transaction_amount.tolist()[:-1]
    assert not set(["is_fraud", "scenario_type", "transaction_id", "customer_id"]) & set(FEATURES)


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_scenarios_are_real_mutations_with_valid_ground_truth(scenario):
    original = population()
    changed = apply_scenario(original, scenario, .15, seed=4)
    assert not changed.equals(original)
    assert validation(changed)["valid"]
    assert (changed.scenario_type == scenario).sum() >= 150


@pytest.mark.parametrize("algorithm", ["logistic_regression", "random_forest", "xgboost", "isolation_forest"])
def test_detectors_hold_out_test_rows_and_predict(algorithm):
    bundle, result = train(population(), algorithm)
    train_ids, test_ids = set(bundle["train"].transaction_id), set(bundle["test"].transaction_id)
    assert not train_ids & test_ids
    assert result["metrics"]["pr_auc"] is not None
    probability = scores(bundle, bundle["test"])
    assert np.isfinite(probability).all() and ((probability >= 0) & (probability <= 1)).all()
    if algorithm == "isolation_forest":
        assert result["metrics"]["brier"] is None


@pytest.mark.parametrize("method", ["ctgan", "tvae"])
def test_actual_sdv_training_sampling_and_quality(method, monkeypatch):
    def unexpected_process_pool(*args, **kwargs):
        raise AssertionError("Learned generation must not create an unbounded nested process pool")
    monkeypatch.setattr("joblib._parallel_backends.LokyBackend.configure", unexpected_process_pool)
    frame = population(500)
    learned = fit_synthesizer(frame, method, epochs=1)
    sampled = sample_synthesizer(learned, frame.head(100).copy(), {"payment_method": "card"})
    assert len(sampled) == 100 and sampled.payment_method.eq("card").all()
    assert validation(sampled)["valid"]
    assert 0 <= sdv_quality(frame, sampled)["score"] <= 1


def test_shap_additivity_uses_training_background():
    bundle, _ = train(population(), "logistic_regression")
    explanation = explain(bundle, bundle["test"], samples=3)
    assert explanation["sample_count"] == 3
    assert explanation["max_additivity_error"] < 1e-5
    assert explanation["importance"]


def test_paired_robustness_and_signed_deltas():
    result = run_study(population(), Robustness(dataset_id="00000000-0000-0000-0000-000000000001", algorithm="logistic_regression", seeds=[42]))
    assert [pair["baseline_experiment"] for pair in result["runs"][0]["pairs"]] == ["A", "C", "E"]
    assert result["runs"][0]["training_only_augmentation"]
    for pair in result["runs"][0]["pairs"]:
        assert pair["signed_delta"]["recall"] == pytest.approx(pair["augmented"]["recall"] - pair["baseline"]["recall"])
        assert pair["recall_difference_ci"]["lower"] is not None


def test_undefined_metrics_stay_undefined():
    result = metrics(np.zeros(10), np.zeros(10))
    assert result["roc_auc"] is None and result["recall"] is None and result["precision"] is None
