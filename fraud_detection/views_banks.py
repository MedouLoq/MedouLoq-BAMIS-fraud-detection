from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import Bank, RawTransaction, Client
from .utils import update_bank_statistics


@login_required
def bank_list_view(request):
    """Liste des banques avec statistiques"""
    
    banks = Bank.objects.order_by('-total_transactions')
    
    # Filtres
    search = request.GET.get('search')
    if search:
        banks = banks.filter(
            Q(bank_code__icontains=search) | Q(bank_name__icontains=search)
        )
    
    min_transactions = request.GET.get('min_transactions')
    if min_transactions:
        try:
            min_trans = int(min_transactions)
            banks = banks.filter(total_transactions__gte=min_trans)
        except ValueError:
            pass
    
    fraud_rate_filter = request.GET.get('fraud_rate')
    if fraud_rate_filter:
        if fraud_rate_filter == 'high':
            # Banques avec taux de fraude > 5%
            banks = [bank for bank in banks if bank.fraud_rate > 5]
        elif fraud_rate_filter == 'medium':
            # Banques avec taux de fraude entre 2% et 5%
            banks = [bank for bank in banks if 2 <= bank.fraud_rate <= 5]
        elif fraud_rate_filter == 'low':
            # Banques avec taux de fraude < 2%
            banks = [bank for bank in banks if bank.fraud_rate < 2]
    
    # Statistiques globales
    total_banks = Bank.objects.count()
    total_bank_transactions = Bank.objects.aggregate(Sum('total_transactions'))['total_transactions__sum'] or 0
    total_bank_amount = Bank.objects.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    avg_fraud_rate = sum(bank.fraud_rate for bank in Bank.objects.all()) / total_banks if total_banks > 0 else 0
    
    # Pagination
    paginator = Paginator(banks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'banks': page_obj,  # Pour compatibilité template
        'total_banks': total_banks,
        'total_bank_transactions': total_bank_transactions,
        'total_bank_amount': total_bank_amount,
        'avg_fraud_rate': avg_fraud_rate,
        'current_filters': {
            'search': search,
            'min_transactions': min_transactions,
            'fraud_rate': fraud_rate_filter,
        }
    }
    
    return render(request, 'banks/list.html', context)


@login_required
def bank_detail_view(request, bank_code):
    """Détail d'une banque avec analytics"""
    
    bank = get_object_or_404(Bank, bank_code=bank_code)
    
    # Transactions de cette banque (source ou destination)
    transactions = RawTransaction.objects.filter(
        Q(bank_i=bank_code) | Q(bank_b=bank_code)
    ).order_by('-uploaded_at')
    
    # Transactions frauduleuses
    fraud_transactions = transactions.filter(ml_is_fraud=True)
    
    # Clients uniques utilisant cette banque
    unique_clients_i = set(transactions.values_list('client_i', flat=True))
    unique_clients_b = set(transactions.values_list('client_b', flat=True))
    all_unique_clients = unique_clients_i.union(unique_clients_b)
    
    # Top clients par volume
    top_clients_data = []
    for client_id in list(all_unique_clients)[:10]:  # Top 10
        client_transactions = transactions.filter(
            Q(client_i=client_id) | Q(client_b=client_id)
        )
        client_amount = client_transactions.aggregate(Sum('montant'))['montant__sum'] or 0
        client_fraud_count = client_transactions.filter(ml_is_fraud=True).count()
        
        try:
            client_obj = Client.objects.get(client_id=client_id)
        except Client.DoesNotExist:
            client_obj = None
        
        top_clients_data.append({
            'client_id': client_id,
            'client_obj': client_obj,
            'transaction_count': client_transactions.count(),
            'total_amount': client_amount,
            'fraud_count': client_fraud_count
        })
    
    # Trier par montant total
    top_clients_data.sort(key=lambda x: x['total_amount'], reverse=True)
    top_clients_data = top_clients_data[:10]
    
    # Statistiques par type de transaction
    transaction_types = transactions.values('trx_type').annotate(
        count=Count('id'),
        fraud_count=Count('id', filter=Q(ml_is_fraud=True)),
        total_amount=Sum('montant')
    ).order_by('-count')
    
    # Données pour les graphiques (30 derniers jours)
    time_series_data = bank.get_transaction_time_series(days=30)
    
    # Préparer les données pour Chart.js
    time_series_labels = []
    time_series_counts = []
    time_series_frauds = []
    time_series_amounts = []
    
    for data in time_series_data:
        time_series_labels.append(data['transaction_date'].strftime('%Y-%m-%d'))
        time_series_counts.append(data['count'])
        time_series_frauds.append(data['fraud_count'])
        time_series_amounts.append(float(data['total_amount']) if data['total_amount'] else 0)
    
    # Pattern horaire des transactions
    hourly_pattern = transactions.values('transaction_hour').annotate(
        count=Count('id')
    ).order_by('transaction_hour')
    
    hourly_pattern_data = [0] * 24
    for data in hourly_pattern:
        if data['transaction_hour'] is not None:
            hourly_pattern_data[data['transaction_hour']] = data['count']
    
    # Transactions inter-banques vs intra-banque
    intra_bank_transactions = transactions.filter(bank_i=bank_code, bank_b=bank_code).count()
    inter_bank_transactions = transactions.count() - intra_bank_transactions
    
    context = {
        'bank': bank,
        'transactions': transactions[:20],  # Dernières 20
        'fraud_transactions': fraud_transactions[:10],
        'total_transactions': transactions.count(),
        'fraud_count': fraud_transactions.count(),
        'unique_clients_count': len(all_unique_clients),
        'top_clients': top_clients_data,
        'transaction_types': transaction_types,
        'intra_bank_transactions': intra_bank_transactions,
        'inter_bank_transactions': inter_bank_transactions,
        'time_series_labels': json.dumps(time_series_labels),
        'time_series_counts': json.dumps(time_series_counts),
        'time_series_frauds': json.dumps(time_series_frauds),
        'time_series_amounts': json.dumps(time_series_amounts),
        'hourly_pattern': json.dumps(hourly_pattern_data),
    }
    
    return render(request, 'banks/detail.html', context)


@login_required
def bank_refresh_statistics(request, bank_code):
    """Actualiser les statistiques d'une banque"""
    
    if request.method == 'POST':
        try:
            bank = get_object_or_404(Bank, bank_code=bank_code)
            bank.update_statistics()
            
            return JsonResponse({
                'success': True,
                'message': f'Statistiques de la banque {bank_code} mises à jour',
                'bank_data': {
                    'total_transactions': bank.total_transactions,
                    'total_amount': float(bank.total_amount),
                    'unique_clients': bank.unique_clients,
                    'fraud_transactions': bank.fraud_transactions,
                    'fraud_rate': bank.fraud_rate
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def banks_comparison_view(request):
    """Vue de comparaison entre banques"""
    
    banks = Bank.objects.order_by('-total_transactions')[:10]  # Top 10 banques
    
    # Données pour le graphique de comparaison
    comparison_data = {
        'labels': [bank.bank_code for bank in banks],
        'transactions': [bank.total_transactions for bank in banks],
        'amounts': [float(bank.total_amount) for bank in banks],
        'fraud_rates': [bank.fraud_rate for bank in banks],
        'unique_clients': [bank.unique_clients for bank in banks]
    }
    
    # Statistiques de performance
    best_performing_bank = min(banks, key=lambda b: b.fraud_rate) if banks else None
    worst_performing_bank = max(banks, key=lambda b: b.fraud_rate) if banks else None
    highest_volume_bank = max(banks, key=lambda b: b.total_transactions) if banks else None
    
    context = {
        'banks': banks,
        'comparison_data': json.dumps(comparison_data),
        'best_performing_bank': best_performing_bank,
        'worst_performing_bank': worst_performing_bank,
        'highest_volume_bank': highest_volume_bank,
    }
    
    return render(request, 'banks/comparison.html', context)


@login_required
def bank_analytics_api(request):
    """API pour les données d'analytics des banques"""
    
    if request.method == 'GET':
        # Paramètres de requête
        days = int(request.GET.get('days', 30))
        bank_code = request.GET.get('bank_code')
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Filtrer par banque si spécifié
        transactions_query = RawTransaction.objects.filter(
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )
        
        if bank_code:
            transactions_query = transactions_query.filter(
                Q(bank_i=bank_code) | Q(bank_b=bank_code)
            )
        
        # Données temporelles
        daily_data = transactions_query.values('transaction_date').annotate(
            count=Count('id'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True)),
            total_amount=Sum('montant')
        ).order_by('transaction_date')
        
        # Données par banque
        bank_data = Bank.objects.values('bank_code', 'bank_name').annotate(
            transaction_count=Count('rawtransaction', filter=Q(
                rawtransaction__transaction_date__gte=start_date,
                rawtransaction__transaction_date__lte=end_date
            )),
            fraud_count=Count('rawtransaction', filter=Q(
                rawtransaction__ml_is_fraud=True,
                rawtransaction__transaction_date__gte=start_date,
                rawtransaction__transaction_date__lte=end_date
            ))
        ).order_by('-transaction_count')
        
        return JsonResponse({
            'daily_data': list(daily_data),
            'bank_data': list(bank_data),
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            }
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


