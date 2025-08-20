from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models import Q, Avg, Sum, Count
from decimal import Decimal
import json
from datetime import datetime, timedelta


class CustomUser(AbstractUser):
    """Modèle utilisateur personnalisé simplifié"""
    department = models.CharField(max_length=50, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.username


class RawTransaction(models.Model):
    """Modèle pour les transactions brutes importées du CSV"""
    
    TRANSACTION_TYPES = [
        ('TRF', 'Transfert interbancaire'),
        ('RT', 'Retrait'),
        ('RCD', 'Recharge'),
        ('PF', 'Paiement de facture')
    ]
    
    STATUS_CHOICES = [
        ('OK', 'Transaction réussie'),
        ('KO', 'Échec de traitement'),
        ('ATT', 'En attente ou en traitement')
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Faible'),
        ('MEDIUM', 'Moyen'),
        ('HIGH', 'Élevé'),
        ('URGENT', 'Urgent')
    ]
    
    # Colonnes exactes du CSV
    trx = models.CharField(max_length=100, unique=True, verbose_name="ID Transaction")
    trx_time = models.CharField(max_length=50, verbose_name="Heure Transaction")
    mls = models.BigIntegerField(verbose_name="Milliseconds")
    trx_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES, verbose_name="Type")
    montant = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Montant")
    client_i = models.CharField(max_length=50, verbose_name="Client Source")
    client_b = models.CharField(max_length=50, verbose_name="Client Destination")
    bank_i = models.CharField(max_length=10, verbose_name="Banque Source")
    bank_b = models.CharField(max_length=10, verbose_name="Banque Destination")
    etat = models.CharField(max_length=3, choices=STATUS_CHOICES, verbose_name="État")
    
    # Résultats ML (simplifiés)
    ml_is_fraud = models.BooleanField(default=False, verbose_name="Fraude Détectée")
    ml_risk_score = models.FloatField(null=True, blank=True, verbose_name="Score de Risque")
    ml_confidence = models.FloatField(null=True, blank=True, verbose_name="Confiance ML")
    ml_feature_importance = models.JSONField(null=True, blank=True, verbose_name="Importance Features")
    ml_processed_at = models.DateTimeField(null=True, blank=True)
    
    # Analyse Claude (automatique pour fraudes)
    claude_explanation = models.TextField(blank=True, verbose_name="Explication IA")
    claude_analyzed_at = models.DateTimeField(null=True, blank=True)
    claude_priority_level = models.CharField(
        max_length=10, 
        choices=PRIORITY_CHOICES,
        blank=True,
        verbose_name="Niveau Priorité"
    )
    claude_risk_factors = models.JSONField(null=True, blank=True, verbose_name="Facteurs de Risque")
    
    # Métadonnées
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    
    # Nouveaux champs pour analytics temporelles
    transaction_hour = models.IntegerField(null=True, blank=True, verbose_name="Heure")
    transaction_day_of_week = models.IntegerField(null=True, blank=True, verbose_name="Jour de la semaine")
    transaction_date = models.DateField(null=True, blank=True, verbose_name="Date")
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        indexes = [
            models.Index(fields=['client_i']),
            models.Index(fields=['client_b']),
            models.Index(fields=['bank_i']),
            models.Index(fields=['bank_b']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['ml_is_fraud']),
        ]
    
    def __str__(self):
        return f"{self.trx} - {self.montant} MRU"
    
    @property
    def is_self_transfer(self):
        """Vérifie si c'est un auto-transfert"""
        return self.client_i == self.client_b
    
    @property
    def parsed_datetime(self):
        """Parse la chaîne TRX_TIME en datetime"""
        try:
            from datetime import datetime
            return datetime.strptime(self.trx_time, '%Y-%m-%d %H:%M:%S')
        except:
            return None
    
    @property
    def risk_level_class(self):
        """Retourne la classe CSS pour le niveau de risque"""
        if self.ml_is_fraud:
            if self.claude_priority_level == 'URGENT':
                return 'danger'
            elif self.claude_priority_level == 'HIGH':
                return 'warning'
            else:
                return 'info'
        return 'success'
    
    @property
    def formatted_amount(self):
        """Montant formaté avec séparateurs"""
        return f"{self.montant:,.2f}  MRU"
    
    def save(self, *args, **kwargs):
        """Override save to extract time analytics"""
        if self.trx_time and not self.transaction_hour:
            try:
                dt = self.parsed_datetime
                if dt:
                    self.transaction_hour = dt.hour
                    self.transaction_day_of_week = dt.weekday()
                    self.transaction_date = dt.date()
            except:
                pass
        super().save(*args, **kwargs)


class Client(models.Model):
    """Profil client auto-généré à partir des transactions"""
    
    RISK_LEVELS = [
        ('NORMAL', 'Normal'),
        ('WATCH', 'Surveillance'),
        ('SUSPECT', 'Suspect')
    ]
    
    client_id = models.CharField(max_length=50, unique=True, verbose_name="ID Client")
    
    # Statistiques de transactions
    total_transactions_sent = models.IntegerField(default=0)
    total_transactions_received = models.IntegerField(default=0)
    total_amount_sent = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount_received = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Patterns comportementaux
    avg_transaction_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    max_transaction_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    min_transaction_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    most_common_transaction_type = models.CharField(max_length=3, blank=True)
    unique_banks_used = models.IntegerField(default=0)
    self_transfers_count = models.IntegerField(default=0)
    failed_transactions_count = models.IntegerField(default=0)
    fraud_transactions_count = models.IntegerField(default=0)
    
    # Patterns temporels
    most_active_hour = models.IntegerField(null=True, blank=True)
    most_active_day = models.IntegerField(null=True, blank=True)
    weekend_transactions = models.IntegerField(default=0)
    night_transactions = models.IntegerField(default=0)  # 22h-6h
    
    # Évaluation des risques
    risk_score = models.FloatField(default=0.0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='NORMAL')
    
    # Analyse Claude du client
    claude_risk_assessment = models.TextField(blank=True, verbose_name="Évaluation IA")
    claude_risk_level = models.CharField(
        max_length=15,
        choices=RISK_LEVELS,
        default='NORMAL',
        verbose_name="Niveau Risque IA"
    )
    claude_behavioral_patterns = models.JSONField(null=True, blank=True, verbose_name="Patterns Comportementaux")
    claude_last_analyzed = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    first_transaction_date = models.DateTimeField(null=True, blank=True)
    last_transaction_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    fraud_rate = models.FloatField(default=0.0, verbose_name="Taux de Fraude (%)")
    class Meta:
        ordering = ['-fraud_transactions_count', '-total_transactions_sent']
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        indexes = [
            models.Index(fields=['risk_level']),
            models.Index(fields=['fraud_transactions_count']),
        ]
    
    def __str__(self):
        return f"Client {self.client_id}"
    
    @property
    def total_transactions(self):
        """Total des transactions (envoyées + reçues)"""
        return self.total_transactions_sent + self.total_transactions_received
    
    @property
    def total_amount(self):
        """Montant total traité"""
        return self.total_amount_sent + self.total_amount_received
    
    @property
    def failure_rate(self):
        """Taux d'échec des transactions"""
        if self.total_transactions_sent == 0:
            return 0
        return (self.failed_transactions_count / self.total_transactions_sent) * 100
    
    
    
    @property
    def risk_level_class(self):
        """Classe CSS pour le niveau de risque"""
        if self.claude_risk_level == 'SUSPECT':
            return 'danger'
        elif self.claude_risk_level == 'WATCH':
            return 'warning'
        return 'success'
    
    def get_transaction_time_series(self, days=30):
        """Retourne les données de série temporelle pour les graphiques"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Sum, Q
        from django.db.models.functions import TruncDate
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get transactions for this client within the date range
        transactions = RawTransaction.objects.filter(
            Q(client_i=self.client_id) | Q(client_b=self.client_id),
            uploaded_at__date__gte=start_date,
            uploaded_at__date__lte=end_date
        )
        
        # Group by date using uploaded_at (which is always populated)
        # and use TruncDate to extract just the date part
        daily_data = transactions.annotate(
            date=TruncDate('uploaded_at')
        ).values('date').annotate(
            count=Count('id'),
            total_amount=Sum('montant'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True))
        ).order_by('date')
        
        # Convert to list and rename 'date' to 'transaction_date' for consistency
        result = []
        for item in daily_data:
            result.append({
                'transaction_date': item['date'],
                'count': item['count'],
                'total_amount': item['total_amount'],
                'fraud_count': item['fraud_count']
            })
        
        return result
    
    def get_hourly_pattern(self):
        """Retourne le pattern d'activité par heure"""
        from django.db.models import Count, Q
        from django.db.models.functions import Extract
        
        transactions = RawTransaction.objects.filter(
            Q(client_i=self.client_id) | Q(client_b=self.client_id)
        )
        
        # Try to use transaction_hour if available, otherwise extract from uploaded_at
        if transactions.filter(transaction_hour__isnull=False).exists():
            # Use the transaction_hour field if it's populated
            hourly_data = transactions.values('transaction_hour').annotate(
                count=Count('id')
            ).order_by('transaction_hour')
        else:
            # Extract hour from uploaded_at as fallback
            hourly_data = transactions.annotate(
                hour=Extract('uploaded_at', 'hour')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')
            
            # Rename 'hour' to 'transaction_hour' for consistency
            hourly_data = [
                {'transaction_hour': item['hour'], 'count': item['count']} 
                for item in hourly_data
            ]
        
        return list(hourly_data)
    def update_statistics(self):
        """Met à jour les statistiques du client"""
        # Transactions envoyées
        sent_transactions = RawTransaction.objects.filter(client_i=self.client_id)
        self.total_transactions_sent = sent_transactions.count()
        self.total_amount_sent = sent_transactions.aggregate(
            total=Sum('montant'))['total'] or Decimal('0')
        
        # Transactions reçues
        received_transactions = RawTransaction.objects.filter(client_b=self.client_id)
        self.total_transactions_received = received_transactions.count()
        self.total_amount_received = received_transactions.aggregate(
            total=Sum('montant'))['total'] or Decimal('0')
        
        # Toutes les transactions
        all_transactions = RawTransaction.objects.filter(
            Q(client_i=self.client_id) | Q(client_b=self.client_id)
        )
        
        # Statistiques comportementales
        if all_transactions.exists():
            amounts = all_transactions.aggregate(
                avg=Avg('montant'),
                max=models.Max('montant'),
                min=models.Min('montant')
            )
            self.avg_transaction_amount = amounts['avg'] or Decimal('0')
            self.max_transaction_amount = amounts['max'] or Decimal('0')
            self.min_transaction_amount = amounts['min'] or Decimal('0')
            
            # Type de transaction le plus fréquent
            type_stats = all_transactions.values('trx_type').annotate(
                count=Count('trx_type')).order_by('-count').first()
            if type_stats:
                self.most_common_transaction_type = type_stats['trx_type']
            
            # Banques uniques utilisées
            banks_used = set()
            for tx in all_transactions:
                banks_used.add(tx.bank_i)
                banks_used.add(tx.bank_b)
            self.unique_banks_used = len(banks_used)
            
            # Auto-transferts
            self.self_transfers_count = all_transactions.filter(
                client_i=models.F('client_b')).count()
            
            # Transactions échouées
            self.failed_transactions_count = sent_transactions.filter(etat='KO').count()
            
            # Transactions frauduleuses
            self.fraud_transactions_count = all_transactions.filter(ml_is_fraud=True).count()
            
            # Patterns temporels
            hour_stats = all_transactions.values('transaction_hour').annotate(
                count=Count('transaction_hour')).order_by('-count').first()
            if hour_stats:
                self.most_active_hour = hour_stats['transaction_hour']
            
            day_stats = all_transactions.values('transaction_day_of_week').annotate(
                count=Count('transaction_day_of_week')).order_by('-count').first()
            if day_stats:
                self.most_active_day = day_stats['transaction_day_of_week']
            
            # Transactions weekend (samedi=5, dimanche=6)
            self.weekend_transactions = all_transactions.filter(
                transaction_day_of_week__in=[5, 6]).count()
            
            # Transactions nocturnes (22h-6h)
            self.night_transactions = all_transactions.filter(
                Q(transaction_hour__gte=22) | Q(transaction_hour__lt=6)).count()
            
            # Dates
            self.first_transaction_date = all_transactions.order_by('uploaded_at').first().uploaded_at
            self.last_transaction_date = all_transactions.order_by('-uploaded_at').first().uploaded_at
        
        self.save()


class Bank(models.Model):
    """Statistiques par banque"""
    
    bank_code = models.CharField(max_length=10, unique=True, verbose_name="Code Banque")
    bank_name = models.CharField(max_length=100, blank=True, verbose_name="Nom Banque")
    
    # Statistiques
    total_transactions = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    unique_clients = models.IntegerField(default=0)
    fraud_transactions = models.IntegerField(default=0)
    high_risk_transactions = models.IntegerField(default=0)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-total_transactions']
        verbose_name = "Banque"
        verbose_name_plural = "Banques"
    
    def __str__(self):
        return f"Banque {self.bank_code}"
    
    @property
    def fraud_rate(self):
        """Taux de fraude de la banque"""
        if self.total_transactions == 0:
            return 0
        return (self.fraud_transactions / self.total_transactions) * 100
    
    def get_transaction_time_series(self, days=30):
        """Retourne les données de série temporelle pour la banque"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        transactions = RawTransaction.objects.filter(
            Q(bank_i=self.bank_code) | Q(bank_b=self.bank_code),
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )
        
        daily_data = transactions.values('transaction_date').annotate(
            count=Count('id'),
            total_amount=Sum('montant'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True))
        ).order_by('transaction_date')
        
        return list(daily_data)
    
    def update_statistics(self):
        """Met à jour les statistiques de la banque"""
        # Transactions où cette banque est impliquée
        transactions = RawTransaction.objects.filter(
            Q(bank_i=self.bank_code) | Q(bank_b=self.bank_code)
        )
        
        self.total_transactions = transactions.count()
        self.total_amount = transactions.aggregate(
            total=Sum('montant'))['total'] or Decimal('0')
        
        # Clients uniques
        clients = set()
        for tx in transactions:
            clients.add(tx.client_i)
            clients.add(tx.client_b)
        self.unique_clients = len(clients)
        
        # Fraudes
        self.fraud_transactions = transactions.filter(ml_is_fraud=True).count()
        self.high_risk_transactions = transactions.filter(
            ml_is_fraud=True,
            claude_priority_level__in=['HIGH', 'URGENT']
        ).count()
        
        self.save()


class DailyInsight(models.Model):
    """Insights quotidiens générés par Claude"""
    
    date = models.DateField(unique=True)
    claude_summary = models.TextField(verbose_name="Résumé IA")
    fraud_count = models.IntegerField(default=0)
    high_priority_count = models.IntegerField(default=0)
    total_amount_fraud = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    top_risk_clients = models.JSONField(default=list, blank=True)
    key_patterns = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "Insight Quotidien"
        verbose_name_plural = "Insights Quotidiens"
    
    def __str__(self):
        return f"Insights {self.date}"


class UploadSession(models.Model):
    """Session d'upload pour tracking"""
    
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Statistiques de traitement
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    fraud_detected = models.IntegerField(default=0)
    claude_analyses_generated = models.IntegerField(default=0)
    
    # Statut
    status = models.CharField(max_length=20, default='PROCESSING')
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Upload {self.filename} - {self.status}"


class TransactionNote(models.Model):
    """Notes d'investigation sur les transactions"""
    
    transaction = models.ForeignKey(RawTransaction, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    note = models.TextField(verbose_name="Note")
    is_flagged = models.BooleanField(default=False, verbose_name="Signalé")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note sur {self.transaction.trx}"

