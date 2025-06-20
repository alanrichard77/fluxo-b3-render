
from flask import Flask, render_template, request
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf
from datetime import datetime
import io, base64, unicodedata

app = Flask(__name__)

def normalize_colname(col):
    return ''.join(c for c in unicodedata.normalize('NFD', str(col))
                   if unicodedata.category(c) != 'Mn').lower().replace(' ', '').replace('.', '')

def parse_valor(valor):
    try:
        v = str(valor).lower().replace('r$', '').replace('mi', '').replace('bi', '').replace('.', '').replace(',', '.').strip()
        if 'mi' in valor.lower(): return float(v) / 1000
        if 'bi' in valor.lower(): return float(v)
        return float(v)
    except:
        return 0.0

def obter_dados(start, end):
    fluxo_url = 'https://www.dadosdemercado.com.br/fluxo'
    fluxo = pd.read_html(fluxo_url, decimal=',', thousands='.')[0]
    fluxo.columns = [normalize_colname(c) for c in fluxo.columns]
    fluxo['data'] = pd.to_datetime(fluxo['data'], dayfirst=True, errors='coerce')
    fluxo = fluxo.dropna(subset=['data'])
    fluxo = fluxo[(fluxo['data'] >= pd.to_datetime(start)) & (fluxo['data'] <= pd.to_datetime(end))]
    fluxo = fluxo.sort_values('data')

    colunas_fluxo = [c for c in fluxo.columns if any(x in c for x in ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros'])]
    for col in colunas_fluxo:
        fluxo[col+'_bi'] = fluxo[col].apply(parse_valor)
        fluxo[col+'_acum'] = fluxo[col+'_bi'].cumsum()

    ibov = yf.download('^BVSP', start=start, end=end).reset_index()
    ibov = ibov.rename(columns={'Date': 'data', 'Close': 'ibovespa'})
    ibov = ibov[['data', 'ibovespa']]
    df = pd.merge(fluxo, ibov, how='left', on='data')
    df['ibovespa'] = df['ibovespa'].fillna(method='ffill')
    return df

def gerar_grafico(df):
    cores = ['#60a5fa', '#fb923c', '#4ade80', '#f472b6', '#c084fc']
    categorias = ['estrangeiro_acum', 'institucional_acum', 'pessoafisica_acum', 'instfinanceira_acum', 'outros_acum']
    nomes = ['Estrangeiro', 'Institucional', 'Pessoa Física', 'Inst. Financeira', 'Outros']

    plt.style.use('dark_background')
    fig, ax1 = plt.subplots(figsize=(16,9))
    ax1.grid(True, linestyle=':', linewidth=0.5)

    for i, cat in enumerate(categorias):
        if cat in df.columns:
            ax1.plot(df['data'], df[cat], label=nomes[i], color=cores[i], linewidth=2.5)

    ax2 = ax1.twinx()
    ax2.plot(df['data'], df['ibovespa'], '--', color='gray', linewidth=2, label='Ibovespa')
    ax2.set_ylim(df['ibovespa'].min() // 2500 * 2500, df['ibovespa'].max() // 2500 * 2500 + 2500)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(2500))
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', '.')))
    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    ax1.set_xticks(df['data'][::7])
    ax1.set_xticklabels([d.strftime('%d/%m') for d in df['data'][::7]])
    ax1.text(0.5, 0.5, '@alan_richard', transform=ax1.transAxes, fontsize=50, color='gray', ha='center', va='center', alpha=0.12, weight='bold', rotation=15)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@app.route("/", methods=["GET", "POST"])
def home():
    data_inicio = request.form.get('data_inicio') or '2025-01-01'
    data_fim = request.form.get('data_fim') or datetime.today().strftime('%Y-%m-%d')
    df = obter_dados(data_inicio, data_fim)
    grafico = gerar_grafico(df)

    resumo = {}
    for cat in ['estrangeiro_acum', 'institucional_acum', 'pessoafisica_acum', 'instfinanceira_acum', 'outros_acum']:
        resumo[cat] = df[cat].iloc[-1] if cat in df.columns else 0.0

    cards = []
    explicacoes = {
        'estrangeiro_acum': 'Fundos e investidores de fora do Brasil',
        'institucional_acum': 'Fundos de pensão, seguradoras, etc.',
        'pessoafisica_acum': 'Investidores individuais',
        'instfinanceira_acum': 'Bancos e corretoras',
        'outros_acum': 'Empresas, governo e não categorizados'
    }
    for key, val in resumo.items():
        cards.append({
            'nome': key.replace('_acum','').capitalize().replace('pessoafisica','Pessoa Física').replace('instfinanceira','Inst. Financeira'),
            'saldo': f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            'resumo': explicacoes.get(key, '')
        })

    df['ano_mes'] = df['data'].dt.to_period('M')
    resumo_mensal = []
    categorias = ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros']
    for mes, grupo in df.groupby('ano_mes'):
        saldos = {cat: grupo[cat+'_bi'].sum() for cat in categorias}
        maior_compra = max(saldos.items(), key=lambda x: x[1])
        maior_venda = min(saldos.items(), key=lambda x: x[1])
        resumo_mensal.append(f"{mes.strftime('%b/%Y')}: 📈 {maior_compra[0].capitalize()} +R$ {maior_compra[1]:.2f} bi | 📉 {maior_venda[0].capitalize()} -R$ {abs(maior_venda[1]):.2f} bi")

    ultima_data = df['data'].max().strftime('%d/%m/%Y')
    return render_template("home.html", grafico=grafico, cards=cards, ultima_data=ultima_data, resumo_mensal=resumo_mensal)
