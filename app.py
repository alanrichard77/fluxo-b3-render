
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
    return ''.join(c for c in unicodedata.normalize('NFD', col) if unicodedata.category(c) != 'Mn').lower().replace(' ', '').replace('.', '')

def parse_valor(valor):
    v = str(valor).replace('r$', '').replace(' ', '').replace('.', '').replace(',', '.').strip().lower()
    if 'mi' in v: return float(v.replace('mi', '')) / 1000
    if 'bi' in v: return float(v.replace('bi', ''))
    if v in ['', '-', 'nan']: return 0.0
    return float(v)

def gerar_grafico(start_date=None, end_date=None):
    start_date = start_date or '2025-01-01'
    end_date = end_date or datetime.today().strftime('%Y-%m-%d')

    ibov = yf.download('^BVSP', start=start_date, end=end_date).reset_index()
    ibov = ibov.rename(columns={'Date': 'data', 'Close': 'ibovespa'})

    url = 'https://www.dadosdemercado.com.br/fluxo'
    tables = pd.read_html(url, decimal=',', thousands='.')
    df = tables[0]
    df.columns = [normalize_colname(col) for col in df.columns]
    df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    df = df[(df['data'] >= pd.to_datetime(start_date)) & (df['data'] <= pd.to_datetime(end_date))].sort_values('data')

    colunas_fluxo = [c for c in df.columns if any(x in c for x in ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros'])]
    for col in colunas_fluxo:
        df[col + '_bi'] = df[col].apply(parse_valor)
        df[col + '_acum'] = df[col + '_bi'].cumsum()

    df_final = pd.merge(df, ibov, how='left', on='data')
    df_final['ibovespa'] = df_final['ibovespa'].fillna(method='ffill')

    labels_dict = {
        'estrangeiro_acum': "Estrangeiro",
        'institucional_acum': "Institucional",
        'pessoafisica_acum': "Pessoa Física",
        'instfinanceira_acum': "Inst. Financeira",
        'outros_acum': "Outros"
    }
    cores = ['#3b82f6', '#f97316', '#22c55e', '#ec4899', '#a855f7']
    ordem_legenda = list(labels_dict.keys())

    fig, ax1 = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#0f172a')
    ax1.set_facecolor('#1e293b')
    ax1.grid(True, linestyle=':', linewidth=0.5, alpha=0.4)

    for i, col in enumerate(ordem_legenda):
        if col in df_final.columns:
            ax1.plot(df_final['data'], df_final[col], linewidth=2.5, label=labels_dict[col], color=cores[i])

    ax2 = ax1.twinx()
    ax2.plot(df_final['data'], df_final['ibovespa'], linestyle='dotted', linewidth=2.5, label='Ibovespa', color='white')
    ax2.set_ylabel('Ibovespa (pts)', color='white')
    ax2.tick_params(axis='y', labelcolor='white')
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))

    ax1.set_ylabel('Acumulado (R$ bilhões)', color='white')
    ax1.tick_params(axis='y', labelcolor='white')
    ax1.xaxis.set_major_locator(plt.MaxNLocator(10))
    ax1.legend(loc='upper left', facecolor='#1e293b', labelcolor='white')

    plt.xticks(color='white')
    plt.yticks(color='white')
    plt.text(0.5, 0.5, '@alan_richard', fontsize=24, alpha=0.06, color='white', transform=plt.gca().transAxes, ha='center')

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buffer.seek(0)
    imagem = base64.b64encode(buffer.read()).decode('utf-8')
    buffer.close()

    resumo = {}
    for k, v in labels_dict.items():
        saldo = df_final[k].iloc[-1] if k in df_final else 0
        resumo[v] = saldo

    resumo_formatado = {}
    for k, v in resumo.items():
        tipo = 'Entrada líquida' if v >= 0 else 'Saída líquida'
        resumo_formatado[k] = {
            'valor': f"R$ {abs(v):,.1f}Bi".replace('.', ','),
            'tipo': tipo
        }

    data_final = df_final['data'].max().strftime('%d/%m/%Y') if not df_final.empty else '-'
    return imagem, resumo_formatado, data_final

@app.route('/', methods=['GET', 'POST'])
def home():
    imagem = None
    resumo = {}
    last_date = ''
    if request.method == 'POST':
        start = request.form.get('start_date')
        end = request.form.get('end_date')
        imagem, resumo, last_date = gerar_grafico(start, end)
    return render_template('home.html', imagem=imagem, resumo=resumo, last_date=last_date)
