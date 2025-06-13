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

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        imagem, resumo = gerar_grafico()
        return render_template('home.html', imagem=imagem, resumo=resumo)
    return render_template('home.html', imagem=None, resumo={})

def gerar_grafico():
    start_date = '2025-01-01'
    end_date = datetime.today().strftime('%Y-%m-%d')
    ibov = yf.download('^BVSP', start=start_date, end=end_date)
    if isinstance(ibov.columns, pd.MultiIndex):
        ibov.columns = [col[0] for col in ibov.columns]
    ibov = ibov.reset_index()
    ibov = ibov.rename(columns={'Date': 'data', 'Close': 'ibovespa'})

    url = 'https://www.dadosdemercado.com.br/fluxo'
    tables = pd.read_html(url, decimal=',', thousands='.')
    df = tables[0]
    df.columns = [normalize_colname(col) for col in df.columns]
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df = df[(df['data'] >= pd.to_datetime(start_date)) & (df['data'] <= pd.to_datetime(end_date))].sort_values('data')
    colunas_fluxo = [c for c in df.columns if any(x in c for x in ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros'])]
    for col in colunas_fluxo:
        df[col+'_bi'] = df[col].apply(parse_valor)
        df[col+'_acum'] = df[col+'_bi'].cumsum()
    df_final = pd.merge(df, ibov, how='left', on='data')
    df_final['ibovespa'] = df_final['ibovespa'].fillna(method='ffill')

    labels_dict = {
        'estrangeiro_acum': "Estrangeiro",
        'institucional_acum': "Institucional",
        'pessoafisica_acum': "Pessoa Física",
        'instfinanceira_acum': "Inst. Financeira",
        'outros_acum': "Outros"
    }
    cores = ['#3b82f6', '#f97316', '#22c55e', '#06b6d4', '#a855f7']
    ordem_legenda = list(labels_dict.keys())

    fig, ax1 = plt.subplots(figsize=(16, 9))
    ax1.grid(True, linestyle=':', linewidth=0.5, alpha=0.7)
    for i, col in enumerate(ordem_legenda):
        if col in df_final.columns:
            ax1.plot(df_final['data'], df_final[col], linewidth=2.5, color=cores[i])
    ax1.set_ylabel('Acumulado (R$ bilhões)', fontsize=13)

    ax2 = ax1.twinx()
    ax2.plot(df_final['data'], df_final['ibovespa'], color='white', linestyle='--', linewidth=2, label='Ibovespa')
    ax2.set_ylabel('Ibovespa (pts)', fontsize=13)
    min_ibov = int(df_final['ibovespa'].min() // 2500 * 2500)
    max_ibov = int(df_final['ibovespa'].max() // 2500 * 2500 + 2500)
    ax2.set_ylim(min_ibov, max_ibov)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(2500))
    import matplotlib.ticker as ticker
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', '.')))

    datas = df_final['data'].tolist()
    xticks = [datas[i] for i in range(0, len(datas), 7) if i < len(datas)]
    ax1.set_xticks(xticks)
    ax1.set_xticklabels([d.strftime('%d/%m') for d in xticks], rotation=0)

    linhas = [ax1.plot([],[], color=cores[i], linewidth=2.5)[0] for i in range(len(ordem_legenda))]
    linhas += [ax2.plot([],[], color='white', linestyle='--', linewidth=2)[0]]
    legendas = list(labels_dict.values()) + ['Ibovespa']
    ax1.legend(linhas, legendas, loc='upper left', fontsize=12, frameon=True)

    plt.text(0.5, 0.5, '@alan_richard', fontsize=60, color='gray', alpha=0.07,
             ha='center', va='center', transform=plt.gcf().transFigure)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor='#111827')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')

    resumo = {}
    for col in ordem_legenda:
        resumo[col] = df_final[col].dropna().iloc[-1] if col in df_final.columns else 0

    return encoded, resumo
