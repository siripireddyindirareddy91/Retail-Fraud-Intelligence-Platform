# MASTER PROMPT: COMPLETE END-TO-END PROJECT DEVELOPMENT

# PROJECT TITLE

A Generative AI-Based Synthetic Transaction Data Framework for Retail Fraud Detection and Model Robustness Evaluation

## PRODUCT NAME

Retail Fraud Intelligence Platform

## PROJECT OBJECTIVE

Act as a Senior Software Architect, Generative AI Engineer, Machine Learning Engineer, Data Scientist, Full-Stack Developer, UI/UX Designer, Database Architect, QA Engineer and DevOps Engineer.

Your task is to develop a complete, professional, enterprise-level, real-time web application from an empty repository.

This must be a fully functional research-oriented AI platform, not just a basic academic project, static dashboard, chatbot or frontend prototype.

The platform must generate realistic synthetic retail transaction data using Generative AI, simulate different fraud scenarios, train machine learning models, detect fraudulent transactions and evaluate model robustness under different data conditions.

The entire application must have an attractive, modern, responsive enterprise SaaS interface with a fixed left sidebar, complete catalog navigation, individual pages, interactive dashboards, real backend integrations and dynamic outputs.

Build the project from frontend to backend, database, AI/ML engines, testing and deployment.

---

# 1. TECHNOLOGY STACK

Use the following technology stack.

## Frontend
- React.js
- Vite
- TypeScript
- Tailwind CSS
- React Router
- Axios
- Recharts
- Plotly.js where appropriate
- Lucide React icons

## Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Uvicorn

## Database
- PostgreSQL
- SQLite for local development fallback
- Alembic for migrations

## Data Science
- Pandas
- NumPy
- SciPy
- Scikit-learn

## Generative AI and Synthetic Data
- Synthetic Data Vault (SDV)
- CTGAN
- TVAE
- Statistical generation
- Rule-based synthetic generation

## Machine Learning
- Logistic Regression
- Random Forest
- XGBoost
- Isolation Forest

## Explainable AI
- SHAP

## Experiment Tracking
- MLflow

## Background Processing
- Celery and Redis, or an appropriate lightweight background-task architecture for local development.

## Testing
- Pytest
- Vitest
- React Testing Library
- Playwright for end-to-end testing

## Deployment
- Docker
- Docker Compose
- Environment-based configuration

Use compatible and stable library versions. Document all dependencies.

Do not introduce unnecessary technologies without explaining their purpose.

---

# 2. COMPLETE WEBSITE DESIGN AND USER EXPERIENCE

## Overall Website Requirements

Develop a premium, professional enterprise SaaS website named:

Retail Fraud Intelligence Platform.

The design quality should be comparable to modern products such as Stripe Dashboard, Linear, Vercel, Datadog and professional financial analytics platforms.

The website must have:
- Professional typography.
- Modern layouts.
- Attractive dashboard cards.
- Consistent spacing.
- Premium visual hierarchy.
- Smooth transitions.
- Interactive charts.
- Modern tables.
- Responsive components.
- Subtle animations.
- Loading skeletons.
- Toast notifications.
- Attractive empty states.
- Error handling.
- Professional icons.

Avoid a basic student-project appearance.

## 2.1 Main Application Layout

Create a two-section layout:

LEFT SIDEBAR:
A fixed, vertically scrollable navigation panel.

RIGHT WORKSPACE:
The main application workspace where individual module pages open.

Sidebar dimensions:
- Expanded: approximately 270px.
- Collapsed: approximately 76px.

The sidebar must remain visible while navigating between pages on desktop.

Implement responsive drawer navigation on mobile.

Include:
- Application logo.
- Application name.
- Expand/collapse button.
- Navigation categories.
- Navigation icons.
- Active-page highlighting.
- Hover effects.
- Optional notification indicators.

## 2.2 Complete Sidebar Catalog

Create the following navigation categories and individual pages.

### A. OVERVIEW
1. Dashboard
2. Platform Overview

### B. SYNTHETIC DATA INTELLIGENCE
3. Synthetic Data Generator
4. Generative AI Models
5. Dataset Explorer
6. Data Quality Analysis
7. Synthetic Data Validation

### C. FRAUD INTELLIGENCE
8. Fraud Detection
9. Fraud Scenario Simulator
10. Transaction Monitoring
11. Fraud Pattern Analysis
12. Risk Analysis

### D. MACHINE LEARNING LAB
13. Model Training
14. Model Comparison
15. Model Registry
16. Model Prediction

### E. ROBUSTNESS EVALUATION
17. Robustness Testing
18. Data Drift Analysis
19. Class Imbalance Analysis
20. Noise Sensitivity Testing
21. Unseen Fraud Evaluation
22. Performance Evaluation

### F. EXPLAINABLE AI
23. SHAP Analysis
24. Feature Importance
25. Individual Prediction Explanation

### G. EXPERIMENT MANAGEMENT
26. Experiments
27. Experiment History
28. Evaluation Reports

### H. SYSTEM MANAGEMENT
29. User Management
30. Settings
31. API Documentation
32. System Health

Every catalog item must open its own individual page.

Do not combine all functionality into a single long dashboard.

## 2.3 Individual Page Navigation

Implement React Router.

Requirements:
- Clicking a sidebar item opens its individual page.
- Sidebar remains visible.
- Active navigation is highlighted.
- Breadcrumbs update dynamically.
- Browser back and forward work.
- Direct page URLs work.
- No full page reload during normal navigation.
- Page state and useful filters persist where appropriate.
- Every page has a meaningful interface and working functionality.

## 2.4 Top Navigation Bar

Include:
- Sidebar toggle.
- Breadcrumb navigation.
- Global search.
- Notification panel.
- User profile.
- Settings.
- Light/dark mode switcher.
- Backend connection status.
- Application status.

The global search should find available pages, datasets, experiments and transactions.

---

# 3. DASHBOARD MODULE

Create a professional analytics dashboard.

Display these live metrics:

- Total transactions generated.
- Legitimate transactions.
- Fraudulent transactions.
- Fraud percentage.
- Active ML models.
- Completed experiments.
- Latest dataset.
- Latest model performance.

Create the following charts:

1. Transaction activity over time.
2. Fraud distribution.
3. Legitimate versus fraudulent transactions.
4. Fraud trends.
5. Model performance comparison.
6. Synthetic data quality.
7. Robustness evaluation results.
8. Recent experiment activity.

Create sections for:
- Recent datasets.
- Recent experiments.
- Recent fraud alerts.
- Model status.
- System activity.

All metrics and charts must be populated from actual backend data.

Do not hardcode fake metrics.

Display meaningful empty states when no experiments have been performed.

---

# 4. SYNTHETIC TRANSACTION DATA GENERATION ENGINE

Develop a complete synthetic retail transaction generation system.

## Transaction Dataset Fields

Generate fields such as:

- transaction_id
- customer_id
- product_id
- product_category
- transaction_amount
- quantity
- transaction_timestamp
- payment_method
- device_type
- location_region
- customer_account_age_days
- transaction_frequency
- previous_transaction_amount
- shipping_address_change
- billing_shipping_mismatch
- transaction_velocity
- is_fraud

Use fictional identifiers and artificial data only.

Never generate real payment credentials or sensitive customer information.

## Generator Features

Allow users to configure:

- Number of transactions.
- Fraud percentage.
- Transaction amount distribution.
- Product categories.
- Payment methods.
- Device types.
- Time period.
- Geographic regions.
- Random seed.
- Generation method.

Support:
- Rule-based generation.
- Statistical generation.
- CTGAN generation.
- TVAE generation.

Provide:
- Generate Dataset button.
- Generation progress.
- Generated transaction count.
- Dataset preview.
- Dataset statistics.
- CSV download.
- JSON download.
- Dataset metadata.

Make the generation pipeline reproducible.

Validate data types, constraints and missing values.

---

# 5. GENERATIVE AI ENGINE

Integrate SDV and its supported generative models.

Implement:

1. CTGAN.
2. TVAE.
3. Statistical synthetic generation.
4. Rule-based synthetic generation.

Features:
- Model selection.
- Model configuration.
- Model training.
- Conditional generation.
- Generation history.
- Training status.
- Model metadata.
- Synthetic dataset generation.

Evaluate synthetic data quality through:

- Statistical distribution comparison.
- Correlation comparison.
- Category distribution comparison.
- Invalid record detection.
- Diversity.
- Coverage.
- Duplicate analysis.

Use appropriate SDV quality reports and supplementary validation metrics.

Do not claim synthetic data is automatically private or identical to real data.

Use a synthetic seed dataset by default, and document the limitations of training generative models on artificial seed data.

---

# 6. FRAUD SCENARIO SIMULATION ENGINE

Develop a configurable fraud simulation system.

Implement the following scenarios:

1. Unusually high-value transactions.
2. Rapid repeated purchases.
3. Multiple transactions within a short time.
4. Unusual device changes.
5. Shipping and billing mismatch.
6. Unusual transaction timings.
7. Abnormal transaction frequency.
8. Unusual customer purchasing patterns.
9. Transaction distribution shifts.
10. Previously unseen combinations of transaction features.

Features:
- Scenario selection.
- Scenario configuration.
- Scenario execution.
- Generation progress.
- Scenario results.
- Fraud statistics.
- Dataset export.
- Scenario history.

Keep the synthetic ground-truth fraud labels separate from model predictions.

---

# 7. DATA PREPROCESSING AND FEATURE ENGINEERING

Develop a reusable data preprocessing pipeline.

Include:
- Missing value handling.
- Duplicate detection.
- Data type validation.
- Categorical encoding.
- Numerical scaling.
- Outlier analysis.
- Feature engineering.
- Class imbalance analysis.
- Train/validation/test splitting.

Prevent data leakage.

Use chronological splits for time-dependent experiments where appropriate.

Keep fitted preprocessing transformations consistent between training and inference.

---

# 8. FRAUD DETECTION MACHINE LEARNING ENGINE

Implement the following models:

1. Logistic Regression.
2. Random Forest.
3. XGBoost.
4. Isolation Forest as an optional anomaly detection baseline.

Features:
- Model selection.
- Dataset selection.
- Training configuration.
- Model training.
- Hyperparameter tuning.
- Model saving.
- Model loading.
- Prediction.
- Model comparison.
- Experiment tracking.

Evaluation metrics:
- Accuracy.
- Precision.
- Recall.
- F1-score.
- ROC-AUC.
- PR-AUC.
- Confusion matrix.
- False positive rate.
- False negative rate.
- Calibration metrics.

Prioritize fraud recall and precision-recall evaluation because the dataset may have significant class imbalance.

Do not select a model using accuracy alone.

---

# 9. MODEL ROBUSTNESS EVALUATION ENGINE

This is the central research contribution of the project.

Build a comprehensive framework to evaluate whether synthetic data augmentation improves fraud detection robustness.

## Robustness Testing Scenarios

1. Different fraud percentages.
2. Class imbalance.
3. Transaction amount distribution changes.
4. Temporal data drift.
5. Missing input values.
6. Noisy input features.
7. Unseen fraud scenarios.
8. Customer behavior changes.
9. Changes in transaction frequency.
10. Distribution shifts in product categories.

## Experimental Comparisons

Experiment A:
Train on baseline synthetic dataset and test on held-out baseline data.

Experiment B:
Train on augmented synthetic dataset and test on the same held-out baseline data.

Experiment C:
Train on baseline data and test on shifted distributions.

Experiment D:
Train on augmented data and test on shifted distributions.

Experiment E:
Train on baseline data and test on unseen fraud patterns.

Experiment F:
Train on augmented data and test on unseen fraud patterns.

## Evaluation Metrics

Calculate:
- Precision.
- Recall.
- F1-score.
- ROC-AUC.
- PR-AUC.
- False positive rate.
- False negative rate.
- Recall at specified false positive rates.
- Performance degradation.
- Calibration error.

## Robustness Dashboard

Create:
- Baseline versus augmented comparison.
- Distribution drift charts.
- Performance degradation charts.
- Robustness scorecard.
- Confusion matrices.
- Experiment comparison tables.

Define every robustness score transparently.

Use consistent held-out test sets and reproducible experiment configurations.

Do not assume synthetic augmentation improves performance. Report actual results, including cases where performance decreases.

---

# 10. EXPLAINABLE AI ENGINE

Integrate SHAP.

Features:
- Global feature importance.
- Individual prediction explanation.
- SHAP summary plot.
- Feature contribution analysis.
- Transaction-level explanation.

For every fraud prediction, provide:
- Predicted class.
- Fraud probability or anomaly score.
- Risk category.
- Important contributing features.
- Explanation of model behavior.

Make clear that model explanations are not proof of actual fraud.

---

# 11. TRANSACTION MONITORING

Create an interactive transaction monitoring page.

Include:
- Transaction table.
- Transaction search.
- Amount filters.
- Date filters.
- Fraud/legitimate filters.
- Risk classification.
- Transaction details.
- Prediction history.

Provide simulated live transaction streaming using WebSockets or Server-Sent Events.

When the stream is running:
- New synthetic transactions should appear.
- Predictions should be displayed.
- Fraud alerts should be generated.
- Dashboard statistics should update.

Clearly label this as a simulated transaction stream, not a connection to real payment networks.

---

# 12. BACKEND DEVELOPMENT

Use FastAPI with modular architecture.

Create endpoints for:

### Dataset
- Generate dataset.
- Get dataset list.
- Get dataset details.
- Preview dataset.
- Get dataset statistics.
- Download dataset.

### Generative AI
- Train CTGAN.
- Train TVAE.
- Generate synthetic records.
- Evaluate synthetic quality.

### Fraud Simulation
- Get available scenarios.
- Configure scenario.
- Execute scenario.
- Get scenario results.

### Machine Learning
- Train model.
- Get model list.
- Compare models.
- Make predictions.
- Get prediction history.

### Robustness
- Run robustness tests.
- Evaluate data drift.
- Evaluate class imbalance.
- Evaluate noise sensitivity.
- Evaluate unseen fraud scenarios.
- Compare experiment results.

### Explainable AI
- Get global SHAP importance.
- Get individual SHAP explanation.

### Experiments
- Create experiment.
- Get experiment history.
- Get experiment details.
- Export reports.

### System
- Authentication.
- Health checks.
- System status.
- User settings.

Implement:
- Pydantic validation.
- Error handling.
- Logging.
- API documentation.
- Authentication.
- Authorization.
- Background jobs.
- Progress updates.
- Pagination.
- Rate limiting for sensitive endpoints where appropriate.

Use FastAPI Swagger documentation.

---

# 13. DATABASE ARCHITECTURE

Use PostgreSQL.

Create database tables for:

1. Users.
2. Datasets.
3. Dataset metadata.
4. Generation configurations.
5. Generative model metadata.
6. Fraud scenarios.
7. Training experiments.
8. ML models.
9. Model metrics.
10. Predictions.
11. Robustness evaluations.
12. Experiment history.
13. Reports.
14. Notifications.

Implement:
- Proper primary keys.
- Foreign keys.
- Relationships.
- Database migrations.
- Indexing.
- Data validation.

Use database persistence for important project outputs.

Store large datasets and model artifacts in a suitable file or object storage layer and maintain references in the database.

---

# 14. EXPERIMENT MANAGEMENT AND MLFLOW

Integrate MLflow.

Track:
- Experiment names.
- Dataset versions.
- Generation methods.
- Model parameters.
- Training metrics.
- Evaluation metrics.
- Model artifacts.
- Timestamps.
- Robustness configurations.

Provide an experiment management interface.

Users should be able to view and compare previous experiments.

---

# 15. COMPLETE INDIVIDUAL FRONTEND PAGES

Implement all 32 sidebar pages as individual React components.

Every page must include its own:
- Page heading.
- Description.
- Controls.
- Data visualizations.
- Tables where relevant.
- API integration.
- Loading state.
- Error state.
- Empty state.

Do not create 32 identical placeholder pages.

Implement their actual functionality progressively.

Use reusable components such as:

- Sidebar.
- Topbar.
- Breadcrumb.
- MetricCard.
- ChartCard.
- DataTable.
- SearchBar.
- FilterPanel.
- StatusBadge.
- Modal.
- NotificationPanel.
- LoadingSkeleton.
- EmptyState.
- PageHeader.
- ConfigurationPanel.
- ProgressIndicator.

---

# 16. REAL-TIME APPLICATION FUNCTIONALITY

The application must support real-time dynamic behavior.

Use:
- FastAPI REST APIs.
- WebSockets or Server-Sent Events.
- Background processing.
- Database persistence.
- Job status management.

Show real-time progress for:
- Dataset generation.
- CTGAN training.
- TVAE training.
- ML model training.
- Fraud simulation.
- Robustness evaluation.

Update the interface when operations finish.

Provide:
- Running status.
- Completed status.
- Failed status.
- Progress percentage.
- Relevant error messages.

Do not display fake progress percentages or claim completion before the actual job finishes.

---

# 17. USER AUTHENTICATION AND SECURITY

Implement a secure authentication system.

Include:
- Registration.
- Login.
- Logout.
- Password hashing.
- JWT authentication.
- Protected routes.
- User profile.
- Role-based access where required.

Security requirements:
- Validate all user inputs.
- Protect sensitive endpoints.
- Use environment variables.
- Never expose API keys.
- Never commit .env files.
- Use a safe .env.example.
- Avoid SQL injection.
- Restrict uploaded file types and sizes.
- Avoid executing arbitrary uploaded content.

Use synthetic data by default.

---

# 18. REPORTS AND EXPORTS

Implement downloadable reports.

Provide:
- Synthetic dataset CSV.
- Synthetic dataset JSON.
- Data quality report.
- Fraud detection performance report.
- Model comparison report.
- Robustness evaluation report.
- Experiment summary.

Provide PDF and CSV export where appropriate.

Include:
- Experiment configuration.
- Dataset information.
- Model details.
- Evaluation metrics.
- Charts.
- Research findings.
- Limitations.

Reports must use actual experiment results.

---

# 19. COMPLETE PROJECT FOLDER STRUCTURE

Create a modular structure similar to:

retail-fraud-intelligence-platform/

    frontend/
        src/
            components/
            layouts/
            pages/
                dashboard/
                synthetic-data/
                generative-models/
                dataset-explorer/
                data-quality/
                fraud-detection/
                fraud-simulator/
                transaction-monitoring/
                fraud-analysis/
                risk-analysis/
                model-training/
                model-comparison/
                model-registry/
                model-prediction/
                robustness/
                data-drift/
                imbalance/
                noise-testing/
                unseen-fraud/
                performance/
                explainability/
                experiments/
                reports/
                settings/
                users/
                system/
            services/
            hooks/
            context/
            routes/
            types/
            utils/

    backend/
        app/
            api/
            core/
            database/
            models/
            schemas/
            services/
            middleware/
            workers/

    synthetic_data/
        generators/
        statistical/
        rule_based/
        ctgan/
        tvae/
        validation/

    fraud_detection/
        preprocessing/
        feature_engineering/
        training/
        prediction/
        saved_models/

    fraud_scenarios/
        generators/
        configurations/
        evaluation/

    robustness_evaluation/
        drift/
        imbalance/
        noise/
        unseen_scenarios/
        metrics/
        reports/

    explainability/
        shap/
        feature_importance/

    experiments/
    datasets/
    artifacts/
    tests/
        backend/
        frontend/
        integration/
        e2e/

    docs/
    docker/

    AGENTS.md
    README.md
    PROJECT_REQUIREMENTS.md
    SYSTEM_ARCHITECTURE.md
    DATABASE_SCHEMA.md
    API_DOCUMENTATION.md
    MODEL_EVALUATION.md
    INSTALLATION_GUIDE.md
    TESTING_GUIDE.md

    docker-compose.yml
    .env.example
    .gitignore

Adapt the structure when needed, but maintain clear separation of responsibilities.

---

# 20. TESTING AND QUALITY ASSURANCE

Write automated tests for:

- Data generation.
- Generative models.
- Synthetic data validation.
- Fraud scenario simulation.
- Preprocessing.
- Feature engineering.
- ML training.
- Prediction.
- Robustness evaluation.
- SHAP explanations.
- API endpoints.
- Database operations.
- Frontend components.
- Frontend/backend integration.
- End-to-end workflows.

Run tests regularly.

Fix errors before proceeding to dependent modules.

Verify that every important UI button performs its advertised action.

Do not use mocked responses as final production functionality.

Mock external dependencies only in isolated tests.

---

# 21. DEPLOYMENT

Prepare a complete local and deployment environment.

Implement:
- Frontend Dockerfile.
- Backend Dockerfile.
- PostgreSQL service.
- Redis service if background workers require it.
- MLflow service.
- Docker Compose.
- Environment configuration.
- Database migrations.
- Health checks.
- Startup instructions.

The entire project should be startable with documented commands.

For example:

docker compose up --build

Ensure the local application is accessible through documented frontend and backend addresses.

---

# 22. DOCUMENTATION

Create comprehensive documentation:

1. README.md
2. AGENTS.md
3. PROJECT_REQUIREMENTS.md
4. SYSTEM_ARCHITECTURE.md
5. DATABASE_SCHEMA.md
6. API_DOCUMENTATION.md
7. MODEL_EVALUATION.md
8. INSTALLATION_GUIDE.md
9. TESTING_GUIDE.md
10. DEPLOYMENT_GUIDE.md

Explain:
- Project objectives.
- Research motivation.
- System architecture.
- Data generation techniques.
- Fraud simulation methodology.
- Machine learning algorithms.
- Robustness evaluation.
- Experimental methodology.
- Results and limitations.
- Installation.
- Execution.
- Deployment.

---

# 23. DEVELOPMENT EXECUTION STRATEGY

IMPORTANT: Do not generate the entire application in one uncontrolled operation.

Work as a senior engineering team and complete the project in phases.

### PHASE 1: REQUIREMENT ANALYSIS AND ARCHITECTURE

Analyze all requirements.

Prepare:
- Architecture diagram.
- Folder structure.
- Database schema.
- API specification.
- UI/UX page structure.
- Module dependencies.
- Development roadmap.

Do not start full implementation until I approve the architecture.

### PHASE 2: FRONTEND SHELL AND DESIGN SYSTEM

Build:
- Sidebar.
- Topbar.
- Breadcrumbs.
- Routing.
- Design system.
- Dashboard layout.
- All 32 catalog page layouts.
- Light and dark themes.
- Responsive behavior.

Make sure each sidebar item opens the correct individual route.

Verify navigation before moving forward.

### PHASE 3: BACKEND AND DATABASE FOUNDATION

Implement:
- FastAPI.
- PostgreSQL.
- SQLAlchemy.
- Database migrations.
- Authentication.
- API structure.
- Background jobs.
- Logging.

Verify connectivity.

### PHASE 4: SYNTHETIC DATA GENERATION

Implement:
- Rule-based generation.
- Statistical generation.
- CTGAN.
- TVAE.
- Dataset validation.
- Export functionality.

### PHASE 5: FRAUD SCENARIO SIMULATION

Implement all configured fraud scenarios.

### PHASE 6: MACHINE LEARNING

Implement:
- Preprocessing.
- Feature engineering.
- Model training.
- Prediction.
- Model comparison.

### PHASE 7: ROBUSTNESS EVALUATION

Implement all robustness experiments and evaluation metrics.

### PHASE 8: EXPLAINABLE AI

Integrate SHAP and feature importance.

### PHASE 9: FRONTEND AND BACKEND INTEGRATION

Connect every page with real backend APIs.

### PHASE 10: REAL-TIME FEATURES

Implement progress tracking, transaction simulation and notifications.

### PHASE 11: TESTING

Run unit, integration and end-to-end tests.

Fix confirmed issues.

### PHASE 12: DEPLOYMENT AND DOCUMENTATION

Complete Docker setup, deployment configuration and documentation.

---

# 24. IMPORTANT CODING RULES

Follow these rules throughout the project:

1. Inspect existing files before modifying them.
2. Preserve existing working functionality.
3. Do not create duplicate files or components.
4. Use modular, maintainable code.
5. Follow clean coding principles.
6. Use reusable services and components.
7. Handle errors properly.
8. Validate all inputs.
9. Use environment variables for secrets.
10. Write meaningful comments and documentation.
11. Run tests after meaningful changes.
12. Keep the application runnable at each major milestone.
13. Do not fabricate API responses, metrics or experiment results.
14. Do not use hardcoded dashboard statistics.
15. Do not silently skip requirements.
16. Do not claim a feature is complete without testing it.
17. Do not remove existing functionality without approval.
18. Keep README and AGENTS.md updated.

If a dependency is unavailable, investigate a compatible alternative and explain the change.

If a feature is too resource-intensive for the local machine, provide a configurable lightweight implementation and document the limitation.

---

# 25. FINAL ACCEPTANCE CRITERIA

The project is complete only when:

1. The full website runs successfully.
2. The premium sidebar and all 32 catalog routes work.
3. Each module has its own meaningful page.
4. Frontend and backend are integrated.
5. Database persistence works.
6. Users can generate synthetic transaction datasets.
7. CTGAN and TVAE integrations work.
8. Fraud scenarios can be generated.
9. ML models can be trained.
10. Transactions can be classified.
11. Robustness experiments can be executed.
12. Baseline and augmented models can be compared.
13. SHAP explanations work.
14. Real-time progress updates work.
15. Dashboard values come from actual results.
16. Datasets and reports can be downloaded.
17. Authentication and security are implemented.
18. Automated tests pass or documented limitations remain.
19. Docker deployment works.
20. Complete documentation is available.

The final result must be a professional Retail Fraud Intelligence Platform that demonstrates the entire research workflow, from synthetic transaction generation to fraud detection and model robustness evaluation.

---

# 26. FIRST ACTION – START NOW

Start by analyzing this entire project specification.

Do not immediately generate thousands of lines of code.

First provide:

1. Your understanding of the project.
2. Complete system architecture.
3. Architecture diagram.
4. Complete folder structure.
5. Database schema.
6. All 32 frontend pages and their functionality.
7. Backend API specification.
8. Synthetic data generation methodology.
9. Fraud detection methodology.
10. Robustness experiment methodology.
11. Development phases and dependencies.
12. Local hardware and resource requirements.

Identify missing requirements and technical risks.

Then wait for my approval.

After approval, start Phase 2 by creating the premium frontend shell, complete left sidebar, individual page routing, top navigation and responsive design.

Proceed phase by phase until the entire application is implemented, integrated, tested and ready to demonstrate.

Your responsibility is not just to generate code. Your responsibility is to build, execute, verify and document the complete working application.