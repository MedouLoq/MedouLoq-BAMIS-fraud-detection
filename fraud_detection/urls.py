from django.urls import path
from . import views
from . import views_banks

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Upload
    path('upload/', views.upload_csv_view, name='upload_csv'),
    path('upload/process-stream/', views.process_csv_stream, name='process_csv_stream'),
    
    # Transactions
    path('transactions/', views.transaction_list_view, name='transaction_list'),
    path('transactions/<int:transaction_id>/', views.transaction_detail_view, name='transaction_detail'),
    
    # Clients
    path('clients/', views.client_list_view, name='client_list'),
    path('clients/<str:client_id>/', views.client_detail_view, name='client_detail'),
    
    # Banks
    path('banks/', views_banks.bank_list_view, name='bank_list'),
    path('banks/<str:bank_code>/', views_banks.bank_detail_view, name='bank_detail'),
    path('banks/comparison/', views_banks.banks_comparison_view, name='banks_comparison'),
    
    # Analytics (avec Bokeh intégré)
    path('analytics/', views.analytics_view, name='analytics'),
    
    # API Endpoints
    path('api/transactions/<int:transaction_id>/analyze/', views.analyze_transaction_claude, name='api_analyze_transaction'),
    path('api/transactions/<int:transaction_id>/claude-analyze/', views.analyze_transaction_claude, name='api_claude_analyze_transaction'),
    path('api/transactions/<int:transaction_id>/notes/', views.add_transaction_note, name='api_add_transaction_note'),
    path('api/clients/<str:client_id>/analyze/', views.analyze_client_claude, name='api_analyze_client'),
    path('api/clients/refresh-analytics/', views.refresh_client_analytics, name='api_refresh_client_analytics'),
    path('api/banks/<str:bank_code>/refresh/', views_banks.bank_refresh_statistics, name='api_refresh_bank_stats'),
    path('api/banks/analytics/', views_banks.bank_analytics_api, name='api_bank_analytics'),
    path('api/analytics/data/', views.analytics_data_api, name='api_analytics_data'),
    path('api/analytics/alerts/', views.analytics_alerts_api, name='api_analytics_alerts'),
    path('api/analytics/generate-insights/', views.generate_insights_api, name='api_generate_insights'),
    path('api/analytics/export/', views.export_analytics_report, name='api_export_analytics'),
]

