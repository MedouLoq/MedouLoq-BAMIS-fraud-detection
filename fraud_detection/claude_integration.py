import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Configuration Claude
CLAUDE_API_KEY = getattr(settings, 'ANTHROPIC_API_KEY', os.getenv('ANTHROPIC_API_KEY'))
CLAUDE_MODEL = "claude-3-sonnet-20240229"
CLAUDE_MAX_TOKENS = 1500
CLAUDE_TEMPERATURE = 0.3

# Initialiser le client Claude
claude_client = None # Assurer que claude_client est toujours défini
try:
    import anthropic
    if CLAUDE_API_KEY:
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        logger.info("Claude client initialized successfully")
    else:
        logger.warning("Claude API key not found, using mock responses")
except ImportError:
    logger.warning("Anthropic library not installed, using mock responses")
except Exception as e:
    logger.error(f"Failed to initialize Claude client: {e}")

class ClaudeAnalyzer:
    """Analyseur Claude pour la détection de fraude"""
    
    def __init__(self):
        self.client = claude_client
        self.is_available = claude_client is not None
    
    def analyze_transaction(self, transaction, context_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyser une transaction avec Claude AI
        
        Args:
            transaction: Instance RawTransaction
            context_data: Données contextuelles additionnelles
            
        Returns:
            Dictionnaire avec l'analyse Claude
        """
        if not self.is_available:
            return self._generate_mock_analysis(transaction, "transaction")
        
        try:
            # Construire le contexte
            context = self._build_transaction_context(transaction, context_data)
            
            # Créer le prompt
            prompt = self._create_transaction_prompt(transaction, context)
            
            # Appeler Claude
            response = self._call_claude(prompt)
            
            # Parser la réponse
            analysis = self._parse_claude_response(response, "transaction")
            
            # Ajouter des métadonnées
            analysis.update({
                'analyzed_at': timezone.now().isoformat(),
                'transaction_id': transaction.trx,
                'claude_model': CLAUDE_MODEL,
                'analysis_type': 'transaction'
            })
            
            logger.info(f"Claude analysis completed for transaction {transaction.trx}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error in Claude transaction analysis: {e}")
            return self._generate_error_analysis(str(e), "transaction")
    
    def analyze_client(self, client, transactions_data: Optional[List] = None) -> Dict[str, Any]:
        """
        Analyser un profil client avec Claude AI
        
        Args:
            client: Instance Client
            transactions_data: Données des transactions du client
            
        Returns:
            Dictionnaire avec l'analyse Claude
        """
        if not self.is_available:
            return self._generate_mock_analysis(client, "client")
        
        try:
            # Construire le contexte client
            context = self._build_client_context(client, transactions_data)
            
            # Créer le prompt
            prompt = self._create_client_prompt(client, context)
            
            # Appeler Claude
            response = self._call_claude(prompt)
            
            # Parser la réponse
            analysis = self._parse_claude_response(response, "client")
            
            # Ajouter des métadonnées
            analysis.update({
                'analyzed_at': timezone.now().isoformat(),
                'client_id': client.client_id,
                'claude_model': CLAUDE_MODEL,
                'analysis_type': 'client'
            })
            
            logger.info(f"Claude analysis completed for client {client.client_id}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error in Claude client analysis: {e}")
            return self._generate_error_analysis(str(e), "client")
    
    def analyze_batch_transactions(self, transactions: List, max_batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        Analyser un lot de transactions avec Claude
        
        Args:
            transactions: Liste des transactions
            max_batch_size: Taille maximale du lot
            
        Returns:
            Liste des analyses Claude
        """
        results = []
        
        # Traiter par lots pour éviter les timeouts
        for i in range(0, len(transactions), max_batch_size):
            batch = transactions[i:i + max_batch_size]
            
            for transaction in batch:
                analysis = self.analyze_transaction(transaction)
                results.append(analysis)
        
        return results
    
    def _build_transaction_context(self, transaction, context_data: Optional[Dict] = None) -> str:
        """Construire le contexte pour l'analyse de transaction"""
        context_parts = []
        
        # Informations de base
        context_parts.append(f"Transaction effectuée le {transaction.uploaded_at}")
        
        # Informations sur les montants
        if hasattr(transaction, 'amount'):
            amount = transaction.amount
        else:
            amount = getattr(transaction, 'montant', 0)
        
        if amount > 10000:
            context_parts.append("⚠️ MONTANT ÉLEVÉ: Transaction de montant important")
        elif amount < 10:
            context_parts.append("⚠️ MONTANT FAIBLE: Transaction de très faible montant")
        
        # Informations temporelles
        if hasattr(transaction, 'trx_time'):
            trx_time = transaction.trx_time
            if isinstance(trx_time, str):
                try:
                    trx_time = datetime.fromisoformat(trx_time.replace('Z', '+00:00'))
                except:
                    trx_time = timezone.now()
            
            hour = trx_time.hour
            if hour < 6 or hour > 22:
                context_parts.append("⚠️ HEURE SUSPECTE: Transaction effectuée en dehors des heures normales")
        
        # Informations sur les clients
        if transaction.client_i == transaction.client_b:
            context_parts.append("ℹ️ AUTO-TRANSACTION: Transaction entre le même client")
        
        # Informations sur les banques
        if hasattr(transaction, 'bank_i') and hasattr(transaction, 'bank_b'):
            if transaction.bank_i != transaction.bank_b:
                context_parts.append("ℹ️ INTER-BANQUES: Transaction entre différentes banques")
        
        # Contexte additionnel fourni
        if context_data:
            if 'client_history' in context_data:
                context_parts.append(f"Historique client: {context_data['client_history']}")
            if 'recent_patterns' in context_data:
                context_parts.append(f"Patterns récents: {context_data['recent_patterns']}")
        
        return "\n".join(context_parts)
    
    def _build_client_context(self, client, transactions_data: Optional[List] = None) -> str:
        """Construire le contexte pour l'analyse client"""
        context_parts = []
        
        # Statistiques de base
        context_parts.append(f"Client enregistré depuis: {client.created_at}")
        context_parts.append(f"Nombre total de transactions: {client.total_transactions}")
        context_parts.append(f"Montant total: {client.total_amount} MRU")
        context_parts.append(f"Nombre de fraudes détectées: {client.fraud_count}")
        context_parts.append(f"Taux de fraude: {client.fraud_rate:.2f}%")
        
        # Analyse des patterns
        if client.fraud_rate > 10:
            context_parts.append("🚨 RISQUE ÉLEVÉ: Taux de fraude supérieur à 10%")
        elif client.fraud_rate > 5:
            context_parts.append("⚠️ RISQUE MODÉRÉ: Taux de fraude entre 5% et 10%")
        
        if client.total_amount > 100000:
            context_parts.append("💰 GROS VOLUME: Client avec un volume de transactions important")
        
        # Données des transactions si disponibles
        if transactions_data:
            context_parts.append(f"Données de {len(transactions_data)} transactions récentes analysées")
            
            # Analyser les patterns temporels
            recent_frauds = sum(1 for t in transactions_data if t.get('ml_is_fraud', False))
            if recent_frauds > 0:
                context_parts.append(f"⚠️ {recent_frauds} fraudes détectées dans les transactions récentes")
        
        return "\n".join(context_parts)
    
    def _create_transaction_prompt(self, transaction, context: str) -> str:
        """Créer le prompt pour l'analyse de transaction"""
        
        # Obtenir le montant correct
        if hasattr(transaction, 'amount'):
            amount = transaction.amount
        else:
            amount = getattr(transaction, 'montant', 0)
        
        prompt = f"""
Vous êtes un expert en détection de fraude bancaire pour la plateforme BAMIS. Analysez cette transaction pour détecter d'éventuelles fraudes.

DÉTAILS DE LA TRANSACTION:
- ID: {transaction.trx}
- Montant: {amount} MRU
- Type: {getattr(transaction, 'trx_type', 'N/A')}
- Client source: {getattr(transaction, 'client_i', 'N/A')}
- Client destination: {getattr(transaction, 'client_b', 'N/A')}
- Banque source: {getattr(transaction, 'bank_i', 'N/A')}
- Banque destination: {getattr(transaction, 'bank_b', 'N/A')}
- Heure: {getattr(transaction, 'trx_time', 'N/A')}
- État: {getattr(transaction, 'etat', 'N/A')}

CONTEXTE:
{context}

ANALYSE DEMANDÉE:
1. Évaluez le niveau de priorité (LOW, MEDIUM, HIGH, URGENT)
2. Identifiez les facteurs de risque spécifiques
3. Fournissez une explication détaillée en français
4. Recommandez des actions concrètes

Répondez UNIQUEMENT au format JSON suivant:
{{
    "priority": "LOW|MEDIUM|HIGH|URGENT",
    "risk_factors": ["facteur1", "facteur2"],
    "explanation": "Explication détaillée en français sur les raisons de cette évaluation",
    "recommendations": ["action1", "action2"],
    "confidence": 0.85,
    "summary": "Résumé en une phrase"
}}
"""
        return prompt
    
    def _create_client_prompt(self, client, context: str) -> str:
        """Créer le prompt pour l'analyse client"""
        prompt = f"""
Vous êtes un expert en analyse de profils clients pour la détection de fraude bancaire BAMIS. Analysez ce profil client.

PROFIL CLIENT:
- ID: {client.client_id}
- Transactions totales: {client.total_transactions}
- Montant total: {client.total_amount} MRU
- Fraudes détectées: {client.fraud_count}
- Taux de fraude: {client.fraud_rate:.2f}%
- Dernière activité: {client.last_transaction_date}

CONTEXTE:
{context}

ANALYSE DEMANDÉE:
1. Évaluez le niveau de risque du client (LOW, MEDIUM, HIGH, CRITICAL)
2. Identifiez les patterns comportementaux
3. Fournissez une évaluation détaillée en français
4. Recommandez des mesures de surveillance

Répondez UNIQUEMENT au format JSON suivant:
{{
    "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
    "behavioral_patterns": ["pattern1", "pattern2"],
    "assessment": "Évaluation détaillée du profil client en français",
    "surveillance_recommendations": ["mesure1", "mesure2"],
    "confidence": 0.90,
    "summary": "Résumé du profil en une phrase"
}}
"""
        return prompt
    
    def _call_claude(self, prompt: str) -> str:
        """Appeler l'API Claude"""
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise
    
    def _parse_claude_response(self, response_text: str, analysis_type: str) -> Dict[str, Any]:
        """Parser la réponse de Claude"""
        try:
            # Nettoyer la réponse (enlever les markdown, etc.)
            cleaned_response = response_text.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            
            # Parser le JSON
            analysis = json.loads(cleaned_response)
            
            # Valider les champs requis selon le type
            if analysis_type == "transaction":
                required_fields = ['priority', 'explanation']
                default_values = {
                    'priority': 'MEDIUM',
                    'risk_factors': [],
                    'explanation': cleaned_response,
                    'recommendations': [],
                    'confidence': 0.5,
                    'summary': 'Analyse effectuée'
                }
            else:  # client
                required_fields = ['risk_level', 'assessment']
                default_values = {
                    'risk_level': 'MEDIUM',
                    'behavioral_patterns': [],
                    'assessment': cleaned_response,
                    'surveillance_recommendations': [],
                    'confidence': 0.5,
                    'summary': 'Profil analysé'
                }
            
            # Ajouter les valeurs par défaut si manquantes
            for field, default_value in default_values.items():
                if field not in analysis:
                    analysis[field] = default_value
            
            return analysis
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse Claude response as JSON, using text response")
            
            # Si le parsing JSON échoue, créer une réponse structurée
            if analysis_type == "transaction":
                return {
                    'priority': 'MEDIUM',
                    'risk_factors': ['analyse_textuelle'],
                    'explanation': response_text,
                    'recommendations': ['Révision manuelle recommandée'],
                    'confidence': 0.5,
                    'summary': 'Analyse textuelle effectuée'
                }
            else:
                return {
                    'risk_level': 'MEDIUM',
                    'behavioral_patterns': ['analyse_textuelle'],
                    'assessment': response_text,
                    'surveillance_recommendations': ['Surveillance recommandée'],
                    'confidence': 0.5,
                    'summary': 'Profil analysé en mode textuel'
                }
    
    def _generate_mock_analysis(self, obj, analysis_type: str) -> Dict[str, Any]:
        """Générer une analyse factice pour les tests"""
        if analysis_type == "transaction":
            # Logique simple pour simuler l'analyse
            amount = getattr(obj, 'amount', getattr(obj, 'montant', 0))
            
            if amount > 10000:
                priority = "HIGH"
                risk_factors = ["montant_élevé", "transaction_suspecte"]
                explanation = f"Transaction de {amount} MRU détectée. Montant élevé nécessitant une attention particulière."
                recommendations = ["Vérification manuelle", "Contacter le client"]
            elif amount < 10:
                priority = "MEDIUM"
                risk_factors = ["montant_faible", "pattern_inhabituel"]
                explanation = f"Transaction de {amount} MRU. Montant très faible pouvant indiquer un test de fraude."
                recommendations = ["Surveiller les transactions suivantes"]
            else:
                priority = "LOW"
                risk_factors = []
                explanation = f"Transaction de {amount} MRU dans les paramètres normaux."
                recommendations = []
            
            return {
                'priority': priority,
                'risk_factors': risk_factors,
                'explanation': explanation,
                'recommendations': recommendations,
                'confidence': 0.75,
                'summary': f"Transaction {priority.lower()} risk",
                'analyzed_at': timezone.now().isoformat(),
                'claude_model': 'mock',
                'analysis_type': 'transaction'
            }
        
        else:  # client
            fraud_rate = getattr(obj, 'fraud_rate', 0)
            
            if fraud_rate > 10:
                risk_level = "HIGH"
                patterns = ["taux_fraude_élevé", "comportement_suspect"]
                assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Profil à haut risque."
                recommendations = ["Surveillance renforcée", "Limitation des montants"]
            elif fraud_rate > 5:
                risk_level = "MEDIUM"
                patterns = ["taux_fraude_modéré"]
                assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Surveillance recommandée."
                recommendations = ["Surveillance régulière"]
            else:
                risk_level = "LOW"
                patterns = ["comportement_normal"]
                assessment = f"Client avec un taux de fraude de {fraud_rate:.1f}%. Profil normal."
                recommendations = []
            
            return {
                'risk_level': risk_level,
                'behavioral_patterns': patterns,
                'assessment': assessment,
                'surveillance_recommendations': recommendations,
                'confidence': 0.75,
                'summary': f"Client {risk_level.lower()} risk",
                'analyzed_at': timezone.now().isoformat(),
                'claude_model': 'mock',
                'analysis_type': 'client'
            }
    
    def _generate_error_analysis(self, error_msg: str, analysis_type: str) -> Dict[str, Any]:
        """Générer une analyse d'erreur"""
        base_analysis = {
            'error': error_msg,
            'analyzed_at': timezone.now().isoformat(),
            'claude_model': 'error',
            'analysis_type': analysis_type,
            'confidence': 0.0
        }
        
        if analysis_type == "transaction":
            base_analysis.update({
                'priority': 'MEDIUM',
                'risk_factors': ['erreur_analyse'],
                'explanation': f"Erreur lors de l'analyse: {error_msg}",
                'recommendations': ['Révision manuelle nécessaire'],
                'summary': 'Erreur d\'analyse'
            })
        else:
            base_analysis.update({
                'risk_level': 'MEDIUM',
                'behavioral_patterns': ['erreur_analyse'],
                'assessment': f"Erreur lors de l'analyse: {error_msg}",
                'surveillance_recommendations': ['Révision manuelle nécessaire'],
                'summary': 'Erreur d\'analyse'
            })
        
        return base_analysis

# Instance globale de l'analyseur Claude
claude_analyzer = ClaudeAnalyzer()

# Fonctions utilitaires pour l'intégration
def analyze_transaction_with_claude(transaction, context_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Analyser une transaction avec Claude"""
    return claude_analyzer.analyze_transaction(transaction, context_data)

def analyze_client_with_claude(client, transactions_data: Optional[List] = None) -> Dict[str, Any]:
    """Analyser un client avec Claude"""
    return claude_analyzer.analyze_client(client, transactions_data)

def is_claude_available() -> bool:
    """Vérifier si Claude est disponible"""
    return claude_analyzer.is_available

def get_claude_status() -> Dict[str, Any]:
    """Obtenir le statut de Claude"""
    return {
        'available': claude_analyzer.is_available,
        'api_key_configured': CLAUDE_API_KEY is not None,
        'model': CLAUDE_MODEL,
        'max_tokens': CLAUDE_MAX_TOKENS
    }



