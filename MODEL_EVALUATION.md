# Research methodology and interpretation

## Data population and ground truth

All default transactions are artificial. Rule-based generation uses declared marginal distributions; statistical generation adds category/customer-dependent amount relationships. Fictional customer histories determine previous amounts, cumulative prior frequency and strictly earlier one-hour velocity. Ten versioned scenario families mutate records or coherent customer sequences. Their labels are simulator ground truth, not verified real-world fraud. Distribution shifts in the robustness engine preserve labels; a fraud-simulator shift deliberately labels selected injected cases.

CTGAN and TVAE are actual SDV/PyTorch models trained on a selected artificial seed dataset. Generation reconstructs fictional identifiers, timestamps and past-derived sequence features, enforces constraints, and uses conditional sampling for requested label quotas and supported category conditions. An impossible condition fails explicitly. Short local training runs demonstrate integration, not convergence. Training seeds control learned fitting; generation seeds control structural transaction templates. SDV's stored internal sampling state also governs learned attributes, so changing a generation seed does not promise independently refitted model distributions. Versions and actual observed label rates are recorded.

Validation checks types/schema, missingness, nonfinite values, duplicate identifiers, positive amounts/quantities, timestamps and binary labels. Business-feature duplicates and IQR amount outliers are reported separately. Outliers are not automatically invalid or fraudulent. Quality combines SDV shape/pair-trend reports, KS/Wasserstein differences, categorical total variation, coverage, correlation differences and diversity. Quality does not establish privacy.

## Detector training and leakage controls

Logistic Regression, Random Forest, XGBoost and Isolation Forest are implemented. Default splits are chronological 70/15/15. Customer-grouped cold-start splitting is also available. Every partition needs both classes and at least 20 rows; insufficient samples produce an actionable failure. Identifiers, labels and injection/scenario metadata are excluded from features. Sequence features use observable earlier records. Median/mode imputation, scaling and unknown-safe categorical encoding fit only on the training partition and are saved with the estimator.

One to five bounded parameter trials are selected using validation average precision, with the decision threshold selected by validation F1. Test labels never choose parameters or thresholds. Whole pipelines, source hashes, exact split row identifiers/hashes, parameters, versions and seeds are persisted in trusted internal artifacts. The registry maintains versions and active/retired status. Changing status preserves historical artifacts and evaluations.

Isolation Forest fits legitimate training rows as an anomaly baseline. Its risk output is a training-reference anomaly percentile, not a fraud probability. Brier/ECE are not presented as probability-calibration measures for that baseline.

Metrics include accuracy, precision, recall, F1, ROC-AUC, PR-AUC (defined as average precision), confusion matrix, false-positive/negative rates, Brier score and 10-bin ECE/reliability data. Undefined metrics remain null with explanatory context. Raw classifier probabilities are not asserted to be calibrated. Small positive counts can make point estimates unstable.

## Paired A–F robustness design

| Experiment | Training | Held-out test |
|---|---|---|
| A | Baseline | Baseline population |
| B | Baseline plus augmentation | Same rows as A |
| C | Baseline | Shifted population |
| D | Baseline plus augmentation | Same rows as C |
| E | Baseline | Reserved novel fraud family |
| F | Baseline plus augmentation | Same rows as E |

Splits are frozen before augmentation. Statistical/rule augmentation samples and perturbs training data only. Learned augmentation fits a new CTGAN/TVAE on that training partition only; it never reuses a synthesizer fitted on held-out data. A same-size bootstrap control distinguishes additional training volume from generator changes. Parameter budgets are equal across arms. Reserved novel-family records are removed from all original training inputs before either arm is fitted. Unseen-history reconstruction retains the legitimate pre-test historical context.

Paired differences stay signed, including decreases. Reports include training costs and test hashes. Recall-difference intervals use 100 paired customer-block bootstrap replicates. Repeated fitting seeds operate on the same artificial source population; they do not establish independent real-world replication. Recall at a target FPR uses a validation-negative quantile threshold and reports the achieved test FPR and recall.

The optional supplementary retention score is `100 * mean(min(1, stressed baseline recall / unshifted baseline recall))` over shifted/unseen conditions and selected seeds. It is undefined when reference recall is zero. It is not a safety score and must be read with precision/FPR and per-condition results. Degradation is an absolute metric difference, not an assumed benefit.

Dedicated analyses sweep prevalence, numerical noise, missing inputs, unknown categories, customer/amount/category behavior shifts and frequency shifts. Results disclose nominal versus actual sampled prevalence. Thresholds and fitted preprocessing remain frozen. Novel-family exclusion is based on declared simulator lineage; it does not prove semantic novelty in real-world data.

## Explainability

Actual SHAP permutation explanations use a training-only background, a bounded number of rows and a common probability-space interface across classifiers. Isolation Forest explanations use anomaly-percentile space. Encoded features are mapped back to original fields for aggregated importance. Individual attributions, base values, output values and additive-error diagnostics are saved. Held-out permutation importance uses average-precision decrease and retains negative importance values.

Explanations are calculated on demand, including through each saved prediction's explanation action. They are not computed automatically for every bulk row because that would multiply local CPU cost substantially. The bounded default uses one permutation cycle: additive consistency is tested, but attribution estimates can be noisy. Model behavior explanations do not prove actual fraud.

## Tracking and reporting

MLflow records parameters, metrics, hashes and output artifacts in per-owner experiments. The application database remains authoritative and reports tracking success/failure separately. Research result records persist configuration, versions, relationships and artifact references. PDF/CSV exports use actual saved run results; PDFs include charts, configuration and limitations, with long JSON details bounded and full data retained through the API/artifact store.

No detector, generator or augmentation method is claimed to improve real payment-network fraud detection based on these artificial studies. Real-world validation, privacy auditing and production decision-policy assessment require separate evidence.
