from flask import Flask, render_template, request
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import yfinance as yf
from datetime import datetime
import io, base64, unicodedata

app = Flask(__name__)

def normalize_colname(col):
    col = str(col)
    return ''.join(c for c in unicodedata.normalize('NFD', col)
                   if unicodedata.category(c) != 'Mn').lower().replace(' ', '').replace('.', '')

def parse_valor(valor):
    v = str(valor).replace('r$', '').replace(' ', '').replace('.', '').replace(',', '.').strip().lower()
    if 'mi' in v:
        try: return float(v.replace('mi', '')) / 1000
        except: return 0.0
    if 'bi' in v:
        try: return float(v.replace('bi', ''))
        except: return 0.0
    if v in ['', '-', 'nan']: return 0.0
    try: return float(v)
    except: return 0.0

def obter_dados_fluxo_e_ibov(start_date, end_date):
    ibov = yf.download('^BVSP', start=start_date, end=end_date).reset_index()
    ibov.columns = ['_'.join([str(x) for x in col if x]).strip() if isinstance(col, tuple) else str(col) for col in ibov.columns]
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
    df = df[(df['data'] >= pd.to_datetime(start_date)) & (df['data'] <= pd.to_datetime(end_date))].sort_values('data')

    colunas_fluxo = [c for c in df.columns if any(x in c for x in ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros'])]
    for col in colunas_fluxo:
        df[col+'_bi'] = df[col].apply(parse_valor)
        df[col+'_acum'] = df[col+'_bi'].cumsum()

    df_final = pd.merge(df, ibov, how='left', on='data')
    df_final['ibovespa'] = df_final['ibovespa'].fillna(method='ffill')
    return df_final

def gerar_grafico(df_final):
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    labels_dict = {
        'estrangeiro_acum': "Estrangeiro",
        'institucional_acum': "Institucional",
        'pessoafisica_acum': "Pessoa Física",
        'instfinanceira_acum': "Inst. Financeira",
        'outros_acum': "Outros"
    }
    ordem_legenda = list(labels_dict.keys())
    cores = ['#152955', '#e77730', '#174a28', '#48b5df', '#9936a3']

    plt.style.use('dark_background')
    fig, ax1 = plt.subplots(figsize=(16, 9))
    ax1.grid(True, linestyle=':', linewidth=0.5, alpha=0.7)

    for i, col in enumerate(ordem_legenda):
        if col in df_final.columns:
            ax1.plot(df_final['data'], df_final[col], linewidth=2.5, label=labels_dict[col], color=cores[i])

    ax1.set_ylabel('Acumulado (R$ bilhões)', fontsize=13)
    ax1.yaxis.set_major_locator(mticker.MultipleLocator(5))

    ax2 = ax1.twinx()
    ax2.plot(df_final['data'], df_final['ibovespa'], color='#cccccc', linestyle='--', linewidth=2, label='Ibovespa')
    ax2.set_ylabel('Ibovespa (pts)', fontsize=13)
    min_ibov = int(df_final['ibovespa'].min() // 2500 * 2500)
    max_ibov = int(df_final['ibovespa'].max() // 2500 * 2500 + 2500)
    ax2.set_ylim(min_ibov, max_ibov)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(2500))
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', '.')))

    datas = df_final['data'].tolist()
    tick_spacing = 7
    ax1.set_xticks(df_final['data'][::tick_spacing])
    ax1.set_xticklabels([d.strftime('%d/%m') for d in df_final['data'][::tick_spacing]])

    linhas = [ax1.plot([],[], color=cores[i], linewidth=2.5)[0] for i in range(len(ordem_legenda))]
    linhas += [ax2.plot([],[], color='#cccccc', linestyle='--', linewidth=2)[0]]
    legendas = list(labels_dict.values()) + ['Ibovespa']
    ax1.legend(linhas, legendas, loc='upper left', fontsize=12, frameon=True)

    ax1.text(0.5, 0.5, '@alan_richard', transform=ax1.transAxes, fontsize=50,
             color='gray', ha='center', va='center', alpha=0.12, weight='bold', rotation=15)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')
