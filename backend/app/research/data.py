import hashlib
from datetime import timezone


from .schemas import Generation, SCENARIOS

NUMERIC = ["transaction_amount", "quantity", "customer_account_age_days", "transaction_frequency", "previous_transaction_amount", "shipping_address_change", "billing_shipping_mismatch", "transaction_velocity", "hour"]
CATEGORICAL = ["product_category", "payment_method", "device_type", "location_region"]
FEATURES = NUMERIC + CATEGORICAL
BUSINESS_COLUMNS = ["transaction_id", "customer_id", "product_id", "transaction_timestamp", *FEATURES, "is_fraud", "scenario_type"]


def sequence_features(frame):
    import numpy as np
    import pandas as pd
    frame = frame.sort_values(["transaction_timestamp", "transaction_id"]).reset_index(drop=True)
    timestamps = pd.to_datetime(frame.transaction_timestamp, utc=True, format="ISO8601")
    frame["hour"] = timestamps.dt.hour
    grouped = frame.groupby("customer_id", sort=False)
    frame["previous_transaction_amount"] = grouped.transaction_amount.shift().fillna(0).round(2)
    frame["transaction_frequency"] = grouped.cumcount()
    # Number of strictly earlier transactions within the preceding hour.
    velocity = np.zeros(len(frame), dtype=int)
    for indexes in grouped.indices.values():
        times = timestamps.iloc[indexes].astype("int64").to_numpy()
        velocity[indexes] = np.searchsorted(times, times, side="left") - np.searchsorted(times, times - 3600 * 10**9, side="left")
    frame["transaction_velocity"] = velocity
    return frame


def apply_scenario(frame, scenario, fraction=.05, severity=1, seed=42, label=True):
    import numpy as np
    import pandas as pd
    data = frame.copy().reset_index(drop=True)
    rng = np.random.default_rng(seed)
    selected = rng.choice(len(data), max(1, round(len(data) * fraction)), replace=False)
    if scenario == "high_value":
        data.loc[selected, "transaction_amount"] *= 2 + 2 * severity
    elif scenario in {"rapid_purchases", "short_window_burst", "frequency_anomaly"}:
        # Coherent repeated fictional customer histories, rather than forged counters.
        for start in range(0, len(selected), 5):
            group = selected[start:start + 5]
            data.loc[group, "customer_id"] = f"SIM-BURST-{seed}-{start}"
            base = pd.to_datetime(data.loc[group[0], "transaction_timestamp"], utc=True, format="ISO8601")
            data.loc[group, "transaction_timestamp"] = [(base + pd.Timedelta(seconds=int(n * 2 / severity))).isoformat() for n in range(len(group))]
    elif scenario == "device_change":
        data.loc[selected, "device_type"] = "unrecognized_device"
    elif scenario == "address_mismatch":
        data.loc[selected, ["shipping_address_change", "billing_shipping_mismatch"]] = 1
    elif scenario == "unusual_hour":
        data.loc[selected, "transaction_timestamp"] = pd.to_datetime(data.loc[selected, "transaction_timestamp"], utc=True, format="ISO8601").dt.normalize().add(pd.Timedelta(hours=3)).map(lambda t: t.isoformat())
    elif scenario == "purchasing_pattern":
        data.loc[selected, "product_category"] = "unfamiliar_category"
        data.loc[selected, "transaction_amount"] *= 1 + severity
    elif scenario == "distribution_shift":
        data.loc[selected, "transaction_amount"] *= 1 + severity
        data.loc[selected, "location_region"] = "shifted_region"
    elif scenario == "novel_combination":
        # Novel family is reserved for robustness tests unless explicitly simulated.
        data.loc[selected, "transaction_amount"] *= .35
        data.loc[selected, "device_type"] = "novel_device"
        data.loc[selected, "payment_method"] = "novel_wallet"
        data.loc[selected, "customer_account_age_days"] = 0
    else:
        raise ValueError("Unknown scenario")
    if label:
        data.loc[selected, "is_fraud"] = 1
    data.loc[selected, "scenario_type"] = scenario
    data["transaction_amount"] = data.transaction_amount.clip(.01, 10000000).round(2)
    return sequence_features(data)


def generate(config: Generation):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(config.seed)
    n = config.rows
    start = pd.Timestamp(config.start_at)
    end = pd.Timestamp(config.end_at)
    start = start.tz_localize("UTC") if start.tz is None else start.tz_convert("UTC")
    end = end.tz_localize("UTC") if end.tz is None else end.tz_convert("UTC")
    customers = rng.integers(0, max(20, n // 8), n)
    categories = rng.choice(config.categories, n)
    weights = {name: 1 + i * .7 for i, name in enumerate(config.categories)}
    if config.distribution == "normal":
        amounts = rng.normal(80, 35, n)
    elif config.distribution == "uniform":
        amounts = rng.uniform(5, 300, n)
    else:
        amounts = rng.lognormal(np.log(55), .85, n)
    if config.method == "statistical":
        amounts *= np.array([weights[name] for name in categories]) * (1 + (customers % 7) * .08)
    timestamps = start + pd.to_timedelta(rng.uniform(0, (end - start).total_seconds(), n), unit="s")
    data = pd.DataFrame({"transaction_id": [f"SYN-{config.seed}-{i:08d}" for i in range(n)], "customer_id": [f"CUS-{value:07d}" for value in customers], "product_id": [f"PRD-{value:05d}" for value in rng.integers(0, 300, n)], "product_category": categories, "transaction_amount": np.maximum(amounts, .01).round(2), "quantity": rng.integers(1, 6, n), "transaction_timestamp": timestamps.map(lambda t: t.isoformat()), "payment_method": rng.choice(config.payment_methods, n), "device_type": rng.choice(config.device_types, n), "location_region": rng.choice(config.regions, n), "customer_account_age_days": (customers % 1800) + 1, "shipping_address_change": rng.binomial(1, .06, n), "billing_shipping_mismatch": rng.binomial(1, .04, n), "is_fraud": 0, "scenario_type": "legitimate"})
    # Different latent mechanisms with overlapping legitimate feature values.
    fraud = rng.choice(n, round(n * config.fraud_rate), replace=False)
    data.loc[fraud, "is_fraud"] = 1
    for index, rows in enumerate(np.array_split(fraud, 3)):
        scenario = ["high_value", "address_mismatch", "unusual_hour"][index]
        data.loc[rows, "scenario_type"] = scenario
        if index == 0:
            data.loc[rows, "transaction_amount"] = (data.loc[rows, "transaction_amount"] * rng.uniform(1.5, 4, len(rows))).round(2)
        elif index == 1:
            data.loc[rows, "billing_shipping_mismatch"] = rng.binomial(1, .75, len(rows))
        else:
            data.loc[rows, "transaction_timestamp"] = pd.to_datetime(data.loc[rows, "transaction_timestamp"], utc=True, format="ISO8601").dt.normalize().add(pd.Timedelta(hours=2)).map(lambda t: t.isoformat())
    data = sequence_features(data)
    # Unusual-hour normalization must respect a partial-day configured interval.
    times = pd.to_datetime(data.transaction_timestamp, utc=True, format="ISO8601").clip(lower=start, upper=end)
    data["transaction_timestamp"] = times.map(lambda t: t.isoformat())
    return sequence_features(data)


def validation(frame):
    import numpy as np
    import pandas as pd
    checks = {"missing_values": int(frame.isna().sum().sum()), "nonfinite_numeric": int((~np.isfinite(frame[NUMERIC].to_numpy(float))).sum()), "duplicate_transaction_ids": int(frame.transaction_id.duplicated().sum()), "nonpositive_amount": int((frame.transaction_amount <= 0).sum()), "invalid_quantity": int((frame.quantity < 1).sum()), "invalid_labels": int((~frame.is_fraud.isin([0, 1])).sum()), "invalid_timestamps": int(pd.to_datetime(frame.transaction_timestamp, utc=True, format="ISO8601", errors="coerce").isna().sum())}
    q1, q3 = frame.transaction_amount.quantile([.25, .75])
    outliers = int(((frame.transaction_amount < q1 - 1.5 * (q3 - q1)) | (frame.transaction_amount > q3 + 1.5 * (q3 - q1))).sum())
    return {"rows": len(frame), "valid": not any(checks.values()), "checks": checks, "business_duplicates": int(frame.drop(columns=["transaction_id"]).duplicated().sum()), "fraud_count": int(frame.is_fraud.sum()), "fraud_rate": float(frame.is_fraud.mean()), "amount_mean": float(frame.transaction_amount.mean()), "amount_median": float(frame.transaction_amount.median()), "amount_max": float(frame.transaction_amount.max()), "amount_iqr_outliers": outliers, "outlier_definition": "Outside Q1-1.5*IQR or Q3+1.5*IQR; outliers are not automatically invalid", "schema": {column: str(dtype) for column, dtype in frame.dtypes.items()}}


def quality(frame, reference):
    import numpy as np
    from scipy.stats import ks_2samp, wasserstein_distance
    numerical, categorical = [], []
    for feature in NUMERIC:
        a, b = frame[feature].dropna().to_numpy(float), reference[feature].dropna().to_numpy(float)
        numerical.append({"feature": feature, "ks_statistic": float(ks_2samp(a, b).statistic), "wasserstein": float(wasserstein_distance(a, b))})
    for feature in CATEGORICAL:
        a, b = frame[feature].value_counts(normalize=True), reference[feature].value_counts(normalize=True)
        categories = a.index.union(b.index)
        categorical.append({"feature": feature, "total_variation": float(np.abs(a.reindex(categories, fill_value=0) - b.reindex(categories, fill_value=0)).sum() / 2), "coverage": float(len(set(a.index) & set(b.index)) / max(1, len(b)))})
    correlation_delta = (frame[NUMERIC].corr().fillna(0) - reference[NUMERIC].corr().fillna(0)).abs()
    return {"validation": validation(frame), "numerical": numerical, "categorical": categorical, "mean_correlation_difference": float(correlation_delta.to_numpy().mean()), "diversity": float(1 - frame[FEATURES].duplicated().mean()), "limitations": "Distribution similarity does not establish privacy or real-world fraud detection efficacy."}


def frame_hash(frame):
    return hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()

