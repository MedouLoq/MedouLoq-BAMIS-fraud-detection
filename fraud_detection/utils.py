import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from decimal import Decimal

# Import the model interface
from .ml_models.model_interface import get_fraud_prediction, get_batch_fraud_predictions, get_model_status

# Import Claude integration
from .claude_integration import analyze_transaction_with_claude, analyze_client_with_claude, is_claude_available

logger = logging.getLogger(__name__)

def calculate_client_features(client_id: str) -> Dict[str, float]:
    """Calculer les features avancées pour un client"""
    from .models import RawTransaction
    
    try:
        # Transactions du client (30 derniers jours)
        cutoff_date = timezone.now() - timedelta(days=30)
        client_transactions = RawTransaction.objects.filter(
            Q(client_i=client_id) | Q(client_b=client_id),
            uploaded_at__gte=cutoff_date
        )
        
        # Transactions envoyées par le client
        sent_transactions = client_transactions.filter(client_i=client_id)
        
        features = {}
        
        # TRANSACTION_COUNT: Nombre de transactions envoyées
        features['transaction_count'] = sent_transactions.count()
        
        # FAILED_TRANSACTION_COUNT: Transactions échouées
        features['failed_transaction_count'] = sent_transactions.filter(etat='KO').count()
        
        # CLIENT_I_UNIQUE_BANKS: Banques uniques utilisées par le client
        unique_banks = sent_transactions.values_list('bank_i', flat=True).distinct().count()
        features['client_i_unique_banks'] = unique_banks
        
        # CLIENT_I_UNIQUE_BENEFICIARIES: Bénéficiaires uniques
        unique_beneficiaires = sent_transactions.values_list('client_b', flat=True).distinct().count()
        features['client_i_unique_beneficiaries'] = unique_beneficiaires
        
        # MONTANT_DEVIATION: Écart type des montants
        if sent_transactions.exists():
            montants = [float(t.montant) for t in sent_transactions]
            if len(montants) > 1:
                import statistics
                features['montant_deviation'] = statistics.stdev(montants)
            else:
                features['montant_deviation'] = 0.0
        else:
            features['montant_deviation'] = 0.0
        
        return features
        
    except Exception as e:
        logger.error(f"Error calculating client features for {client_id}: {e}")
        return {
            'transaction_count': 0,
            'failed_transaction_count': 0,
            'client_i_unique_banks': 0,
            'client_i_unique_beneficiaries': 0,
            'montant_deviation': 0.0
        }

def calculate_beneficiary_features(client_b_id: str) -> Dict[str, float]:
    """Calculer les features pour un bénéficiaire"""
    from .models import RawTransaction
    
    try:
        # Transactions vers ce bénéficiaire (30 derniers jours)
        cutoff_date = timezone.now() - timedelta(days=30)
        received_transactions = RawTransaction.objects.filter(
            client_b=client_b_id,
            uploaded_at__gte=cutoff_date
        )
        
        features = {}
        
        # CLIENT_B_UNIQUE_INITIATORS: Nombre d'initiateurs uniques
        unique_initiators = received_transactions.values_list('client_i', flat=True).distinct().count()
        features['client_b_unique_initiators'] = unique_initiators
        
        # CLIENT_B_UNIQUE_BANKS: Banques uniques utilisées
        unique_banks = received_transactions.values_list('bank_b', flat=True).distinct().count()
        features['client_b_unique_banks'] = unique_banks
        
        return features
        
    except Exception as e:
        logger.error(f"Error calculating beneficiary features for {client_b_id}: {e}")
        return {
            'client_b_unique_initiators': 0,
            'client_b_unique_banks': 0
        }

def apply_fraud_detection_model(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """Appliquer le modèle de détection de fraude à une transaction"""
    try:
        # Calculer les features avancées
        client_features = calculate_client_features(transaction_data.get('client_i', ''))
        beneficiary_features = calculate_beneficiary_features(transaction_data.get('client_b', ''))
        
        # Préparer les données complètes pour le modèle
        ml_input_data = {
            'trx': transaction_data.get('trx', ''),
            'montant': float(transaction_data.get('montant', 0)),
            'trx_type': transaction_data.get('trx_type', 'TRF'),
            'trx_time': transaction_data.get('trx_time', ''),
            'client_i': transaction_data.get('client_i', ''),
            'client_b': transaction_data.get('client_b', ''),
            'bank_i': transaction_data.get('bank_i', ''),
            'bank_b': transaction_data.get('bank_b', ''),
            'etat': transaction_data.get('etat', 'OK'),
            'mls': transaction_data.get('mls', 0),
            
            # Features calculées
            **client_features,
            **beneficiary_features
        }
        
        # Obtenir la prédiction du modèle
        prediction = get_fraud_prediction(ml_input_data)
        
        logger.info(f"Fraud prediction for transaction {ml_input_data.get('trx')}: "
                   f"fraud={prediction.get('is_fraud')}, "
                   f"risk={prediction.get('risk_score', 0):.3f}")
        
        return prediction
        
    except Exception as e:
        logger.error(f"Error applying fraud detection model: {e}")
        return {
            'is_fraud': False,
            'risk_score': 0.0,
            'confidence': 0.0,
            'feature_importance': {},
            'model_version': 'error',
            'error': str(e),
            'prediction_time': datetime.now().isoformat()
        }

def generate_claude_analysis(transaction) -> Dict[str, Any]:
    """Générer une analyse Claude pour une transaction"""
    try:
        if is_claude_available():
            analysis = analyze_transaction_with_claude(transaction)
            
            result = {
                'priority': analysis.get('priority', 'MEDIUM'),
                'risk_factors': analysis.get('risk_factors', []),
                'explanation': analysis.get('explanation', 'Analyse effectuée'),
                'recommendations': analysis.get('recommendations', []),
                'confidence': analysis.get('confidence', 0.5),
                'model_used': analysis.get('claude_model', 'claude-3-sonnet'),
                'analysis_timestamp': analysis.get('analyzed_at', timezone.now().isoformat())
            }
        else:
            result = _generate_mock_claude_analysis(transaction)
        
        logger.info(f"Claude analysis completed for transaction {transaction.trx}: "
                   f"priority={result['priority']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in Claude analysis for transaction {transaction.trx}: {e}")
        return _generate_mock_claude_analysis(transaction)

def generate_claude_client_analysis(client) -> Dict[str, Any]:
    """Générer une analyse Claude pour un client"""
    try:
        if is_claude_available():
            analysis = analyze_client_with_claude(client)
            
            result = {
                'risk_level': analysis.get('risk_level', 'NORMAL'),
                'behavioral_patterns': analysis.get('behavioral_patterns', []),
                'assessment': analysis.get('assessment', 'Analyse effectuée'),
                'surveillance_recommendations': analysis.get('surveillance_recommendations', []),
                'confidence': analysis.get('confidence', 0.5),
                'model_used': analysis.get('claude_model', 'claude-3-sonnet'),
                'analysis_timestamp': analysis.get('analyzed_at', timezone.now().isoformat())
            }
        else:
            result = _generate_mock_client_analysis(client)
        
        logger.info(f"Claude client analysis completed for {client.client_id}: "
                   f"risk_level={result['risk_level']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in Claude client analysis for {client.client_id}: {e}")
        return _generate_mock_client_analysis(client)

def _generate_mock_claude_analysis(transaction) -> Dict[str, Any]:
    """Générer une analyse Claude fictive"""
    montant = float(getattr(transaction, 'montant', 0))
    
    if montant > 50000:
        priority = "HIGH"
        risk_factors = ["montant_très_élevé", "transaction_suspecte"]
        explanation = f"Transaction de {montant} MRU détectée. Montant très élevé nécessitant une attention particulière."
    elif montant > 20000:
        priority = "MEDIUM"
        risk_factors = ["montant_élevé"]
        explanation = f"Transaction de {montant} MRU. Montant élevé à surveiller."
    else:
        priority = "LOW"
        risk_factors = []
        explanation = f"Transaction de {montant} MRU. Montant dans la normale."
    
    # Ajouter des facteurs de risque additionnels
    if hasattr(transaction, 'client_i') and hasattr(transaction, 'client_b'):
        if transaction.client_i == transaction.client_b:
            risk_factors.append("auto_transfert")
    
    if hasattr(transaction, 'etat') and transaction.etat == 'KO':
        risk_factors.append("transaction_échouée")
        priority = "HIGH"
    
    return {
        'priority': priority,
        'risk_factors': risk_factors,
        'explanation': explanation,
        'recommendations': ["Surveillance continue", "Vérification manuelle si nécessaire"],
        'confidence': 0.75,
        'model_used': 'mock',
        'analysis_timestamp': datetime.now().isoformat()
    }

def _generate_mock_client_analysis(client) -> Dict[str, Any]:
    """Générer une analyse client fictive"""
    fraud_rate = getattr(client, 'fraud_rate', 0)
    total_transactions = getattr(client, 'total_transactions_sent', 0) + getattr(client, 'total_transactions_received', 0)
    
    if fraud_rate > 15:
        risk_level = "SUSPECT"
        patterns = ["taux_fraude_critique", "comportement_très_suspect"]
        assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Profil critique."
        recommendations = ["Blocage temporaire", "Investigation approfondie"]
    elif fraud_rate > 10:
        risk_level = "WATCH"
        patterns = ["taux_fraude_élevé", "comportement_suspect"]
        assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Profil à haut risque."
        recommendations = ["Surveillance renforcée", "Limitation des montants"]
    elif fraud_rate > 5:
        risk_level = "WATCH"
        patterns = ["taux_fraude_modéré"]
        assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Surveillance recommandée."
        recommendations = ["Surveillance régulière"]
    else:
        risk_level = "NORMAL"
        patterns = ["comportement_normal"]
        assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Profil normal."
        recommendations = ["Surveillance standard"]
    
    return {
        'risk_level': risk_level,
        'behavioral_patterns': patterns,
        'assessment': assessment,
        'surveillance_recommendations': recommendations,
        'confidence': 0.75,
        'model_used': 'mock',
        'analysis_timestamp': timezone.now().isoformat()
    }

# Reste des fonctions utilities inchangées...
def update_client_statistics(client_id: str):
    """Met à jour les statistiques du client"""
    try:
        from .models import Client, RawTransaction
        
        client, created = Client.objects.get_or_create(client_id=client_id)
        
        # Calculer les statistiques pour toutes les transactions du client
        all_transactions = RawTransaction.objects.filter(
            Q(client_i=client_id) | Q(client_b=client_id)
        )
        
        # Statistiques des transactions envoyées
        sent_stats = RawTransaction.objects.filter(client_i=client_id).aggregate(
            count=Count('id'),
            total_amount=Sum('montant'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True))
        )
        
        # Statistiques des transactions reçues
        received_stats = RawTransaction.objects.filter(client_b=client_id).aggregate(
            count=Count('id'),
            total_amount=Sum('montant')
        )
        
        # Statistiques globales
        all_stats = all_transactions.aggregate(
            total_count=Count('id'),
            total_fraud_count=Count('id', filter=Q(ml_is_fraud=True)),
            total_amount=Sum('montant')
        )
        
        # Mettre à jour les champs du client
        client.total_transactions_sent = sent_stats['count'] or 0
        client.total_transactions_received = received_stats['count'] or 0
        client.total_amount_sent = sent_stats['total_amount'] or Decimal('0')
        client.total_amount_received = received_stats['total_amount'] or Decimal('0')
        client.fraud_transactions_count = all_stats['total_fraud_count'] or 0
        
        # Calculer le taux de fraude
        total_transactions = all_stats['total_count'] or 0
        if total_transactions > 0:
            client.fraud_rate = (client.fraud_transactions_count / total_transactions) * 100
        else:
            client.fraud_rate = 0.0
        
        # Mettre à jour les dates
        first_txn = all_transactions.order_by('uploaded_at').first()
        last_txn = all_transactions.order_by('-uploaded_at').first()
        
        if first_txn:
            client.first_transaction_date = first_txn.uploaded_at
        if last_txn:
            client.last_transaction_date = last_txn.uploaded_at
        
        client.save()
        
        logger.debug(f"Updated statistics for client {client_id}: "
                    f"{total_transactions} transactions, {client.fraud_transactions_count} frauds")
        
    except Exception as e:
        logger.error(f"Error updating client statistics for {client_id}: {e}")

def update_bank_statistics(bank_code: str):
    """Met à jour les statistiques de la banque"""
    try:
        from .models import Bank, RawTransaction
        
        bank, created = Bank.objects.get_or_create(bank_code=bank_code)
        
        # Calculer les statistiques
        stats = RawTransaction.objects.filter(
            Q(bank_i=bank_code) | Q(bank_b=bank_code)
        ).aggregate(
            count=Count('id'),
            total_amount=Sum('montant'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True))
        )
        
        bank.total_transactions = stats['count'] or 0
        bank.total_amount = stats['total_amount'] or Decimal('0')
        bank.fraud_transactions = stats['fraud_count'] or 0
        
        bank.save()
        
        logger.debug(f"Updated statistics for bank {bank_code}")
        
    except Exception as e:
        logger.error(f"Error updating bank statistics for {bank_code}: {e}")

def get_client_ip(request):
    """Obtenir l'IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def generate_daily_insights():
    """Générer les insights quotidiens"""
    try:
        from .models import DailyInsight, RawTransaction
        
        today = timezone.now().date()
        
        if DailyInsight.objects.filter(date=today).exists():
            logger.info(f"Daily insights already exist for {today}")
            return
        
        # Statistiques du jour
        today_transactions = RawTransaction.objects.filter(
            uploaded_at__date=today
        )
        
        stats = today_transactions.aggregate(
            total=Count('id'),
            frauds=Count('id', filter=Q(ml_is_fraud=True)),
            total_amount=Sum('montant'),
            avg_amount=Avg('montant')
        )
        
        claude_summary = f"Analyse automatique: {stats['total']} transactions traitées, {stats['frauds']} fraudes détectées."
        
        # Créer l'insight quotidien
        DailyInsight.objects.create(
            date=today,
            fraud_count=stats['frauds'] or 0,
            total_amount_fraud=Decimal('0'),
            claude_summary=claude_summary
        )
        
        logger.info(f"Daily insights generated for {today}")
        
    except Exception as e:
        logger.error(f"Error generating daily insights: {e}")

def build_transaction_context(transaction) -> str:
    """Construire le contexte d'une transaction"""
    context_parts = []
    
    montant = float(getattr(transaction, 'montant', 0))
    
    if montant > 50000:
        context_parts.append("⚠️ MONTANT TRÈS ÉLEVÉ")
    elif montant > 20000:
        context_parts.append("⚠️ MONTANT ÉLEVÉ")
    
    if hasattr(transaction, 'client_i') and hasattr(transaction, 'client_b'):
        if transaction.client_i == transaction.client_b:
            context_parts.append("ℹ️ AUTO-TRANSACTION")
    
    if hasattr(transaction, 'etat') and transaction.etat == 'KO':
        context_parts.append("⚠️ TRANSACTION ÉCHOUÉE")
    
    return " | ".join(context_parts) if context_parts else "Contexte normal"

def calculate_transaction_velocity(client_id: str, hours: int = 24) -> Dict[str, Any]:
    """Calculer la vélocité des transactions"""
    try:
        from .models import RawTransaction
        
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        recent_transactions = RawTransaction.objects.filter(
            client_i=client_id,
            uploaded_at__gte=cutoff_time
        )
        
        stats = recent_transactions.aggregate(
            count=Count('id'),
            total_amount=Sum('montant'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True))
        )
        
        return {
            'transaction_count': stats['count'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
            'fraud_count': stats['fraud_count'] or 0,
            'velocity_per_hour': (stats['count'] or 0) / hours,
            'amount_per_hour': float(stats['total_amount'] or 0) / hours,
            'time_window_hours': hours
        }
        
    except Exception as e:
        logger.error(f"Error calculating transaction velocity for {client_id}: {e}")
        return {
            'transaction_count': 0,
            'total_amount': 0.0,
            'fraud_count': 0,
            'velocity_per_hour': 0.0,
            'amount_per_hour': 0.0,
            'time_window_hours': hours
        }

def get_transaction_patterns(client_id: str) -> Dict[str, Any]:
    """Analyser les patterns de transaction"""
    try:
        from .models import RawTransaction
        
        transactions = RawTransaction.objects.filter(
            Q(client_i=client_id) | Q(client_b=client_id)
        ).order_by('-uploaded_at')[:100]
        
        if not transactions:
            return {'patterns': [], 'analysis': 'Insufficient data'}
        
        patterns = []
        
        # Analyse des montants
        amounts = [float(t.montant) for t in transactions]
        avg_amount = sum(amounts) / len(amounts)
        max_amount = max(amounts)
        
        if max_amount > avg_amount * 5:
            patterns.append('unusual_high_amounts')
        
        return {
            'patterns': patterns,
            'analysis': f'Analyzed {len(transactions)} transactions',
            'avg_amount': avg_amount,
            'max_amount': max_amount,
            'transaction_count': len(transactions)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing transaction patterns for {client_id}: {e}")
        return {'patterns': [], 'analysis': 'Error in analysis'}

def get_model_performance_metrics() -> Dict[str, Any]:
    """Obtenir les métriques de performance du modèle"""
    try:
        return get_model_status()
    except Exception as e:
        logger.error(f"Error getting model performance metrics: {e}")
        return {
            'error': str(e),
            'status': 'unavailable'
        }