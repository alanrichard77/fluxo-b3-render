
from flask import Flask, render_template, request
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
from io import BytesIO
import base64
import os

plt.switch_backend('Agg')

app = Flask(__name__)

def gerar_grafico(start_date=None, end_date=None):
    url = "https://sistemaswebb3-listados.b3.com.br/fundsProxy/fundsCall/GetRegraNegociacaoFundos"
    fluxo = pd.read_csv("https://arquivos.b3.com.br/apinegocios/tickertape?CodTipoNegocio=19&Formato=csv")

    fluxo['Data'] = pd.to_datetime(fluxo['Data'])
    fluxo = fluxo.sort_values(by='Data')

    if start_date:
        fluxo = fluxo[fluxo['Data'] >= pd.to_datetime(start_date)]
    if end_date:
        fluxo = fluxo[fluxo['Data'] <= pd.to_datetime(end_date)]

    ibov = yf.download('^BVSP', start=fluxo['Data'].min(), end=fluxo['Data'].max()).reset_index()
    ibov['Date'] = pd.to_datetime(ibov['Date'])
    ibov = ibov[['Date', 'Close']].rename(columns={'Date': 'Data'})

    fluxo = fluxo.groupby(['Data', 'TipoInvestidor'])['Valor'].sum().unstack().fillna(0).cumsum()

    categorias = ['Estrangeiro', 'Institucional', 'Pessoa Física', 'Inst. Financeira', 'Outros']
    cores = ['royalblue', 'darkorange', 'limegreen', 'turquoise', 'orchid']

    fig, ax1 = plt.subplots(figsize=(12, 6), facecolor='none')
    for cat, cor in zip(categorias, cores):
        if cat in fluxo.columns:
            ax1.plot(fluxo.index, fluxo[cat] / 1e9, label=cat, color=cor)
    ax1.set_ylabel('Acumulado (R$ bilhões)', fontsize=10)
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:,.0f}'.replace(',', '.')))

    ax2 = ax1.twinx()
    ax2.plot(ibov['Data'], ibov['Close'], 'w--', linewidth=1.2, label='Ibovespa')
    ax2.set_ylabel('Ibovespa (pts)', fontsize=10)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'.replace(',', '.')))

    ax1.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    fig.autofmt_xdate()
    ax1.legend(loc='upper left')
    fig.text(0.5, 0.5, '@alan_richard', fontsize=18, color='gray', alpha=0.3, ha='center')

    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', transparent=True)
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()
    return img_base64

@app.route('/', methods=['GET'])
def index():
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    try:
        imagem = gerar_grafico(start_date, end_date)
    except Exception as e:
        imagem = None

    return render_template('index.html', imagem=imagem)

if __name__ == '__main__':
    app.run(debug=True)
