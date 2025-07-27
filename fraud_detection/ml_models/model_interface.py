import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuration des chemins
MODEL_DIR = Path(__file__).parent
MODEL_PATH = MODEL_DIR / "fraud_detection_model.pkl"

# Cache du modèle
_fraud_model = None

class FraudDetectionModel:
    """Classe wrapper pour le modèle de détection de fraude XGBoost"""
    
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.feature_importance = {}
        self.is_loaded = False
        
    def load_model(self) -> bool:
        """Charger le modèle"""
        try:
            if not MODEL_PATH.exists():
                logger.warning(f"Model file not found at {MODEL_PATH}")
                return self._load_dummy_model()
            
            # Charger le modèle principal
            with open(MODEL_PATH, 'rb') as f:
                self.model = pickle.load(f)
            
            # Définir les noms des features (ordre fixe basé sur l'importance fournie)
            self.feature_names = [
                'TRX_TYPE_ENCODED',
                'ETAT_ENCODED',
                'MONTANT',
                'FAILED_TRANSACTION_COUNT',
                'CLIENT_B_UNIQUE_INITIATORS',
                'TRANSACTION_COUNT',
                'MONTANT_DEVIATION',
                'CLIENT_I_UNIQUE_BANKS',
                'CLIENT_I_UNIQUE_BENEFICIARIES',
                'HOUR',
                'CLIENT_B_UNIQUE_BANKS',
                'MONTH',
                'DAY_OF_WEEK',
                'mls',
                'SELF_TRANSACTION'
            ]
            
            # Importance des features (valeurs fixes fournies)
            self.feature_importance = {
                'TRX_TYPE_ENCODED': 0.225605,
                'ETAT_ENCODED': 0.137922,
                'MONTANT': 0.132801,
                'FAILED_TRANSACTION_COUNT': 0.114793,
                'CLIENT_B_UNIQUE_INITIATORS': 0.098045,
                'TRANSACTION_COUNT': 0.065678,
                'MONTANT_DEVIATION': 0.052858,
                'CLIENT_I_UNIQUE_BANKS': 0.049341,
                'CLIENT_I_UNIQUE_BENEFICIARIES': 0.046755,
                'HOUR': 0.022550,
                'CLIENT_B_UNIQUE_BANKS': 0.016475,
                'MONTH': 0.014439,
                'DAY_OF_WEEK': 0.007877,
                'mls': 0.007699,
                'SELF_TRANSACTION': 0.007163
            }
            
            self.is_loaded = True
            logger.info(f"Real model loaded successfully from {MODEL_PATH}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return self._load_dummy_model()
    
    def _load_dummy_model(self) -> bool:
        """Charger un modèle factice pour les tests"""
        logger.info("Loading dummy model for testing purposes")
        
        class DummyModel:
            def predict(self, X):
                predictions = []
                for row in X:
                    # Règles simples basées sur les features importantes
                    montant = row[2]  # MONTANT est à l'index 2
                    trx_type = row[0]  # TRX_TYPE_ENCODED à l'index 0
                    etat = row[1]  # ETAT_ENCODED à l'index 1
                    
                    # Logique de détection simple
                    is_fraud = (montant > 50000 or 
                              trx_type == 1 or  # RT (Retrait) 
                              etat == 1)  # KO
                    predictions.append(1 if is_fraud else 0)
                
                return np.array(predictions)
            
            def predict_proba(self, X):
                predictions = self.predict(X)
                probas = []
                for pred in predictions:
                    if pred == 1:
                        probas.append([0.2, 0.8])  # Haute probabilité de fraude
                    else:
                        probas.append([0.9, 0.1])  # Faible probabilité de fraude
                return np.array(probas)
        
        self.model = DummyModel()
        self.feature_names = [
            'TRX_TYPE_ENCODED', 'ETAT_ENCODED', 'MONTANT', 'FAILED_TRANSACTION_COUNT',
            'CLIENT_B_UNIQUE_INITIATORS', 'TRANSACTION_COUNT', 'MONTANT_DEVIATION',
            'CLIENT_I_UNIQUE_BANKS', 'CLIENT_I_UNIQUE_BENEFICIARIES', 'HOUR',
            'CLIENT_B_UNIQUE_BANKS', 'MONTH', 'DAY_OF_WEEK', 'mls', 'SELF_TRANSACTION'
        ]
        
        self.feature_importance = {
            'TRX_TYPE_ENCODED': 0.225605, 'ETAT_ENCODED': 0.137922, 'MONTANT': 0.132801,
            'FAILED_TRANSACTION_COUNT': 0.114793, 'CLIENT_B_UNIQUE_INITIATORS': 0.098045,
            'TRANSACTION_COUNT': 0.065678, 'MONTANT_DEVIATION': 0.052858,
            'CLIENT_I_UNIQUE_BANKS': 0.049341, 'CLIENT_I_UNIQUE_BENEFICIARIES': 0.046755,
            'HOUR': 0.022550, 'CLIENT_B_UNIQUE_BANKS': 0.016475, 'MONTH': 0.014439,
            'DAY_OF_WEEK': 0.007877, 'mls': 0.007699, 'SELF_TRANSACTION': 0.007163
        }
        
        self.is_loaded = True
        return True
    
    def extract_features(self, transaction_data: Dict[str, Any]) -> np.ndarray:
        """Extraire les features d'une transaction à partir des données brutes"""
        features_dict = {}
        
        # Mappings pour l'encodage
        trx_type_map = {'TRF': 0, 'RT': 1, 'RCD': 2, 'PF': 3}
        etat_map = {'OK': 0, 'KO': 1, 'ATT': 2}

        # Features de base
        features_dict['MONTANT'] = float(transaction_data.get('montant', 0))
        features_dict['mls'] = int(transaction_data.get('mls', 0))
        features_dict['TRX_TYPE_ENCODED'] = trx_type_map.get(transaction_data.get('trx_type', 'TRF'), 0)
        features_dict['ETAT_ENCODED'] = etat_map.get(transaction_data.get('etat', 'OK'), 0)

        # Features temporelles
        try:
            if 'trx_time' in transaction_data and transaction_data['trx_time']:
                if isinstance(transaction_data['trx_time'], datetime):
                    trx_dt = transaction_data['trx_time']
                else:
                    # Essayer plusieurs formats de date
                    trx_time_str = str(transaction_data['trx_time'])
                    try:
                        trx_dt = pd.to_datetime(trx_time_str, format='%m/%d/%Y %H:%M')
                    except:
                        try:
                            trx_dt = pd.to_datetime(trx_time_str)
                        except:
                            raise ValueError(f"Cannot parse date: {trx_time_str}")
                
                features_dict['HOUR'] = trx_dt.hour
                features_dict['DAY_OF_WEEK'] = trx_dt.weekday()
                features_dict['MONTH'] = trx_dt.month
            else:
                # Valeurs par défaut
                features_dict['HOUR'] = 12
                features_dict['DAY_OF_WEEK'] = 0
                features_dict['MONTH'] = 1
        except Exception as e:
            logger.warning(f"Could not parse trx_time {transaction_data.get('trx_time')}: {e}")
            features_dict['HOUR'] = 12
            features_dict['DAY_OF_WEEK'] = 0
            features_dict['MONTH'] = 1

        # SELF_TRANSACTION
        features_dict['SELF_TRANSACTION'] = 1 if transaction_data.get('client_i') == transaction_data.get('client_b') else 0

        # Features calculées (pour l'instant des valeurs par défaut)
        # Ces valeurs devraient être calculées à partir de l'historique des transactions
        features_dict['FAILED_TRANSACTION_COUNT'] = transaction_data.get('failed_transaction_count', 0)
        features_dict['CLIENT_B_UNIQUE_INITIATORS'] = transaction_data.get('client_b_unique_initiators', 1)
        features_dict['TRANSACTION_COUNT'] = transaction_data.get('transaction_count', 1)
        features_dict['MONTANT_DEVIATION'] = transaction_data.get('montant_deviation', 0.0)
        features_dict['CLIENT_I_UNIQUE_BANKS'] = transaction_data.get('client_i_unique_banks', 1)
        features_dict['CLIENT_I_UNIQUE_BENEFICIARIES'] = transaction_data.get('client_i_unique_beneficiaries', 1)
        features_dict['CLIENT_B_UNIQUE_BANKS'] = transaction_data.get('client_b_unique_banks', 1)

        # Construire le tableau de features dans l'ordre correct
        features_array = []
        for feature_name in self.feature_names:
            features_array.append(features_dict.get(feature_name, 0.0))
        
        return np.array(features_array)
    
    def predict(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prédire si une transaction est frauduleuse"""
        if not self.is_loaded:
            if not self.load_model():
                return self._get_error_prediction("Model not loaded")
        
        try:
            # Extraire les features
            features = self.extract_features(transaction_data)
            features_2d = features.reshape(1, -1)
            
            # Faire la prédiction
            prediction = self.model.predict(features_2d)[0]
            
            # Obtenir les probabilités
            if hasattr(self.model, 'predict_proba'):
                probabilities = self.model.predict_proba(features_2d)[0]
                confidence = float(probabilities[1])  # Probabilité de fraude
            else:
                confidence = 0.8 if prediction == 1 else 0.2
            
            risk_score = confidence
            
            return {
                'is_fraud': bool(prediction),
                'risk_score': float(risk_score),
                'confidence': float(confidence),
                'feature_importance': self.feature_importance,
                'model_version': '1.0.0',
                'prediction_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return self._get_error_prediction(str(e))
    
    def predict_batch(self, transactions_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prédire pour un lot de transactions"""
        results = []
        for transaction_data in transactions_data:
            result = self.predict(transaction_data)
            results.append(result)
        return results
    
    def _get_error_prediction(self, error_msg: str) -> Dict[str, Any]:
        """Retourner une prédiction d'erreur"""
        return {
            'is_fraud': False,
            'risk_score': 0.0,
            'confidence': 0.0,
            'feature_importance': {},
            'model_version': 'error',
            'error': error_msg,
            'prediction_time': datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Obtenir le statut du modèle"""
        return {
            'is_loaded': self.is_loaded,
            'model_path': str(MODEL_PATH),
            'model_exists': MODEL_PATH.exists(),
            'feature_count': len(self.feature_names),
            'feature_names': self.feature_names,
            'model_type': 'XGBoost' if self.is_loaded else 'Unknown'
        }

# Instance globale du modèle
_fraud_model = FraudDetectionModel()

def get_fraud_prediction(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """Obtenir une prédiction de fraude pour une transaction"""
    return _fraud_model.predict(transaction_data)

def get_batch_fraud_predictions(transactions_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Obtenir des prédictions de fraude pour un lot de transactions"""
    return _fraud_model.predict_batch(transactions_data)

def get_model_status() -> Dict[str, Any]:
    """Obtenir le statut du modèle de détection de fraude"""
    return _fraud_model.get_status()

def load_model() -> bool:
    """Charger le modèle de détection de fraude"""
    return _fraud_model.load_model()

def update_model(model_path: str) -> bool:
    """Mettre à jour le modèle avec un nouveau fichier"""
    try:
        import shutil
        shutil.copy2(model_path, MODEL_PATH)
        
        global _fraud_model
        _fraud_model = FraudDetectionModel()
        return _fraud_model.load_model()
        
    except Exception as e:
        logger.error(f"Error updating model: {e}")
        return False

# Charger le modèle au démarrage
try:
    _fraud_model.load_model()
    logger.info("Fraud detection model initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize fraud detection model: {e}")