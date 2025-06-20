
from flask import Flask, render_template, request
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime
import io, base64, unicodedata
import matplotlib.ticker as mticker

app = Flask(__name__)

def normalize_colname(col):
    col = str(col)
    return ''.join(c for c in unicodedata.normalize('NFD', col)
                   if unicodedata.category(c) != 'Mn').lower().replace(' ', '').replace('.', '')

def parse_valor(valor):
    v = str(valor).replace('r$', '').replace(' ', '').replace('.', '').replace(',', '.').strip().lower()
    if 'mi' in v: return float(v.replace('mi', '')) / 1000
    if 'bi' in v: return float(v.replace('bi', ''))
    if v in ['', '-', 'nan']: return 0.0
    return float(v)

def obter_dados_fluxo_e_ibov(start_date, end_date):
    ibov = yf.download('^BVSP', start=start_date, end=end_date).reset_index()
    col_fechamento = [c for c in ibov.columns if 'close' in c.lower()][0]
    col_data = [c for c in ibov.columns if 'date' in c.lower()][0]
    ibov = ibov.rename(columns={col_fechamento: 'ibovespa', col_data: 'data'})
    ibov['data'] = pd.to_datetime(ibov['data'])
    ibov = ibov[['data', 'ibovespa']]

    url = 'https://www.dadosdemercado.com.br/fluxo'
    tables = pd.read_html(url, decimal=',', thousands='.')
    df = tables[0]
    df.columns = [normalize_colname(col) for col in df.columns]
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df = df.dropna(subset=['data'])
    df = df.sort_values('data')

    colunas_fluxo = [c for c in df.columns if any(x in c for x in ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros'])]
    for col in colunas_fluxo:
        df[col+'_bi'] = df[col].apply(parse_valor)
        df[col+'_acum'] = df[col+'_bi'].cumsum()

    df_final = pd.merge(df, ibov, how='left', on='data')
    df_final['ibovespa'] = df_final['ibovespa'].fillna(method='ffill')
    return df_final

def gerar_grafico(df):
    labels_dict = {
        'estrangeiro_acum': "Estrangeiro",
        'institucional_acum': "Institucional",
        'pessoafisica_acum': "Pessoa Física",
        'instfinanceira_acum': "Inst. Financeira",
        'outros_acum': "Outros"
    }
    cores = ['#60a5fa', '#fb923c', '#4ade80', '#f472b6', '#c084fc']

    plt.style.use('dark_background')
    fig, ax1 = plt.subplots(figsize=(16, 9))
    ax1.grid(True, linestyle=':', linewidth=0.5, alpha=0.7)

    for i, col in enumerate(labels_dict):
        if col in df.columns:
            ax1.plot(df['data'], df[col], label=labels_dict[col], linewidth=2.5, color=cores[i])

    ax2 = ax1.twinx()
    ax2.plot(df['data'], df['ibovespa'], '--', color='gray', linewidth=2, label='Ibovespa')
    ax1.set_ylabel('R$ bilhões')
    ax2.set_ylabel('Ibovespa (pts)')
    ax2.set_ylim(df['ibovespa'].min() // 2500 * 2500, df['ibovespa'].max() // 2500 * 2500 + 2500)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(2500))
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', '.')))

    ax1.legend(loc='upper left')
    ax2.legend(loc='upper right')
    ax1.set_xticks(df['data'][::7])
    ax1.set_xticklabels([d.strftime('%d/%m') for d in df['data'][::7]])

    ax1.text(0.5, 0.5, '@alan_richard', transform=ax1.transAxes, fontsize=50,
             color='gray', ha='center', va='center', alpha=0.12, weight='bold', rotation=15)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def calcular_resumo(df):
    resumo = {}
    for col in ['estrangeiro_acum', 'institucional_acum', 'pessoafisica_acum', 'instfinanceira_acum', 'outros_acum']:
        resumo[col] = df[col].iloc[-1] if col in df.columns else 0.0
    return resumo

def resumo_mensal(df):
    df['ano_mes'] = df['data'].dt.to_period('M')
    categorias = ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros']
    resumo = []

    for mes, grupo in df.groupby('ano_mes'):
        saldos = {cat: grupo[cat+'_bi'].sum() for cat in categorias}
        maior_compra = max(saldos.items(), key=lambda x: x[1])
        maior_venda = min(saldos.items(), key=lambda x: x[1])
        resumo.append(f"{mes.strftime('%b/%Y')}: 📈 {maior_compra[0].capitalize()} +R$ {maior_compra[1]:.2f} bi | 📉 {maior_venda[0].capitalize()} -R$ {abs(maior_venda[1]):.2f} bi")
    return resumo

@app.route("/", methods=["GET", "POST"])
def home():
    start_date = request.form.get("data_inicio") if request.method == "POST" else "2025-01-01"
    end_date = request.form.get("data_fim") if request.method == "POST" else datetime.today().strftime("%Y-%m-%d")

    df = obter_dados_fluxo_e_ibov(start_date, end_date)
    imagem = gerar_grafico(df)
    resumo = calcular_resumo(df)
    ult_data = df['data'].max().strftime('%d/%m/%Y')
    resumo_mensal_str = resumo_mensal(df)

    return render_template("home.html", imagem=imagem, resumo=resumo, last_date=ult_data, resumo_mensal=resumo_mensal_str)
