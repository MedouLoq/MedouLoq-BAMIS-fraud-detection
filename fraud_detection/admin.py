from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, RawTransaction, Client, Bank, 
    DailyInsight, UploadSession
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'department', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('username', 'email', 'department')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Informations Supplémentaires', {
            'fields': ('department',)
        }),
        ('Informations de Connexion', {
            'fields': ('last_login_ip',)
        }),
    )


@admin.register(RawTransaction)
class RawTransactionAdmin(admin.ModelAdmin):
    list_display = ('trx', 'montant', 'trx_type', 'client_i', 'client_b', 'ml_is_fraud', 'claude_priority_level', 'uploaded_at')
    list_filter = ('ml_is_fraud', 'trx_type', 'etat', 'claude_priority_level', 'uploaded_at')
    search_fields = ('trx', 'client_i', 'client_b')
    readonly_fields = ('uploaded_at', 'ml_processed_at', 'claude_analyzed_at')
    
    fieldsets = (
        ('Données Transaction', {
            'fields': ('trx', 'trx_time', 'mls', 'trx_type', 'montant', 'client_i', 'client_b', 'bank_i', 'bank_b', 'etat')
        }),
        ('Analyse ML', {
            'fields': ('ml_is_fraud', 'ml_feature_importance', 'ml_processed_at')
        }),
        ('Analyse Claude', {
            'fields': ('claude_explanation', 'claude_priority_level', 'claude_analyzed_at')
        }),
        ('Métadonnées', {
            'fields': ('uploaded_by', 'uploaded_at')
        }),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('client_id', 'total_transactions', 'fraud_transactions_count', 'claude_risk_level', 'updated_at')
    list_filter = ('claude_risk_level', 'risk_level', 'most_common_transaction_type')
    search_fields = ('client_id',)
    readonly_fields = ('created_at', 'updated_at', 'claude_last_analyzed')
    
    actions = ['update_statistics']
    
    def update_statistics(self, request, queryset):
        for client in queryset:
            client.update_statistics()
        self.message_user(request, f"Statistiques mises à jour pour {queryset.count()} clients.")
    update_statistics.short_description = "Mettre à jour les statistiques"


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('bank_code', 'bank_name', 'total_transactions', 'fraud_transactions', 'fraud_rate')
    search_fields = ('bank_code', 'bank_name')
    readonly_fields = ('created_at', 'updated_at')
    
    actions = ['update_statistics']
    
    def fraud_rate(self, obj):
        return f"{obj.fraud_rate:.1f}%"
    fraud_rate.short_description = "Taux de Fraude"
    
    def update_statistics(self, request, queryset):
        for bank in queryset:
            bank.update_statistics()
        self.message_user(request, f"Statistiques mises à jour pour {queryset.count()} banques.")
    update_statistics.short_description = "Mettre à jour les statistiques"


@admin.register(DailyInsight)
class DailyInsightAdmin(admin.ModelAdmin):
    list_display = ('date', 'fraud_count', 'high_priority_count', 'total_amount_fraud', 'created_at')
    list_filter = ('date', 'fraud_count')
    readonly_fields = ('created_at',)


@admin.register(UploadSession)
class UploadSessionAdmin(admin.ModelAdmin):
    list_display = ('filename', 'uploaded_by', 'status', 'processed_rows', 'fraud_detected', 'started_at')
    list_filter = ('status', 'started_at')
    search_fields = ('filename', 'uploaded_by__username')
    readonly_fields = ('started_at', 'completed_at')

