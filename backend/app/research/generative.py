import random

import numpy as np
import pandas as pd
from joblib import parallel_config

from .data import CATEGORICAL, FEATURES, sequence_features, validation


def fit_synthesizer(frame, method="ctgan", epochs=10, seed=42):
    import time
    started = time.perf_counter()
    import torch
    from sdv.metadata import Metadata
    from sdv.single_table import CTGANSynthesizer, TVAESynthesizer
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    columns = ["transaction_amount", "quantity", "customer_account_age_days", "shipping_address_change", "billing_shipping_mismatch", *CATEGORICAL, "is_fraud"]
    data = frame[columns].copy()
    metadata = Metadata.detect_from_dataframe(data=data, table_name="transactions", infer_keys=None)
    for column in CATEGORICAL:
        metadata.update_column(table_name="transactions", column_name=column, sdtype="categorical")
    model = CTGANSynthesizer(metadata, epochs=epochs, batch_size=100, pac=10, generator_dim=(64, 64), discriminator_dim=(64, 64), cuda=False, verbose=False) if method == "ctgan" else TVAESynthesizer(metadata, epochs=epochs, batch_size=100, embedding_dim=32, compress_dims=(64, 32), decompress_dims=(32, 64), cuda=False)
    # CTGAN's data transformer explicitly asks Joblib for every CPU (n_jobs=-1)
    # at 500+ rows. Keep preprocessing inside our bounded worker instead of
    # spawning another all-core process pool, especially on Windows/containers.
    with parallel_config(backend="sequential"):
        model.fit(data)
    return {"synthesizer": model, "metadata": metadata.to_dict(), "method": method, "columns": columns, "seed": seed, "epochs": epochs, "training_rows": len(frame), "training_seconds": time.perf_counter() - started}


def sample_synthesizer(bundle, template, conditions=None):
    conditions = conditions or {}
    if any(key not in bundle["columns"] for key in conditions):
        raise ValueError("Conditions must use fitted synthesizer columns")
    with parallel_config(backend="sequential"):
        if conditions:
            from sdv.sampling import Condition
            sampled = bundle["synthesizer"].sample_from_conditions([Condition(num_rows=len(template), column_values=conditions)], max_tries_per_batch=30, output_file_path="disable")
        else:
            sampled = bundle["synthesizer"].sample(num_rows=len(template), output_file_path="disable")
    data = template.copy()
    for column in bundle["columns"]:
        data[column] = sampled[column].to_numpy()
    data["transaction_amount"] = pd.to_numeric(data.transaction_amount, errors="coerce").fillna(1).clip(.01, 10000000).round(2)
    for column in ["quantity", "customer_account_age_days", "shipping_address_change", "billing_shipping_mismatch", "is_fraud"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0).round().astype(int)
    data["quantity"] = data.quantity.clip(1, 100)
    data["customer_account_age_days"] = data.customer_account_age_days.clip(0)
    for column in ["shipping_address_change", "billing_shipping_mismatch", "is_fraud"]:
        data[column] = data[column].clip(0, 1)
    data["scenario_type"] = "learned_synthetic"
    data = sequence_features(data)
    if not validation(data)["valid"]:
        raise ValueError("Learned samples failed transaction constraints")
    return data


def sdv_quality(reference, generated):
    from sdv.evaluation.single_table import evaluate_quality
    from sdv.metadata import Metadata
    columns = ["transaction_amount", "quantity", *CATEGORICAL, "is_fraud"]
    metadata = Metadata.detect_from_dataframe(data=reference[columns], table_name="transactions", infer_keys=None)
    report = evaluate_quality(reference[columns], generated[columns], metadata, verbose=False)
    return {"score": float(report.get_score()), "properties": report.get_properties().to_dict(orient="records"), "definition": "SDV column shapes and column-pair trends; not a privacy guarantee"}
