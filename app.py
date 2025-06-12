from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime
import io, base64, unicodedata
import matplotlib.ticker as mticker

app = Flask(__name__)

senha_sistema = "123456"

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
def login():
    if request.method == 'POST':
        senha = request.form['senha']
        if senha == senha_sistema:
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro=True)
    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        grafico = gerar_grafico()
        return render_template('home.html', imagem=grafico)
    return render_template('home.html', imagem=None)

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
    cores = ['#152955', '#e77730', '#174a28', '#48b5df', '#9936a3']
    ordem_legenda = list(labels_dict.keys())

    fig, ax1 = plt.subplots(figsize=(16, 9))
    ax1.grid(True, linestyle=':', linewidth=0.5, alpha=0.7)
    for i, col in enumerate(ordem_legenda):
        if col in df_final.columns:
            ax1.plot(df_final['data'], df_final[col], linewidth=2.5, label=labels_dict[col], color=cores[i])
    ax1.set_ylabel('Acumulado (R$ bilhões)', fontsize=13)
    ax2 = ax1.twinx()
    ax2.plot(df_final['data'], df_final['ibovespa'], color='#1c1c1c', linestyle='--', linewidth=2, label='Ibovespa')
    ax2.set_ylabel('Ibovespa (pts)', fontsize=13)
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    return encoded

if __name__ == '__main__':
    app.run()
