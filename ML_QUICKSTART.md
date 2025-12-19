# ML Pipeline Quick Start Guide

## Prerequisites

Install required packages:
```bash
pip install -r requirements.txt
```

## Step-by-Step Setup

### 1. Prepare Your Dataset

```bash
python ml/prepare_dataset.py --input updated_nyc_inspections.xlsx --output processed_dataset.csv
```

This creates `processed_dataset.csv` with all features ready for ML.

### 2. Train All Models

Run each training script:

```bash
# Grade prediction (A/B/C)
python ml/train_grade_model.py

# Critical violation prediction
python ml/train_critical_model.py

# Score forecasting
python ml/train_score_forecast.py

# Inspection date prediction
python ml/train_inspection_date_model.py
```

### 3. Verify Models

Check that models were created:
- `models/grade_model.pkl`
- `models/critical_model.pkl`
- `models/forecast_model.pkl`
- `models/inspection_date_model.pkl`

### 4. Use in Application

The models are automatically integrated. In your code:

```python
from backend.services.risk_forecast import (
    predict_next_grade,
    predict_next_score,
    predict_critical_violation
)

# Get predictions
grade_probs = predict_next_grade(restaurant_history_df)
score_pred = predict_next_score(restaurant_history_df)
critical_pred = predict_critical_violation(restaurant_history_df)
```

## Model Outputs

### Grade Prediction
```python
{
    "A": 0.7,  # 70% probability of Grade A
    "B": 0.25, # 25% probability of Grade B
    "C": 0.05  # 5% probability of Grade C
}
```

### Score Forecast
```python
{
    "score": 15.5,
    "confidence_interval": [12.0, 19.0]
}
```

### Critical Violation
```python
{
    "probability": 0.3,  # 30% chance of critical violation
    "has_critical": False
}
```

## Troubleshooting

**Models not loading?**
- Ensure models are in `models/` directory
- Check that feature maps (`.json` files) exist
- Application will use heuristics as fallback

**Training fails?**
- Ensure `processed_dataset.csv` exists
- Check that you have enough data (need multiple inspections per restaurant)
- Verify all required packages are installed

**SHAP not working?**
- Install: `pip install shap`
- SHAP is optional - models work without it

## Performance Tips

- Models are cached after first load
- Use `get_shap_explanations()` sparingly (computationally expensive)
- Retrain models periodically as new data arrives

