from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.core.paginator import Paginator
from django.conf import settings
from django.db import transaction as db_transaction

import pandas as pd
import json
import time
import io
import csv
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    CustomUser, RawTransaction, Client, Bank, 
    DailyInsight, UploadSession, TransactionNote
)
from .utils import (
    apply_fraud_detection_model, 
    generate_claude_analysis,
    generate_claude_client_analysis,
    build_transaction_context,
    update_client_statistics,
    update_bank_statistics,
    get_client_ip,
    generate_daily_insights,
    calculate_transaction_velocity,
    get_transaction_patterns
)


# ==================== AUTHENTIFICATION ====================

def login_view(request):
    """Page de connexion"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Enregistrer l'IP de connexion
            user.last_login_ip = get_client_ip(request)
            user.save()
            
            messages.success(request, f'Bienvenue, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect.')
    
    return render(request, 'auth/login.html')

@login_required
def logout_view(request):
    """Déconnexion"""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté avec succès.')
    return redirect('login')

@login_required
def profile_view(request):
    """Profil utilisateur"""
    return render(request, 'auth/profile.html', {
        'user': request.user
    })


# ==================== DASHBOARD ====================

@login_required
def dashboard_view(request):
    """Dashboard principal avec analytics avancées"""
    
    # Métriques principales
    total_transactions = RawTransaction.objects.count()
    fraud_transactions = RawTransaction.objects.filter(ml_is_fraud=True).count()
    total_clients = Client.objects.count()
    total_banks = Bank.objects.count()
    
    # Transactions récentes
    recent_transactions = RawTransaction.objects.select_related('uploaded_by').order_by('-uploaded_at')[:10]
    
    # Fraudes prioritaires
    urgent_frauds = RawTransaction.objects.filter(
        ml_is_fraud=True,
        claude_priority_level__in=['URGENT', 'HIGH']
    ).order_by('-uploaded_at')[:5]
    
    # Insights quotidiens
    today_insight = DailyInsight.objects.filter(date=timezone.now().date()).first()
    
    # Statistiques par type de transaction
    transaction_types = RawTransaction.objects.values('trx_type').annotate(
        count=Count('id'),
        fraud_count=Count('id', filter=Q(ml_is_fraud=True))
    ).order_by('-count')
    
    # Montants totaux
    total_amount = RawTransaction.objects.aggregate(
        total=Sum('montant'))['total'] or Decimal('0')
    fraud_amount = RawTransaction.objects.filter(ml_is_fraud=True).aggregate(
        total=Sum('montant'))['total'] or Decimal('0')
    
    # Données pour les graphiques du dashboard
    # Série temporelle des 30 derniers jours
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    daily_stats = RawTransaction.objects.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    ).values('transaction_date').annotate(
        count=Count('id'),
        fraud_count=Count('id', filter=Q(ml_is_fraud=True))
    ).order_by('transaction_date')
    
    # Préparer les données pour Chart.js
    chart_labels = []
    chart_counts = []
    chart_frauds = []
    
    for stat in daily_stats:
        chart_labels.append(stat['transaction_date'].strftime('%Y-%m-%d'))
        chart_counts.append(stat['count'])
        chart_frauds.append(stat['fraud_count'])
    
    context = {
        'total_transactions': total_transactions,
        'fraud_transactions': fraud_transactions,
        'total_clients': total_clients,
        'total_banks': total_banks,
        'recent_transactions': recent_transactions,
        'urgent_frauds': urgent_frauds,
        'today_insight': today_insight,
        'transaction_types': transaction_types,
        'total_amount': total_amount,
        'fraud_amount': fraud_amount,
        'fraud_rate': (fraud_transactions / total_transactions * 100) if total_transactions > 0 else 0,
        'chart_labels': json.dumps(chart_labels),
        'chart_counts': json.dumps(chart_counts),
        'chart_frauds': json.dumps(chart_frauds),
    }
    
    return render(request, 'dashboard/dashboard.html', context)


# ==================== UPLOAD CSV ====================

@login_required
def upload_csv_view(request):
    """Page d'upload CSV"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            messages.error(request, 'Veuillez sélectionner un fichier CSV.')
            return render(request, 'upload/upload.html')
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Le fichier doit être au format CSV.')
            return render(request, 'upload/upload.html')
        
        # Créer une session d'upload
        upload_session = UploadSession.objects.create(
            filename=csv_file.name,
            file_size=csv_file.size,
            uploaded_by=request.user
        )
        
        # Stocker le fichier en session pour le traitement
        request.session['upload_session_id'] = upload_session.id
        request.session['csv_file_content'] = csv_file.read().decode('utf-8')
        
        return render(request, 'upload/processing.html', {
            'filename': csv_file.name,
            'file_size': csv_file.size,
            'upload_session': upload_session
        })
    
    return render(request, 'upload/upload.html')

from logging import getLogger,Logger
logger = getLogger(__name__)
@login_required
def process_csv_stream(request):
    """Stream de traitement CSV avec Server-Sent Events"""
    
    def event_stream():
        try:
            upload_session_id = request.session.get('upload_session_id')
            csv_content = request.session.get('csv_file_content')
            
            if not upload_session_id or not csv_content:
                yield f"data: {json.dumps({'error': 'Session expirée'})}\n\n"
                return
            
            upload_session = UploadSession.objects.get(id=upload_session_id)
            
            # Lire le CSV
            csv_file = io.StringIO(csv_content)
            df = pd.read_csv(csv_file)
            
            # Valider les colonnes requises
            required_columns = ['TRX', 'mls', 'TRX_TYPE', 'MONTANT', 
                              'CLIENT_I', 'CLIENT_B', 'BANK_I', 'BANK_B', 'ETAT']
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                yield f"data: {json.dumps({'error': f'Colonnes manquantes: {missing_columns}'})}\n\n"
                return
            
            total_rows = len(df)
            upload_session.total_rows = total_rows
            upload_session.save()
            
            processed_count = 0
            fraud_count = 0
            claude_analyses = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    with db_transaction.atomic():
                        # Vérifier les doublons
                        if RawTransaction.objects.filter(trx=row['TRX']).exists():
                            continue
                        
                        # Parser la date si présente
                        transaction_date = None
                        trx_time_str = str(row.get("TRX_TIME", "")) if pd.notna(row.get("TRX_TIME")) else ""
                        
                        if trx_time_str:
                            try:
                                transaction_date = datetime.strptime(trx_time_str, "%m/%d/%Y %H:%M")
                            except ValueError:
                                try:
                                    transaction_date = pd.to_datetime(trx_time_str)
                                except:
                                    pass
                        
                        # 1. Créer la transaction
                        transaction_data = {
                            'trx': str(row['TRX']),
                            'mls': int(row['mls']) if pd.notna(row['mls']) else 0,
                            'trx_type': str(row['TRX_TYPE']),
                            'montant': Decimal(str(row['MONTANT'])),
                            'client_i': str(row['CLIENT_I']),
                            'client_b': str(row['CLIENT_B']),
                            'bank_i': str(row['BANK_I']),
                            'bank_b': str(row['BANK_B']),
                            'etat': str(row['ETAT']),
                            'uploaded_by': request.user,
                            'transaction_date': transaction_date.date() if transaction_date else None,
                            'trx_time': trx_time_str
                        }
                        
                        transaction_obj = RawTransaction.objects.create(**transaction_data)
                        
                        # 2. Préparer les données pour le modèle ML avec toutes les features
                        ml_input_data = {
                            'trx': transaction_obj.trx,
                            'mls': transaction_obj.mls,
                            'trx_type': transaction_obj.trx_type,
                            'montant': float(transaction_obj.montant),
                            'client_i': transaction_obj.client_i,
                            'client_b': transaction_obj.client_b,
                            'bank_i': transaction_obj.bank_i,
                            'bank_b': transaction_obj.bank_b,
                            'etat': transaction_obj.etat,
                            'trx_time': transaction_date if transaction_date else datetime.now(),
                        }
                        
                        # 3. Appliquer le modèle ML (qui calculera automatiquement les features)
                        ml_result = apply_fraud_detection_model(ml_input_data)
                        
                        # 4. Sauvegarder les résultats ML
                        transaction_obj.ml_is_fraud = ml_result['is_fraud']
                        transaction_obj.ml_risk_score = ml_result.get('risk_score', 0.0)
                        transaction_obj.ml_confidence = ml_result.get('confidence', 0.0)
                        transaction_obj.ml_feature_importance = ml_result.get('feature_importance', {})
                        transaction_obj.ml_processed_at = timezone.now()
                        
                        # 5. Si fraude détectée → Analyse Claude
                        if ml_result['is_fraud']:
                            try:
                                claude_result = generate_claude_analysis(transaction_obj)
                                transaction_obj.claude_explanation = claude_result['explanation']
                                transaction_obj.claude_priority_level = claude_result['priority']
                                transaction_obj.claude_risk_factors = claude_result['risk_factors']
                                transaction_obj.claude_analyzed_at = timezone.now()
                                claude_analyses += 1
                            except Exception as claude_error:
                                logger.error(f"Erreur analyse Claude pour {transaction_obj.trx}: {claude_error}")
                            
                            fraud_count += 1
                        
                        transaction_obj.save()
                        processed_count += 1
                        
                        # 6. Mettre à jour les statistiques
                        try:
                            update_client_statistics(transaction_obj.client_i)
                            if transaction_obj.client_i != transaction_obj.client_b:
                                update_client_statistics(transaction_obj.client_b)
                            update_bank_statistics(transaction_obj.bank_i)
                            if transaction_obj.bank_i != transaction_obj.bank_b:
                                update_bank_statistics(transaction_obj.bank_b)
                        except Exception as stats_error:
                            logger.error(f"Erreur mise à jour statistiques: {stats_error}")
                    
                    # 7. Envoyer le progrès
                    if processed_count % 10 == 0 or processed_count == total_rows:
                        progress = (processed_count / total_rows) * 100
                        data = {
                            'progress': progress,
                            'processed': processed_count,
                            'frauds': fraud_count,
                            'claude_analyses': claude_analyses,
                            'current_transaction': transaction_obj.trx,
                            'errors_count': len(errors)
                        }
                        yield f"data: {json.dumps(data)}\n\n"
                        time.sleep(0.05)
                
                except Exception as e:
                    error_msg = f"Erreur ligne {index + 1}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue
            
            # 8. Finaliser
            upload_session.processed_rows = processed_count
            upload_session.fraud_detected = fraud_count
            upload_session.claude_analyses_generated = claude_analyses
            upload_session.completed_at = timezone.now()
            upload_session.status = 'COMPLETED'
            upload_session.save()
            
            # 9. Générer les insights quotidiens
            try:
                generate_daily_insights()
            except Exception as e:
                logger.error(f"Erreur génération insights: {e}")
            
            final_data = {
                'completed': True,
                'total': processed_count,
                'frauds': fraud_count,
                'claude_analyses': claude_analyses,
                'errors': errors[:10]
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
        except Exception as e:
            error_data = {
                'error': f'Erreur critique: {str(e)}',
                'completed': True
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['X-Accel-Buffering'] = 'no'
    response['Access-Control-Allow-Origin'] = '*'
    return response
# ==================== TRANSACTIONS ====================

@login_required
def transaction_list_view(request):
    """Liste des transactions avec filtres avancés"""
    
    transactions = RawTransaction.objects.select_related('uploaded_by').order_by('-uploaded_at')
    
    # Filtres depuis les paramètres GET
    trx_type_filter = request.GET.get('trx_type')
    if trx_type_filter:
        transactions = transactions.filter(trx_type=trx_type_filter)
    
    etat_filter = request.GET.get('etat')
    if etat_filter:
        transactions = transactions.filter(etat=etat_filter)
    
    fraud_filter = request.GET.get('fraud')
    if fraud_filter == 'fraud_only':
        transactions = transactions.filter(ml_is_fraud=True)
    elif fraud_filter == 'legitimate_only':
        transactions = transactions.filter(ml_is_fraud=False)
    
    client_filter = request.GET.get('client')
    if client_filter:
        transactions = transactions.filter(
            Q(client_i__icontains=client_filter) | Q(client_b__icontains=client_filter)
        )
    
    montant_min = request.GET.get('montant_min')
    if montant_min:
        try:
            transactions = transactions.filter(montant__gte=float(montant_min))
        except ValueError:
            pass
    
    montant_max = request.GET.get('montant_max')
    if montant_max:
        try:
            transactions = transactions.filter(montant__lte=float(montant_max))
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(transactions, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques pour les filtres
    stats = {
        'total': RawTransaction.objects.count(),
        'frauds': RawTransaction.objects.filter(ml_is_fraud=True).count(),
        'types': RawTransaction.objects.values('trx_type').annotate(count=Count('id')),
    }
    
    context = {
        'page_obj': page_obj,
        'transactions': page_obj,  # Pour compatibilité template
        'stats': stats,
        'current_filters': {
            'trx_type': trx_type_filter,
            'etat': etat_filter,
            'fraud': fraud_filter,
            'client': client_filter,
            'montant_min': montant_min,
            'montant_max': montant_max,
        }
    }
    
    return render(request, 'transactions/transaction_list.html', context)


@login_required
def transaction_detail_view(request, transaction_id):
    """Détail d'une transaction avec analytics avancées"""
    
    transaction_obj = get_object_or_404(RawTransaction, id=transaction_id)
    
    # Transactions similaires
    similar_transactions = RawTransaction.objects.filter(
        Q(client_i=transaction_obj.client_i) | Q(client_b=transaction_obj.client_b),
        montant__gte=transaction_obj.montant * Decimal('0.8'),
        montant__lte=transaction_obj.montant * Decimal('1.2')
    ).exclude(id=transaction_obj.id)[:5]
    
    # Contexte client
    client_stats = []
    try:
        sender_client = Client.objects.get(client_id=transaction_obj.client_i)
        client_stats.append(sender_client)
    except Client.DoesNotExist:
        pass
    
    if not transaction_obj.is_self_transfer:
        try:
            receiver_client = Client.objects.get(client_id=transaction_obj.client_b)
            client_stats.append(receiver_client)
        except Client.DoesNotExist:
            pass
    
    context = {
        'transaction': transaction_obj,
        'similar_transactions': similar_transactions,
        'client_stats': client_stats
    }
    
    return render(request, 'transactions/detail.html', context)


# ==================== CLIENTS ====================

@login_required
def client_list_view(request):
    """Liste des clients avec analytics"""
    
    clients = Client.objects.order_by('-fraud_transactions_count', '-total_transactions_sent')
    
    # Filtres
    search = request.GET.get('search')
    if search:
        clients = clients.filter(client_id__icontains=search)
    
    risk_level = request.GET.get('risk')
    if risk_level:
        clients = clients.filter(claude_risk_level=risk_level)
    
    min_transactions = request.GET.get('min_transactions')
    if min_transactions:
        try:
            min_trans = int(min_transactions)
            clients = clients.filter(
                total_transactions_sent__gte=min_trans
            )
        except ValueError:
            pass
    
    # Statistiques pour le header
    clients_watch_count = Client.objects.filter(claude_risk_level='WATCH').count()
    clients_suspect_count = Client.objects.filter(claude_risk_level='SUSPECT').count()
    total_fraud_transactions = Client.objects.aggregate(
        total=Sum('fraud_transactions_count'))['total'] or 0
    
    # Pagination
    paginator = Paginator(clients, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'clients_watch_count': clients_watch_count,
        'clients_suspect_count': clients_suspect_count,
        'total_fraud_transactions': total_fraud_transactions,
        'current_filters': {
            'search': search,
            'risk': risk_level,
            'min_transactions': min_transactions
        }
    }
    
    return render(request, 'clients/list.html', context)

@login_required
def client_detail_view(request, client_id):
    """Profil détaillé d'un client avec time series"""
    from django.utils import timezone
    from datetime import timedelta
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    client = get_object_or_404(Client, client_id=client_id)
    
    # Transactions du client
    transactions = RawTransaction.objects.filter(
        Q(client_i=client_id) | Q(client_b=client_id)
    ).order_by('-uploaded_at')
    
    # Transactions frauduleuses
    fraud_transactions = transactions.filter(ml_is_fraud=True)
    
    # Statistiques temporelles
    recent_activity = transactions.filter(
        uploaded_at__gte=timezone.now() - timedelta(days=30)
    )
    
    # Données pour les graphiques
    time_series_data = client.get_transaction_time_series(days=30)
    hourly_pattern = client.get_hourly_pattern()
    
    print(f"Time series data for client {client_id}: {time_series_data}")
    print(f"Hourly pattern data for client {client_id}: {hourly_pattern}")
    
    # Préparer les données pour Chart.js
    time_series_labels = []
    time_series_counts = []
    time_series_frauds = []
    
    # Fill in missing dates with zeros to ensure continuous timeline
    if time_series_data:
        from datetime import datetime, timedelta
        
        # Create a complete range of dates
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Create a dictionary from existing data
        data_dict = {item['transaction_date']: item for item in time_series_data}
        
        # Fill in the complete date range
        current_date = start_date
        while current_date <= end_date:
            time_series_labels.append(current_date.strftime('%Y-%m-%d'))
            
            if current_date in data_dict:
                time_series_counts.append(int(data_dict[current_date]['count']))
                time_series_frauds.append(int(data_dict[current_date]['fraud_count']))
            else:
                time_series_counts.append(0)
                time_series_frauds.append(0)
            
            current_date += timedelta(days=1)
    else:
        # No data available, create empty arrays
        from datetime import datetime, timedelta
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        current_date = start_date
        while current_date <= end_date:
            time_series_labels.append(current_date.strftime('%Y-%m-%d'))
            time_series_counts.append(0)
            time_series_frauds.append(0)
            current_date += timedelta(days=1)
    
    # Pattern horaire (24 heures) - Initialize with zeros
    hourly_pattern_data = [0] * 24
    
    if hourly_pattern:
        for data in hourly_pattern:
            hour = data.get('transaction_hour')
            if hour is not None and 0 <= hour <= 23:
                hourly_pattern_data[hour] = int(data['count'])
    
    print(f"Final time series labels: {time_series_labels[:5]}...")
    print(f"Final time series counts: {time_series_counts[:5]}...")
    print(f"Final hourly pattern: {hourly_pattern_data}")
    
    # Use DjangoJSONEncoder to handle any special types
    context = {
        'client': client,
        'transactions': transactions[:20],
        'fraud_transactions': fraud_transactions[:10],
        'recent_activity': recent_activity,
        'total_transactions': transactions.count(),
        'fraud_count': fraud_transactions.count(),
        'time_series_labels': json.dumps(time_series_labels, cls=DjangoJSONEncoder),
        'time_series_counts': json.dumps(time_series_counts, cls=DjangoJSONEncoder),
        'time_series_frauds': json.dumps(time_series_frauds, cls=DjangoJSONEncoder),
        'hourly_pattern': json.dumps(hourly_pattern_data, cls=DjangoJSONEncoder),
    }
    
    return render(request, 'clients/detail.html', context)# ==================== ANALYTICS ====================

@login_required
def analytics_view(request):
    """Page d'analytics avancées"""
    
    # Métriques principales
    total_transactions = RawTransaction.objects.count()
    fraud_transactions = RawTransaction.objects.filter(ml_is_fraud=True).count()
    total_amount = RawTransaction.objects.aggregate(Sum('montant'))['montant__sum'] or 0
    avg_transaction_amount = RawTransaction.objects.aggregate(Avg('montant'))['montant__avg'] or 0
    
    # Clients et banques
    unique_clients = Client.objects.count()
    active_banks = Bank.objects.count()
    
    # Top clients à risque
    top_risk_clients = Client.objects.filter(
        fraud_transactions_count__gt=0
    ).order_by('-fraud_transactions_count')[:10]
    
    # Insights du jour
    today_insight = DailyInsight.objects.filter(date=timezone.now().date()).first()
    
    # Données pour les graphiques (30 derniers jours)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Volume time series
    volume_data = RawTransaction.objects.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    ).values('transaction_date').annotate(
        legitimate=Count('id', filter=Q(ml_is_fraud=False)),
        fraud=Count('id', filter=Q(ml_is_fraud=True))
    ).order_by('transaction_date')
    
    volume_labels = []
    volume_legitimate = []
    volume_fraud = []
    
    for data in volume_data:
        volume_labels.append(data['transaction_date'].strftime('%Y-%m-%d'))
        volume_legitimate.append(data['legitimate'])
        volume_fraud.append(data['fraud'])
    
    # Fraud trends
    fraud_trend_data = RawTransaction.objects.filter(
        transaction_date__gte=start_date,
        ml_is_fraud=True
    ).values('transaction_date').annotate(
        count=Count('id')
    ).order_by('transaction_date')
    
    fraud_trend_labels = []
    fraud_trend_counts = []
    
    for data in fraud_trend_data:
        fraud_trend_labels.append(data['transaction_date'].strftime('%Y-%m-%d'))
        fraud_trend_counts.append(data['count'])
    
    # Transaction types
    transaction_types = RawTransaction.objects.values('trx_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    transaction_type_labels = [t['trx_type'] for t in transaction_types]
    transaction_type_data = [t['count'] for t in transaction_types]
    
    # Transaction status
    transaction_status = RawTransaction.objects.values('etat').annotate(
        count=Count('id')
    )
    
    status_ok = next((s['count'] for s in transaction_status if s['etat'] == 'OK'), 0)
    status_ko = next((s['count'] for s in transaction_status if s['etat'] == 'KO'), 0)
    status_att = next((s['count'] for s in transaction_status if s['etat'] == 'ATT'), 0)
    
    # Bank performance
    bank_stats = Bank.objects.order_by('-total_transactions')[:10]
    bank_labels = [bank.bank_code for bank in bank_stats]
    bank_transaction_data = [bank.total_transactions for bank in bank_stats]
    
    # Hourly activity
    hourly_activity = RawTransaction.objects.values('transaction_hour').annotate(
        count=Count('id')
    ).order_by('transaction_hour')
    
    hourly_activity_data = [0] * 24
    for data in hourly_activity:
        if data['transaction_hour'] is not None:
            hourly_activity_data[data['transaction_hour']] = data['count']
    print(hourly_activity_data)
    print(fraud_trend_data)
    print(total_transactions)
    print(total_amount)
    print(volume_data)
    context = {
        'total_transactions': total_transactions,
        'fraud_transactions': fraud_transactions,
        'fraud_rate': (fraud_transactions / total_transactions * 100) if total_transactions > 0 else 0,
        'total_amount': total_amount,
        'avg_transaction_amount': avg_transaction_amount,
        'unique_clients': unique_clients,
        'active_banks': active_banks,
        'processing_time': 150,  # Mock data
        'top_risk_clients': top_risk_clients,
        'today_insight': today_insight,
        
        # Chart data
        'volume_labels': json.dumps(volume_labels),
        'volume_legitimate': json.dumps(volume_legitimate),
        'volume_fraud': json.dumps(volume_fraud),
        'fraud_trend_labels': json.dumps(fraud_trend_labels),
        'fraud_trend_data': json.dumps(fraud_trend_counts),
        'detection_rate_data': json.dumps([80, 85, 82, 88, 90] * 6),  # Mock data
        'transaction_type_labels': json.dumps(transaction_type_labels),
        'transaction_type_data': json.dumps(transaction_type_data),
        'transaction_status_data': json.dumps([status_ok, status_ko, status_att]),
        'bank_labels': json.dumps(bank_labels),
        'bank_transaction_data': json.dumps(bank_transaction_data),
        'hourly_activity_data': json.dumps(hourly_activity_data),
    }
    
    return render(request, 'analytics/analytics.html', context)



# ==================== API ENDPOINTS ====================

@login_required
@require_http_methods(["POST"])
def analyze_transaction_claude(request, transaction_id):
    """API pour analyser une transaction avec Claude"""
    
    try:
        transaction_obj = get_object_or_404(RawTransaction, id=transaction_id)
        
        # Générer l'analyse Claude
        claude_result = generate_claude_analysis(transaction_obj)
        
        # Sauvegarder les résultats
        transaction_obj.claude_explanation = claude_result['explanation']
        transaction_obj.claude_priority_level = claude_result['priority']
        transaction_obj.claude_risk_factors = claude_result['risk_factors']
        transaction_obj.claude_analyzed_at = timezone.now()
        transaction_obj.save()
        
        return JsonResponse({
            'success': True,
            'explanation': claude_result['explanation'],
            'priority': claude_result['priority'],
            'risk_factors': claude_result['risk_factors']
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def analyze_client_claude(request, client_id):
    """API pour analyser un client avec Claude"""
    
    try:
        client = get_object_or_404(Client, client_id=client_id)
        
        # Générer l'analyse Claude
        claude_result = generate_claude_client_analysis(client)
        
        # Sauvegarder les résultats
        client.claude_risk_assessment = claude_result.get('assessment', 'Analyse effectuée')
        client.claude_risk_level = claude_result.get('risk_level', 'MEDIUM')
        client.claude_behavioral_patterns = claude_result.get('behavioral_patterns', [])
        client.claude_last_analyzed = timezone.now()
        client.save()
        
        return JsonResponse({
            'success': True,
            'analysis': claude_result.get('assessment', 'Analyse effectuée'),
            'risk_level': claude_result.get('risk_level', 'MEDIUM'),
            'behavioral_patterns': claude_result.get('behavioral_patterns', []),
            'surveillance_recommendations': claude_result.get('surveillance_recommendations', []),
            'analyzed_at': client.claude_last_analyzed.isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_http_methods(["POST"])
def add_transaction_note(request, transaction_id):
    """API pour ajouter une note à une transaction"""
    
    try:
        transaction_obj = get_object_or_404(RawTransaction, id=transaction_id)
        data = json.loads(request.body)
        
        note = TransactionNote.objects.create(
            transaction=transaction_obj,
            author=request.user,
            note=data.get('note', ''),
            is_flagged=data.get('is_flagged', False)
        )
        
        return JsonResponse({
            'success': True,
            'note_id': note.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def analytics_data_api(request):
    """API pour récupérer les données d'analytics"""
    
    if request.method == 'POST':
        data = json.loads(request.body)
        time_range = int(data.get('time_range', 30))
        transaction_type = data.get('transaction_type', '')
        
        # Calculer les nouvelles données basées sur les filtres
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=time_range)
        
        transactions = RawTransaction.objects.filter(
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )
        
        if transaction_type:
            transactions = transactions.filter(trx_type=transaction_type)
        
        # Recalculer les métriques
        total_transactions = transactions.count()
        fraud_transactions = transactions.filter(ml_is_fraud=True).count()
        total_amount = transactions.aggregate(Sum('montant'))['montant__sum'] or 0
        
        # Nouvelles données de série temporelle
        volume_data = transactions.values('transaction_date').annotate(
            legitimate=Count('id', filter=Q(ml_is_fraud=False)),
            fraud=Count('id', filter=Q(ml_is_fraud=True))
        ).order_by('transaction_date')
        
        volume_labels = []
        volume_legitimate = []
        volume_fraud = []
        
        for data_point in volume_data:
            volume_labels.append(data_point['transaction_date'].strftime('%Y-%m-%d'))
            volume_legitimate.append(data_point['legitimate'])
            volume_fraud.append(data_point['fraud'])
        
        return JsonResponse({
            'total_transactions': total_transactions,
            'fraud_transactions': fraud_transactions,
            'fraud_rate': (fraud_transactions / total_transactions * 100) if total_transactions > 0 else 0,
            'total_amount': f"{total_amount:,.0f}",
            'volume_labels': volume_labels,
            'volume_legitimate': volume_legitimate,
            'volume_fraud': volume_fraud,
            'fraud_trend_labels': volume_labels,
            'fraud_trend_data': volume_fraud,
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def analytics_alerts_api(request):
    """API pour récupérer les alertes temps réel"""
    
    # Simuler des alertes temps réel
    alerts = [
        {
            'type': 'warning',
            'icon': 'exclamation-triangle',
            'message': f'Transaction suspecte détectée - Montant élevé: {timezone.now().strftime("%H:%M")}'
        },
        {
            'type': 'info',
            'icon': 'info-circle',
            'message': 'Nouveau pattern de fraude identifié dans les transferts nocturnes'
        },
        {
            'type': 'success',
            'icon': 'check-circle',
            'message': 'Modèle ML mis à jour avec succès'
        }
    ]
    
    return JsonResponse({'alerts': alerts})

@login_required
@require_http_methods(["POST"])
def generate_insights_api(request):
    """API pour générer les insights quotidiens"""
    
    try:
        generate_daily_insights()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_http_methods(["POST"])
def refresh_client_analytics(request):
    """API pour actualiser les analytics des clients"""
    
    try:
        # Mettre à jour les statistiques de tous les clients
        clients = Client.objects.all()
        updated_count = 0
        
        for client in clients:
            client.update_statistics()
            updated_count += 1
        
        return JsonResponse({
            'success': True,
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# ==================== EXPORT FUNCTIONS ====================

@login_required
def export_analytics_report(request):
    """Exporter un rapport d'analytics en CSV"""
    
    time_range = int(request.GET.get('time_range', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=time_range)
    
    transactions = RawTransaction.objects.filter(
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    )
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_report_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Total Transactions', 'Fraud Transactions', 
        'Fraud Rate (%)', 'Total Amount', 'Avg Amount'
    ])
    
    daily_stats = transactions.values('transaction_date').annotate(
        total=Count('id'),
        frauds=Count('id', filter=Q(ml_is_fraud=True)),
        total_amount=Sum('montant'),
        avg_amount=Avg('montant')
    ).order_by('transaction_date')
    
    for stat in daily_stats:
        fraud_rate = (stat['frauds'] / stat['total'] * 100) if stat['total'] > 0 else 0
        writer.writerow([
            stat['transaction_date'],
            stat['total'],
            stat['frauds'],
            f"{fraud_rate:.2f}",
            f"{stat['total_amount']:.2f}",
            f"{stat['avg_amount']:.2f}"
        ])
    
    return response


def transaction_detail(request, transaction_id):
    """
    Display detailed view of a specific transaction with Claude analysis.
    """
    transaction = get_object_or_404(RawTransaction, id=transaction_id)
    
    if not transaction.claude_explanation:
        try:
            claude_result = generate_claude_analysis(transaction)
            transaction.claude_explanation = claude_result['explanation']
            transaction.claude_priority_level = claude_result['priority']
            transaction.claude_analyzed_at = timezone.now()
            transaction.save()
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({
        'analysis': transaction.claude_explanation,
        'priority': transaction.claude_priority_level,
        'analyzed_at': transaction.claude_analyzed_at.isoformat()
    })


# ==================== ANALYTICS ====================



# ==================== UTILS ====================

def get_client_ip(request):
    """Récupère l'IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

