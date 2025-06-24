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
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        imagem, resumo, last_date, resumo_mensal = gerar_grafico(data_inicio, data_fim)
        return render_template('home.html', imagem=imagem, resumo=resumo, last_date=last_date, resumo_mensal=resumo_mensal)

    if request.method == 'POST':
        imagem, resumo, last_date = gerar_grafico()
        return render_template('home.html', imagem=imagem, resumo=resumo, last_date=last_date, resumo_mensal=resumo_mensal)
    return render_template('home.html', imagem=None, resumo={}, last_date=None, resumo_mensal={})


def gerar_grafico(data_inicio=None, data_fim=None):
    start_date = data_inicio if data_inicio else '2025-01-01'
    end_date = data_fim if data_fim else datetime.today().strftime('%Y-%m-%d')
    ibov = yf.download('^BVSP', start=start_date, end=end_date)
    if isinstance(ibov.columns, pd.MultiIndex):
        ibov.columns = [col[0] for col in ibov.columns]
    ibov = ibov.reset_index()
    ibov = ibov.rename(columns={'Date': 'data', 'Close': 'ibovespa'})

    start_date = '2025-01-01'
    end_date = datetime.today().strftime('%Y-%m-%d')
    ibov = yf.download('^BVSP', start=start_date, end=end_date)
    if isinstance(ibov.columns, pd.MultiIndex):
        ibov.columns = [col[0] for col in ibov.columns]
    ibov = ibov.reset_index()
    ibov = ibov.rename(columns={'Date': 'data', 'Close': 'ibovespa'})

    # Web scraping fluxo
    url = 'https://www.dadosdemercado.com.br/fluxo'
    tables = pd.read_html(url, decimal=',', thousands='.')
    df = tables[0]
    df.columns = [normalize_colname(col) for col in df.columns]
    df['data'] = pd.to_datetime(df['data'], dayfirst=True)
    df = df[(df['data'] >= pd.to_datetime(start_date)) & (df['data'] <= pd.to_datetime(end_date))].sort_values('data')

    colunas_fluxo = ['estrangeiro', 'institucional', 'pessoafisica', 'instfinanceira', 'outros']
    for col in colunas_fluxo:
        df[f'{col}_bi'] = df[col].apply(parse_valor)

    resumo = {}
    for col in colunas_fluxo:
        saldo = df[f'{col}_bi'].sum()
        tipo = 'Entrada líquida' if saldo >= 0 else 'Saída líquida'
        resumo[col] = {'saldo': saldo, 'tipo': tipo}

    last_date = df['data'].max().strftime('%d/%m/%Y')

    # Resumo mensal
    df['ano_mes'] = df['data'].dt.to_period('M')
    resumo_mensal = {}
    for mes, grupo in df.groupby('ano_mes'):
        totais = {col: grupo[f'{col}_bi'].sum() for col in colunas_fluxo}
        maior_comprador = max(totais.items(), key=lambda x: x[1])
        maior_vendedor = min(totais.items(), key=lambda x: x[1])
        resumo_mensal[str(mes)] = {
            'maior_compra': {'categoria': maior_comprador[0], 'valor': maior_comprador[1]},
            'maior_venda': {'categoria': maior_vendedor[0], 'valor': maior_vendedor[1]}
        }

    # Geração do gráfico (mantém o código já existente)
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
    cores = ['#3b82f6', '#f97316', '#22c55e', '#ec4899', '#a855f7']
    ordem_legenda = list(labels_dict.keys())

    fig, ax1 = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor('#0f172a')
    ax1.set_facecolor('#1e293b')
    ax1.grid(True, linestyle=':', linewidth=0.5, alpha=0.4)

    for i, col in enumerate(ordem_legenda):
        if col in df_final.columns:
            ax1.plot(df_final['data'], df_final[col], linewidth=2.5, label=labels_dict[col], color=cores[i])

    ax1.set_ylabel('Acumulado (R$ bilhões)', fontsize=13, color='white')
    ax1.tick_params(colors='white')

    ax2 = ax1.twinx()
    ax2.plot(df_final['data'], df_final['ibovespa'], color='white', linestyle='--', linewidth=2, label='Ibovespa')
    ax2.set_ylabel('Ibovespa (pts)', fontsize=13, color='white')
    ax2.tick_params(colors='white')
    min_ibov = int(df_final['ibovespa'].min() // 2500 * 2500)
    max_ibov = int(df_final['ibovespa'].max() // 2500 * 2500 + 2500)
    ax2.set_ylim(min_ibov, max_ibov)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(2500))
    import matplotlib.ticker as ticker
    ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', '.')))

    datas = df_final['data'].tolist()
    xticks = [datas[i] for i in range(0, len(datas), 7) if i < len(datas)]
    ax1.set_xticks(xticks)
    ax1.set_xticklabels([d.strftime('%d/%m') for d in xticks], color='white', rotation=0)

    linhas = ax1.get_lines() + ax2.get_lines()
    labels = [l.get_label() for l in linhas]
    ax1.legend(linhas, labels, loc='upper left', fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')

    plt.text(0.5, 0.5, '@alan_richard', fontsize=60, color='gray', alpha=0.08,
             ha='center', va='center', transform=plt.gcf().transFigure)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')

    resumo = {}
    for col in ordem_legenda:
        resumo[col] = df_final[col].dropna().iloc[-1] if col in df_final.columns else 0

    last_date = df_final['data'].dropna().iloc[-1].strftime('%d/%m/%Y')
    return encoded, resumo, last_date
