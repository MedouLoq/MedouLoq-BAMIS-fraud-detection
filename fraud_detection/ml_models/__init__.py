"""
Module de modèles d'apprentissage automatique pour la détection de fraude BAMIS
"""

from .model_interface import (
    get_fraud_prediction,
    get_batch_fraud_predictions,
    get_model_status,
    load_model,
    update_model
)

__all__ = [
    'get_fraud_prediction',
    'get_batch_fraud_predictions', 
    'get_model_status',
    'load_model',
    'update_model'
]

