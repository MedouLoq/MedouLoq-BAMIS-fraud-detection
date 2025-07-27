"""
Module pour la génération de graphiques Bokeh pour la plateforme BAMIS
"""

import pandas as pd
import numpy as np
from bokeh.plotting import figure
from bokeh.models import (
    HoverTool, ColumnDataSource, LinearColorMapper, ColorBar,
    DatetimeTickFormatter, NumeralTickFormatter, Legend, LegendItem,
    Div, Panel, Tabs, DataTable, TableColumn, StringFormatter,
    NumberFormatter, HTMLTemplateFormatter
)
from bokeh.layouts import column, row, gridplot
from bokeh.palettes import Category20, RdYlBu, Viridis256, Spectral6
from bokeh.transform import cumsum, factor_cmap
from bokeh.embed import components
from bokeh.io import curdoc
from bokeh.themes import Theme
from datetime import datetime, timedelta
import json

# Couleurs BAMIS
BAMIS_COLORS = {
    'green_primary': '#4CAF50',
    'green_light': '#66BB6A',
    'green_dark': '#388E3C',
    'orange_primary': '#FF9800',
    'orange_light': '#FFB74D',
    'orange_dark': '#F57C00',
    'danger': '#F44336',
    'info': '#2196F3',
    'gray': '#9E9E9E',
    'white': '#FFFFFF',
    'black': '#000000'
}

# Thème BAMIS pour Bokeh
BAMIS_THEME = Theme(json={
    "attrs": {
        "Figure": {
            "background_fill_color": "#FAFAFA",
            "border_fill_color": "#FFFFFF",
            "outline_line_color": "#E0E0E0",
            "outline_line_width": 1,
        },
        "Grid": {
            "grid_line_color": "#E0E0E0",
            "grid_line_alpha": 0.5,
        },
        "Axis": {
            "axis_line_color": "#424242",
            "axis_label_text_color": "#424242",
            "major_tick_line_color": "#424242",
            "major_label_text_color": "#424242",
            "minor_tick_line_color": "#757575",
            "axis_label_text_font": "Inter",
            "major_label_text_font": "Inter",
        },
        "Title": {
            "text_color": "#212121",
            "text_font": "Inter",
            "text_font_size": "16pt",
            "text_font_style": "bold",
        },
        "Legend": {
            "background_fill_color": "#FFFFFF",
            "background_fill_alpha": 0.9,
            "border_line_color": "#E0E0E0",
            "label_text_font": "Inter",
            "label_text_color": "#424242",
        }
    }
})

class BokehChartGenerator:
    """Générateur de graphiques Bokeh pour la plateforme BAMIS"""
    
    def __init__(self):
        self.theme = BAMIS_THEME
        
    def create_transaction_volume_chart(self, transactions_df):
        """Créer un graphique de volume des transactions par jour"""
        if transactions_df.empty:
            return self._create_empty_chart("Aucune donnée de transaction disponible")
        
        # Préparer les données
        daily_data = transactions_df.groupby(
            transactions_df['uploaded_at'].dt.date
        ).agg({
            'amount': ['count', 'sum'],
            'ml_is_fraud': 'sum'
        }).reset_index()
        
        daily_data.columns = ['date', 'count', 'total_amount', 'fraud_count']
        daily_data['date'] = pd.to_datetime(daily_data['date'])
        daily_data['normal_count'] = daily_data['count'] - daily_data['fraud_count']
        
        source = ColumnDataSource(daily_data)
        
        # Créer la figure
        p = figure(
            title="Volume des Transactions par Jour",
            x_axis_type='datetime',
            width=800,
            height=400,
            tools="pan,wheel_zoom,box_zoom,reset,save",
            toolbar_location="above"
        )
        
        # Barres empilées
        p.vbar_stack(
            ['normal_count', 'fraud_count'],
            x='date',
            width=timedelta(days=0.8),
            color=[BAMIS_COLORS['green_primary'], BAMIS_COLORS['orange_primary']],
            source=source,
            legend_label=['Transactions Normales', 'Fraudes Détectées']
        )
        
        # Configuration des axes
        p.xaxis.formatter = DatetimeTickFormatter(days="%d/%m")
        p.yaxis.formatter = NumeralTickFormatter(format="0,0")
        
        # Hover tool
        hover = HoverTool(
            tooltips=[
                ('Date', '@date{%F}'),
                ('Total Transactions', '@count'),
                ('Transactions Normales', '@normal_count'),
                ('Fraudes', '@fraud_count'),
                ('Montant Total', '@total_amount{0,0.00} MRU')
            ],
            formatters={'@date': 'datetime'}
        )
        p.add_tools(hover)
        
        # Style
        p.legend.location = "top_left"
        p.legend.click_policy = "hide"
        
        return p
    
    def create_fraud_distribution_pie(self, transactions_df):
        """Créer un graphique en secteurs de la distribution des fraudes"""
        if transactions_df.empty:
            return self._create_empty_chart("Aucune donnée disponible")
        
        # Calculer les statistiques
        total_transactions = len(transactions_df)
        fraud_transactions = transactions_df['ml_is_fraud'].sum()
        normal_transactions = total_transactions - fraud_transactions
        
        data = {
            'category': ['Transactions Normales', 'Fraudes Détectées'],
            'count': [normal_transactions, fraud_transactions],
            'angle': [
                2 * np.pi * normal_transactions / total_transactions,
                2 * np.pi * fraud_transactions / total_transactions
            ],
            'color': [BAMIS_COLORS['green_primary'], BAMIS_COLORS['orange_primary']]
        }
        
        source = ColumnDataSource(data)
        
        p = figure(
            title="Distribution des Transactions",
            toolbar_location=None,
            tools="hover",
            tooltips="@category: @count (@{angle}{0.00} rad)",
            x_range=(-0.5, 1.0),
            width=400,
            height=400
        )
        
        p.wedge(
            x=0, y=1, radius=0.4,
            start_angle=cumsum('angle', include_zero=True),
            end_angle=cumsum('angle'),
            line_color="white",
            fill_color='color',
            source=source
        )
        
        p.axis.axis_label = None
        p.axis.visible = False
        p.grid.grid_line_color = None
        
        return p
    
    def create_amount_distribution_histogram(self, transactions_df):
        """Créer un histogramme de la distribution des montants"""
        if transactions_df.empty:
            return self._create_empty_chart("Aucune donnée disponible")
        
        # Séparer les transactions normales et frauduleuses
        normal_amounts = transactions_df[~transactions_df['ml_is_fraud']]['amount']
        fraud_amounts = transactions_df[transactions_df['ml_is_fraud']]['amount']
        
        # Créer les histogrammes
        hist_normal, edges = np.histogram(normal_amounts, bins=50)
        hist_fraud, _ = np.histogram(fraud_amounts, bins=edges)
        
        p = figure(
            title="Distribution des Montants de Transaction",
            width=800,
            height=400,
            tools="pan,wheel_zoom,box_zoom,reset,save"
        )
        
        # Barres pour transactions normales
        p.quad(
            top=hist_normal, bottom=0,
            left=edges[:-1], right=edges[1:],
            fill_color=BAMIS_COLORS['green_primary'],
            line_color="white",
            alpha=0.7,
            legend_label="Transactions Normales"
        )
        
        # Barres pour fraudes
        p.quad(
            top=hist_fraud, bottom=0,
            left=edges[:-1], right=edges[1:],
            fill_color=BAMIS_COLORS['orange_primary'],
            line_color="white",
            alpha=0.7,
            legend_label="Fraudes"
        )
        
        p.xaxis.axis_label = "Montant ( MRU)"
        p.yaxis.axis_label = "Nombre de Transactions"
        p.xaxis.formatter = NumeralTickFormatter(format="0,0")
        p.legend.location = "top_right"
        
        return p
    
    def create_client_risk_scatter(self, clients_df):
        """Créer un graphique de dispersion des risques clients"""
        if clients_df.empty:
            return self._create_empty_chart("Aucune donnée client disponible")
        
        # Préparer les données
        source = ColumnDataSource(clients_df)
        
        # Mapper les couleurs selon le niveau de risque
        color_mapper = LinearColorMapper(
            palette=Viridis256,
            low=clients_df['fraud_rate'].min(),
            high=clients_df['fraud_rate'].max()
        )
        
        p = figure(
            title="Analyse des Risques Clients",
            width=800,
            height=500,
            tools="pan,wheel_zoom,box_zoom,reset,save"
        )
        
        scatter = p.circle(
            'total_transactions', 'total_amount',
            size='fraud_count',
            color={'field': 'fraud_rate', 'transform': color_mapper},
            alpha=0.7,
            source=source
        )
        
        # Ajouter une barre de couleur
        color_bar = ColorBar(
            color_mapper=color_mapper,
            width=8,
            location=(0, 0),
            title="Taux de Fraude (%)"
        )
        p.add_layout(color_bar, 'right')
        
        # Hover tool
        hover = HoverTool(
            tooltips=[
                ('Client', '@client_id'),
                ('Transactions', '@total_transactions'),
                ('Montant Total', '@total_amount{0,0.00} MRU'),
                ('Fraudes', '@fraud_count'),
                ('Taux de Fraude', '@fraud_rate{0.0}%')
            ]
        )
        p.add_tools(hover)
        
        p.xaxis.axis_label = "Nombre de Transactions"
        p.yaxis.axis_label = "Montant Total ( MRU)"
        p.yaxis.formatter = NumeralTickFormatter(format="0,0")
        
        return p
    
    def create_transaction_type_bar_chart(self, transactions_df):
        """Créer un graphique en barres par type de transaction"""
        if transactions_df.empty:
            return self._create_empty_chart("Aucune donnée disponible")
        
        # Grouper par type de transaction
        type_stats = transactions_df.groupby('trx_type').agg({
            'amount': ['count', 'sum'],
            'ml_is_fraud': 'sum'
        }).reset_index()
        
        type_stats.columns = ['trx_type', 'count', 'total_amount', 'fraud_count']
        type_stats['normal_count'] = type_stats['count'] - type_stats['fraud_count']
        type_stats['fraud_rate'] = (type_stats['fraud_count'] / type_stats['count'] * 100).round(1)
        
        source = ColumnDataSource(type_stats)
        
        p = figure(
            x_range=type_stats['trx_type'].tolist(),
            title="Transactions par Type",
            width=600,
            height=400,
            tools="pan,wheel_zoom,box_zoom,reset,save"
        )
        
        # Barres empilées
        p.vbar_stack(
            ['normal_count', 'fraud_count'],
            x='trx_type',
            width=0.6,
            color=[BAMIS_COLORS['green_primary'], BAMIS_COLORS['orange_primary']],
            source=source,
            legend_label=['Normales', 'Fraudes']
        )
        
        # Hover tool
        hover = HoverTool(
            tooltips=[
                ('Type', '@trx_type'),
                ('Total', '@count'),
                ('Normales', '@normal_count'),
                ('Fraudes', '@fraud_count'),
                ('Taux de Fraude', '@fraud_rate%')
            ]
        )
        p.add_tools(hover)
        
        p.xaxis.axis_label = "Type de Transaction"
        p.yaxis.axis_label = "Nombre de Transactions"
        p.legend.location = "top_right"
        
        return p
    
    def create_time_series_chart(self, transactions_df):
        """Créer un graphique de série temporelle des fraudes"""
        if transactions_df.empty:
            return self._create_empty_chart("Aucune donnée disponible")
        
        # Grouper par heure
        hourly_data = transactions_df.groupby(
            transactions_df['uploaded_at'].dt.floor('H')
        ).agg({
            'amount': 'count',
            'ml_is_fraud': 'sum'
        }).reset_index()
        
        hourly_data.columns = ['datetime', 'total', 'frauds']
        hourly_data['fraud_rate'] = (hourly_data['frauds'] / hourly_data['total'] * 100).round(2)
        
        source = ColumnDataSource(hourly_data)
        
        p = figure(
            title="Évolution Temporelle des Fraudes",
            x_axis_type='datetime',
            width=800,
            height=400,
            tools="pan,wheel_zoom,box_zoom,reset,save"
        )
        
        # Ligne pour le taux de fraude
        line = p.line(
            'datetime', 'fraud_rate',
            line_width=3,
            color=BAMIS_COLORS['orange_primary'],
            source=source,
            legend_label="Taux de Fraude (%)"
        )
        
        # Points pour mettre en évidence
        circles = p.circle(
            'datetime', 'fraud_rate',
            size=8,
            color=BAMIS_COLORS['orange_primary'],
            source=source
        )
        
        # Hover tool
        hover = HoverTool(
            tooltips=[
                ('Heure', '@datetime{%F %H:%M}'),
                ('Total Transactions', '@total'),
                ('Fraudes', '@frauds'),
                ('Taux de Fraude', '@fraud_rate%')
            ],
            formatters={'@datetime': 'datetime'}
        )
        p.add_tools(hover)
        
        p.xaxis.formatter = DatetimeTickFormatter(hours="%H:%M")
        p.yaxis.axis_label = "Taux de Fraude (%)"
        p.legend.location = "top_left"
        
        return p
    
    def create_dashboard_layout(self, transactions_df, clients_df=None):
        """Créer un layout complet pour le dashboard"""
        charts = []
        
        # Graphique de volume
        volume_chart = self.create_transaction_volume_chart(transactions_df)
        charts.append(volume_chart)
        
        # Graphiques en ligne
        row1 = []
        
        # Distribution des fraudes
        pie_chart = self.create_fraud_distribution_pie(transactions_df)
        row1.append(pie_chart)
        
        # Types de transactions
        type_chart = self.create_transaction_type_bar_chart(transactions_df)
        row1.append(type_chart)
        
        charts.append(row(row1))
        
        # Histogramme des montants
        amount_hist = self.create_amount_distribution_histogram(transactions_df)
        charts.append(amount_hist)
        
        # Série temporelle
        time_series = self.create_time_series_chart(transactions_df)
        charts.append(time_series)
        
        # Graphique des clients si disponible
        if clients_df is not None and not clients_df.empty:
            client_scatter = self.create_client_risk_scatter(clients_df)
            charts.append(client_scatter)
        
        return column(charts)
    
    def _create_empty_chart(self, message):
        """Créer un graphique vide avec un message"""
        p = figure(
            title=message,
            width=400,
            height=300,
            toolbar_location=None
        )
        
        p.text(
            x=[0.5], y=[0.5],
            text=[message],
            text_align="center",
            text_baseline="middle",
            text_font_size="14pt",
            text_color=BAMIS_COLORS['gray']
        )
        
        p.axis.visible = False
        p.grid.visible = False
        
        return p
    
    def get_chart_components(self, chart):
        """Obtenir les composants HTML et JS pour intégration Django"""
        script, div = components(chart, theme=self.theme)
        return script, div

def generate_analytics_charts(transactions_queryset, clients_queryset=None):
    """Fonction utilitaire pour générer les graphiques d'analytics"""
    generator = BokehChartGenerator()
    
    # Convertir les querysets en DataFrames
    if transactions_queryset.exists():
        transactions_df = pd.DataFrame(list(transactions_queryset.values(
            'trx', 'amount', 'trx_type', 'ml_is_fraud', 'uploaded_at',
            'client_i', 'client_b'
        )))
    else:
        transactions_df = pd.DataFrame()
    
    clients_df = None
    if clients_queryset and clients_queryset.exists():
        clients_df = pd.DataFrame(list(clients_queryset.values()))
    
    # Créer le layout du dashboard
    layout = generator.create_dashboard_layout(transactions_df, clients_df)
    
    # Retourner les composants
    return generator.get_chart_components(layout)

