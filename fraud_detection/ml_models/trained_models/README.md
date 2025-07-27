# Trained Models Directory

This directory is where the real fraud detection models will be stored once they are trained.

## Model File Structure

The expected structure for model files:

```
fraud_model.pkl  # Main model file (joblib/pickle format)
```

## Model File Format

The model file should contain a dictionary with the following structure:

```python
{
    'model': trained_model_object,  # The actual trained model (sklearn, xgboost, etc.)
    'scaler': preprocessing_scaler,  # Feature scaler (StandardScaler, MinMaxScaler, etc.)
    'feature_names': ['feature1', 'feature2', ...],  # List of feature names
    'metadata': {
        'version': 'v1.0',
        'trained_at': '2024-01-01T00:00:00',
        'training_data_size': 100000,
        'performance_metrics': {
            'accuracy': 0.95,
            'precision': 0.92,
            'recall': 0.88,
            'f1_score': 0.90,
            'auc_roc': 0.96
        },
        'feature_importance': {
            'feature1': 0.25,
            'feature2': 0.20,
            # ...
        }
    }
}
```

## Integration Instructions

1. Train your fraud detection model using your preferred ML framework
2. Save the model in the format described above
3. Place the file as `fraud_model.pkl` in this directory
4. The platform will automatically detect and load the model
5. The system will switch from mock predictions to real predictions

## Supported Model Types

- Scikit-learn models (RandomForest, SVM, LogisticRegression, etc.)
- XGBoost models
- LightGBM models
- Any model that implements `predict()` and optionally `predict_proba()` methods

## Feature Engineering

The current mock model expects these features:
- `montant`: Transaction amount (float)
- `trx_type`: Transaction type (string: TRF, RT, RCD, PF)
- `trx_time`: Transaction time (string: HH:MM:SS)
- `client_i`: Source client ID (string)
- `client_b`: Destination client ID (string)
- `bank_i`: Source bank code (string)
- `bank_b`: Destination bank code (string)

You can modify the `_preprocess_features()` method in `model_interface.py` to match your model's feature requirements.

## Testing

Before deploying your model:

1. Test it with the mock data to ensure compatibility
2. Verify the prediction format matches the expected output
3. Check performance metrics are reasonable
4. Ensure the model loads without errors

## Monitoring

The platform provides model monitoring through:
- Prediction logging
- Performance tracking
- Error handling and fallback to mock model
- Model status API endpoints

## Example Model Training Script

```python
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Load and prepare your training data
# df = pd.read_csv('training_data.csv')
# X = df[feature_columns]
# y = df['is_fraud']

# Train model
# X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
# scaler = StandardScaler()
# X_train_scaled = scaler.fit_transform(X_train)
# model = RandomForestClassifier(n_estimators=100, random_state=42)
# model.fit(X_train_scaled, y_train)

# Save model
# model_data = {
#     'model': model,
#     'scaler': scaler,
#     'feature_names': feature_columns,
#     'metadata': {
#         'version': 'v1.0',
#         'trained_at': datetime.now().isoformat(),
#         # ... other metadata
#     }
# }
# joblib.dump(model_data, 'fraud_model.pkl')
```

