"""
Vues pour les analytics avec intégration Bokeh
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd

from .models import RawTransaction, Client, Bank
from .bokeh_charts import BokehChartGenerator, generate_analytics_charts
from .utils import user_can_access_analytics


@login_required
def analytics_view(request):
    """Vue principale des analytics avec graphiques Bokeh"""
    
    # Vérifier les permissions
    if not user_can_access_analytics(request.user):
        messages.error(request, "Vous n'avez pas l'autorisation d'accéder aux analytics.")
        return redirect('dashboard')
    
    # Récupérer les paramètres de filtre
    date_range = request.GET.get('date_range', '30')  # 30 jours par défaut
    transaction_type = request.GET.get('transaction_type', 'all')
    fraud_filter = request.GET.get('fraud_filter', 'all')
    
    # Calculer la date de début
    end_date = timezone.now()
    if date_range == '7':
        start_date = end_date - timedelta(days=7)
    elif date_range == '30':
        start_date = end_date - timedelta(days=30)
    elif date_range == '90':
        start_date = end_date - timedelta(days=90)
    elif date_range == '365':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=30)
    
    # Construire la requête de base
    transactions_query = RawTransaction.objects.filter(
        uploaded_at__gte=start_date,
        uploaded_at__lte=end_date
    )
    
    # Appliquer les filtres
    if transaction_type != 'all':
        transactions_query = transactions_query.filter(trx_type=transaction_type)
    
    if fraud_filter == 'fraud_only':
        transactions_query = transactions_query.filter(ml_is_fraud=True)
    elif fraud_filter == 'normal_only':
        transactions_query = transactions_query.filter(ml_is_fraud=False)
    
    # Récupérer les données
    transactions = transactions_query.order_by('-uploaded_at')
    
    # Calculer les statistiques générales
    total_transactions = transactions.count()
    fraud_transactions = transactions.filter(ml_is_fraud=True).count()
    total_amount = transactions.aggregate(Sum('amount'))['amount__sum'] or 0
    fraud_amount = transactions.filter(ml_is_fraud=True).aggregate(Sum('amount'))['amount__sum'] or 0
    
    fraud_rate = (fraud_transactions / total_transactions * 100) if total_transactions > 0 else 0
    avg_transaction_amount = transactions.aggregate(Avg('amount'))['amount__avg'] or 0
    
    # Statistiques par type de transaction
    transaction_types = transactions.values('trx_type').annotate(
        count=Count('id'),
        fraud_count=Count('id', filter=Q(ml_is_fraud=True)),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount')
    ).order_by('-count')
    
    # Calculer les taux de fraude par type
    for t_type in transaction_types:
        t_type['fraud_rate'] = (t_type['fraud_count'] / t_type['count'] * 100) if t_type['count'] > 0 else 0
    
    # Statistiques des clients à haut risque
    high_risk_clients = Client.objects.filter(
        fraud_rate__gte=10.0
    ).order_by('-fraud_rate')[:10]
    
    # Tendances temporelles
    daily_stats = transactions.extra(
        select={'day': 'date(uploaded_at)'}
    ).values('day').annotate(
        count=Count('id'),
        fraud_count=Count('id', filter=Q(ml_is_fraud=True)),
        total_amount=Sum('amount')
    ).order_by('day')
    
    # Générer les graphiques Bokeh
    try:
        # Préparer les données pour les clients
        clients_data = Client.objects.filter(
            total_transactions__gt=0
        ).values(
            'client_id', 'total_transactions', 'total_amount', 
            'fraud_count', 'fraud_rate'
        )
        
        # Générer les composants Bokeh
        script, div = generate_analytics_charts(transactions, clients_data)
        
    except Exception as e:
        # En cas d'erreur, utiliser des graphiques vides
        print(f"Erreur lors de la génération des graphiques Bokeh: {e}")
        script, div = "", "<div class='alert alert-warning'>Erreur lors du chargement des graphiques</div>"
    
    # Insights et recommandations
    insights = []
    
    if fraud_rate > 5:
        insights.append({
            'type': 'warning',
            'title': 'Taux de fraude élevé',
            'message': f'Le taux de fraude actuel ({fraud_rate:.1f}%) dépasse le seuil recommandé de 5%.',
            'recommendation': 'Renforcez les contrôles de sécurité et examinez les transactions suspectes.'
        })
    
    if total_transactions > 0:
        # Analyser les pics d'activité
        max_daily = max([day['count'] for day in daily_stats]) if daily_stats else 0
        avg_daily = sum([day['count'] for day in daily_stats]) / len(daily_stats) if daily_stats else 0
        
        if max_daily > avg_daily * 2:
            insights.append({
                'type': 'info',
                'title': 'Pic d\'activité détecté',
                'message': f'Un pic d\'activité inhabituel a été observé ({max_daily} transactions vs {avg_daily:.0f} en moyenne).',
                'recommendation': 'Vérifiez si ce pic correspond à des événements planifiés ou à une activité suspecte.'
            })
    
    # Types de transactions les plus risqués
    risky_types = [t for t in transaction_types if t['fraud_rate'] > 10]
    if risky_types:
        insights.append({
            'type': 'danger',
            'title': 'Types de transactions à risque',
            'message': f"Les types {', '.join([t['trx_type'] for t in risky_types])} présentent un taux de fraude élevé.",
            'recommendation': 'Renforcez la surveillance de ces types de transactions.'
        })
    
    # Comparaison avec la période précédente
    previous_start = start_date - (end_date - start_date)
    previous_transactions = RawTransaction.objects.filter(
        uploaded_at__gte=previous_start,
        uploaded_at__lt=start_date
    )
    
    previous_total = previous_transactions.count()
    previous_fraud = previous_transactions.filter(ml_is_fraud=True).count()
    previous_fraud_rate = (previous_fraud / previous_total * 100) if previous_total > 0 else 0
    
    # Calculer les tendances
    transaction_trend = 'stable'
    fraud_trend = 'stable'
    
    if total_transactions > previous_total * 1.1:
        transaction_trend = 'up'
    elif total_transactions < previous_total * 0.9:
        transaction_trend = 'down'
    
    if fraud_rate > previous_fraud_rate * 1.1:
        fraud_trend = 'up'
    elif fraud_rate < previous_fraud_rate * 0.9:
        fraud_trend = 'down'
    
    context = {
        # Données générales
        'total_transactions': total_transactions,
        'fraud_transactions': fraud_transactions,
        'fraud_rate': fraud_rate,
        'total_amount': total_amount,
        'fraud_amount': fraud_amount,
        'avg_transaction_amount': avg_transaction_amount,
        
        # Statistiques détaillées
        'transaction_types': transaction_types,
        'high_risk_clients': high_risk_clients,
        'daily_stats': daily_stats,
        
        # Tendances
        'transaction_trend': transaction_trend,
        'fraud_trend': fraud_trend,
        'previous_fraud_rate': previous_fraud_rate,
        
        # Graphiques Bokeh
        'bokeh_script': script,
        'bokeh_div': div,
        
        # Insights
        'insights': insights,
        
        # Filtres actuels
        'current_filters': {
            'date_range': date_range,
            'transaction_type': transaction_type,
            'fraud_filter': fraud_filter
        },
        
        # Options pour les filtres
        'date_range_options': [
            ('7', '7 derniers jours'),
            ('30', '30 derniers jours'),
            ('90', '3 derniers mois'),
            ('365', '12 derniers mois')
        ],
        'transaction_type_options': [
            ('all', 'Tous les types'),
            ('TRF', 'Transferts'),
            ('RT', 'Retraits'),
            ('RCD', 'Recharges'),
            ('PF', 'Paiements')
        ],
        'fraud_filter_options': [
            ('all', 'Toutes les transactions'),
            ('fraud_only', 'Fraudes uniquement'),
            ('normal_only', 'Transactions normales')
        ]
    }
    
    return render(request, 'analytics/analytics_bokeh.html', context)


@login_required
def export_analytics_data(request):
    """Exporter les données d'analytics en CSV"""
    
    if not user_can_access_analytics(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Récupérer les mêmes filtres que la vue principale
    date_range = request.GET.get('date_range', '30')
    transaction_type = request.GET.get('transaction_type', 'all')
    fraud_filter = request.GET.get('fraud_filter', 'all')
    
    # Appliquer les filtres (même logique que analytics_view)
    end_date = timezone.now()
    if date_range == '7':
        start_date = end_date - timedelta(days=7)
    elif date_range == '30':
        start_date = end_date - timedelta(days=30)
    elif date_range == '90':
        start_date = end_date - timedelta(days=90)
    elif date_range == '365':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=30)
    
    transactions_query = RawTransaction.objects.filter(
        uploaded_at__gte=start_date,
        uploaded_at__lte=end_date
    )
    
    if transaction_type != 'all':
        transactions_query = transactions_query.filter(trx_type=transaction_type)
    
    if fraud_filter == 'fraud_only':
        transactions_query = transactions_query.filter(ml_is_fraud=True)
    elif fraud_filter == 'normal_only':
        transactions_query = transactions_query.filter(ml_is_fraud=False)
    
    # Créer le CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Transaction ID', 'Type', 'Montant', 'Client Initiateur', 'Client Bénéficiaire',
        'Date', 'Fraude Détectée', 'Confiance ML', 'Analyse Claude'
    ])
    
    for transaction in transactions_query.select_related():
        writer.writerow([
            transaction.trx,
            transaction.get_trx_type_display(),
            transaction.amount,
            transaction.client_i,
            transaction.client_b,
            transaction.uploaded_at.strftime('%Y-%m-%d %H:%M:%S'),
            'Oui' if transaction.ml_is_fraud else 'Non',
            f"{transaction.ml_confidence:.2f}" if transaction.ml_confidence else 'N/A',
            transaction.claude_explanation[:100] + '...' if transaction.claude_explanation else 'N/A'
        ])
    
    return response


@login_required
def get_chart_data_api(request):
    """API pour récupérer les données des graphiques en temps réel"""
    
    if not user_can_access_analytics(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    chart_type = request.GET.get('type', 'volume')
    date_range = request.GET.get('date_range', '7')
    
    # Calculer la période
    end_date = timezone.now()
    if date_range == '7':
        start_date = end_date - timedelta(days=7)
    elif date_range == '30':
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=7)
    
    transactions = RawTransaction.objects.filter(
        uploaded_at__gte=start_date,
        uploaded_at__lte=end_date
    )
    
    if chart_type == 'volume':
        # Données de volume par jour
        daily_data = transactions.extra(
            select={'day': 'date(uploaded_at)'}
        ).values('day').annotate(
            total=Count('id'),
            frauds=Count('id', filter=Q(ml_is_fraud=True))
        ).order_by('day')
        
        return JsonResponse({
            'labels': [item['day'] for item in daily_data],
            'datasets': [
                {
                    'label': 'Total Transactions',
                    'data': [item['total'] for item in daily_data],
                    'backgroundColor': '#4CAF50'
                },
                {
                    'label': 'Fraudes',
                    'data': [item['frauds'] for item in daily_data],
                    'backgroundColor': '#FF9800'
                }
            ]
        })
    
    elif chart_type == 'types':
        # Données par type de transaction
        type_data = transactions.values('trx_type').annotate(
            count=Count('id'),
            fraud_count=Count('id', filter=Q(ml_is_fraud=True))
        ).order_by('-count')
        
        return JsonResponse({
            'labels': [item['trx_type'] for item in type_data],
            'datasets': [
                {
                    'label': 'Total',
                    'data': [item['count'] for item in type_data],
                    'backgroundColor': ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0']
                },
                {
                    'label': 'Fraudes',
                    'data': [item['fraud_count'] for item in type_data],
                    'backgroundColor': ['#F44336', '#E91E63', '#FF5722', '#795548']
                }
            ]
        })
    
    return JsonResponse({'error': 'Type de graphique non supporté'}, status=400)

