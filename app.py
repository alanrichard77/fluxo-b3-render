from flask import Flask, render_template, request
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import io
import base64
import numpy as np

app = Flask(__name__)

def get_data(start_date, end_date):
    ibov = yf.download('^BVSP', start=start_date, end=end_date)['Close'].reset_index()
    ibov.columns = ['data', 'ibovespa']
    url = 'https://www.dadosdemercado.com.br/fluxo'
    df = pd.read_html(url, decimal=',', thousands='.')[0]
    df.columns = [c.lower() for c in df.columns]
    df['data'] = pd.to_datetime(df['data'], dayfirst=True)
    df = df[(df['data'] >= pd.to_datetime(start_date)) & (df['data'] <= pd.to_datetime(end_date))]
    df = df.sort_values('data').reset_index(drop=True)
    return ibov, df

def plot_chart(ibov, df):
    fig, ax1 = plt.subplots(figsize=(12, 6))
    categorias = ['estrangeiro', 'institucional', 'pessoa física', 'inst. financeira', 'outros']
    cores = ['#4e79a7', '#f28e2c', '#59a14f', '#76b7b2', '#af7aa1']
    for cat, cor in zip(categorias, cores):
        if cat in df.columns:
            ax1.plot(df['data'], df[cat], label=cat.title(), color=cor, linewidth=2)

    ax1.set_ylabel('Acumulado (R$ bilhões)', color='white')
    ax1.tick_params(axis='y', labelcolor='white')
    ax1.set_facecolor('#1c1f2e')
    ax1.grid(True, linestyle='--', alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(ibov['data'], ibov['ibovespa'], 'w--', linewidth=1.5, label='Ibovespa')
    ax2.set_ylabel('Ibovespa (pts)', color='white')
    ax2.tick_params(axis='y', labelcolor='white')

    fig.patch.set_facecolor('#1c1f2e')
    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))

    plt.title('')
    fig.text(0.5, 0.5, '@alan_richard', fontsize=40, color='gray', ha='center', va='center', alpha=0.1)
    ax1.legend(loc='upper left')
    fig.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png', dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode()

@app.route("/", methods=["GET", "POST"])
def index():
    start_date = request.form.get("start") or "2025-01-01"
    end_date = request.form.get("end") or datetime.today().strftime('%Y-%m-%d')
    ibov, df = get_data(start_date, end_date)

    categorias = {
        'estrangeiro': 'fundos e investidores de fora do Brasil',
        'institucional': 'fundos de pensão, seguradoras, etc',
        'pessoa física': 'investidores individuais',
        'inst. financeira': 'bancos e corretoras',
        'outros': 'empresas, governo e não categorizados'
    }

    resumo = []
    for cat in categorias:
        if cat in df.columns:
            saldo = df[cat].iloc[-1]
            entrada = saldo >= 0
            resumo.append({
                'categoria': cat.title(),
                'descricao': categorias[cat],
                'valor': f"R$ {abs(saldo):,.2f}Bi".replace('.', 'v').replace(',', '.').replace('v', ','),
                'tipo': 'Entrada líquida' if entrada else 'Saída líquida',
                'cor': 'green' if entrada else 'red'
            })

    chart = plot_chart(ibov, df)
    ultima_data = df['data'].max().strftime('%d/%m/%Y')
    return render_template("index.html", chart=chart, resumo=resumo, ultima_data=ultima_data)

if __name__ == "__main__":
    app.run(debug=True)
