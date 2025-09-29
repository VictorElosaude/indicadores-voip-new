import os
import time
import datetime
import pandas as pd
import dash
from dash import dcc, html, Input, Output
from dash import dash_table
from dash.exceptions import PreventUpdate
import plotly.express as px
from dotenv import load_dotenv

# (Opcional) automação via Selenium para coleta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===================== CONFIGURAÇÃO =====================
load_dotenv()
URL_LOGIN = "https://uservoz.uservoz.com.br/painel/"
USERNAME = os.environ.get("SERVICE_USERNAME")
PASSWORD = os.environ.get("SERVICE_PASSWORD")

PALETA = ['#20A490', '#32BCA2', '#148C8C', '#0A6F6F', '#214D73', '#1A3F5C']
FUNDO = "#dfe1e4"

# Chrome headless (compatível com Docker/Linux)
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-setuid-sandbox")

# ===================== PREPARO DE DADOS =====================
def preparar_dados_para_dashboard(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    df.columns = df.columns.str.strip().str.lower()

    mapeamento = {
        'date': 'data',
        'service / origin': 'serviço/origem',
        'region': 'região',
        'tech prefix': 'prefixo_tecnico',
        'destination': 'destino',
        'duration': 'duração',
        'price': 'preço'
    }
    df = df.rename(columns=mapeamento)

    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df['somente data'] = df['data'].dt.date
        df['somente hora'] = df['data'].dt.time

    if 'preço' in df.columns:
        df['preço'] = (
            df['preço'].astype(str)
            .str.replace('"', '')
            .str.replace(',', '.')
        )
        df['preço'] = pd.to_numeric(df['preço'], errors='coerce').fillna(0)

    def to_seconds(hms):
        if isinstance(hms, str) and hms.count(':') == 2:
            try:
                h, m, s = map(int, hms.split(':'))
                return h*3600 + m*60 + s
            except ValueError:
                return 0
        return 0

    if 'duração' in df.columns:
        df['duração (segundos)'] = df['duração'].apply(to_seconds)
    else:
        df['duração (segundos)'] = 0

    if 'destino' in df.columns:
        df['destino'] = df['destino'].astype(str)
        df['ddd'] = df['destino'].str.extract(r'^55(\d{2})')

    # Faixas > 5 min
    df['faixa de tempo'] = pd.NA
    longas = df[df['duração (segundos)'] > 300].copy()
    if not longas.empty:
        bins = [300, 360, 420, 480, 540, 600, float('inf')]
        labels = ['5-6 min', '6-7 min', '7-8 min', '8-9 min', '9-10 min', '10+ min']
        df.loc[longas.index, 'faixa de tempo'] = pd.cut(
            longas['duração (segundos)'],
            bins=bins, labels=labels, right=False, include_lowest=True
        )
    return df

# ===================== COLETA/PIPELINE (Opcional) =====================
def executar_pipeline_completa() -> pd.DataFrame:
    print(f"[{datetime.datetime.now()}] INÍCIO AUTOMAÇÃO")
    if not USERNAME or not PASSWORD:
        print("Erro: defina SERVICE_USERNAME e SERVICE_PASSWORD no ambiente.")
        return pd.DataFrame()

    hoje = datetime.date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
    primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
    data_inicio_str = primeiro_dia_mes_anterior.strftime("%d/%m/%Y")
    data_fim_str = ultimo_dia_mes_anterior.strftime("%d/%m/%Y")
    print(f"Período: {data_inicio_str} a {data_fim_str}")

    dados, nomes_colunas = [], []
    driver = None

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(URL_LOGIN)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="login"]'))).send_keys(USERNAME)
        driver.find_element(By.XPATH, '//*[@id="senha"]').send_keys(PASSWORD)
        driver.find_element(By.XPATH, '//*[@id="bt-login]/input').click()
        time.sleep(5)

        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="1"]'))).click()
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="1_4"]'))).click()

        campo_inicio = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="ui-accordion-accordion-panel-0"]/table/tbody/tr[1]/td[4]/input[1]'))
        )
        campo_inicio.clear(); campo_inicio.send_keys(data_inicio_str)
        campo_fim = driver.find_element(By.XPATH, '//*[@id="ui-accordion-accordion-panel-0"]/table/tbody/tr[1]/td[4]/input[2]')
        campo_fim.clear(); campo_fim.send_keys(data_fim_str)
        driver.find_element(By.XPATH, '//*[@id="ui-accordion-accordion-panel-0"]/table/tbody/tr[8]/td/div/input').click()

        # Cabeçalho
        try:
            head = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="site"]/table/tbody/tr/td/table/tbody/tr[1]'))
            )
            nomes_colunas = [th.text for th in head.find_elements(By.TAG_NAME, 'th')]
        except Exception:
            print("Cabeçalho não identificado; usando nomes genéricos.")

        # Paginado
        while True:
            tbody = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="site"]/table/tbody/tr/td/table/tbody'))
            )
            linhas = tbody.find_elements(By.TAG_NAME, 'tr')
            for ln in linhas[1:]:
                tds = ln.find_elements(By.TAG_NAME, 'td')
                dados.append([td.text for td in tds])

            # próxima página
            try:
                prox = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="site"]/div/table/tbody/tr/td/div/span[2]/a'))
                )
                driver.execute_script("arguments[0].click();", prox)
                time.sleep(5)
            except Exception:
                break

        if not dados:
            raise Exception("Tabela vazia.")

        if nomes_colunas:
            df = pd.DataFrame(dados, columns=nomes_colunas)
        else:
            cols = [f'Coluna {i+1}' for i in range(len(dados[0]))]
            df = pd.DataFrame(dados, columns=cols)

        df_tratado = preparar_dados_para_dashboard(df)

        os.makedirs("dados", exist_ok=True)
        caminho = "dados/dados_tratados_final.csv"
        df_tratado.to_csv(caminho, index=False)
        print(f"Dados salvos em {caminho}")
        return df_tratado

    except Exception as e:
        print(f"Erro na automação: {e}")
        return pd.DataFrame()
    finally:
        if driver is not None:
            driver.quit()

def carregar_dados_iniciais() -> pd.DataFrame:
    caminho = "dados/dados_tratados_final.csv"
    if os.path.exists(caminho):
        try:
            df_cache = pd.read_csv(caminho)
            df_ok = preparar_dados_para_dashboard(df_cache)
            if 'destino' in df_ok.columns:
                return df_ok
        except Exception as e:
            print(f"Falha lendo cache local: {e}")
    print("Executando coleta completa...")
    return executar_pipeline_completa()

# ===================== CARREGAMENTO =====================
df = carregar_dados_iniciais()

app = dash.Dash(__name__, assets_folder='assets')

if df.empty:
    app.layout = html.Div(style={'textAlign': 'center', 'marginTop': '50px'}, children=[
        html.H1("Não foi possível carregar os dados.", style={'color': 'red'}),
        html.P("Verifique as variáveis de ambiente e a conexão com o site de origem.")
    ])
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=8050, debug=False)
    #raise SystemExit

# Mês de referência (sempre mês anterior)
hoje = datetime.date.today()
primeiro_dia_mes_atual = hoje.replace(day=1)
ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
mes_de_referencia_str = ultimo_dia_mes_anterior.strftime("%m de %Y")

# ===================== AGREGAÇÕES =====================
top_numeros_df = df['destino'].value_counts().head(10).reset_index(name='Contagem')

contagem_regiao = df['região'].value_counts()
top_5_regioes_lista = contagem_regiao.head(5).index.tolist()
top_5_regioes = contagem_regiao.head(5)
outros_total = contagem_regiao.iloc[5:].sum()
distribuicao_df = top_5_regioes.to_frame(name='Contagem')
if outros_total > 0:
    distribuicao_df.loc['Outros'] = outros_total
distribuicao_df = distribuicao_df.reset_index()
distribuicao_df.columns = ['Região', 'Contagem']

top_ddds_df = df['ddd'].value_counts().head(10).reset_index(name='Contagem')
top_ddds_df.columns = ['ddd', 'Contagem']

ligacoes_longas_df = df.dropna(subset=['faixa de tempo']).groupby('faixa de tempo').agg(
    Contagem=('faixa de tempo', 'count'),
    Custo_Acumulado=('preço', 'sum')
).reset_index()
faixas_ordenadas = ['5-6 min','6-7 min','7-8 min','8-9 min','9-10 min','10+ min']
ligacoes_longas_df['faixa de tempo'] = pd.Categorical(ligacoes_longas_df['faixa de tempo'], categories=faixas_ordenadas, ordered=True)
ligacoes_longas_df = ligacoes_longas_df.sort_values('faixa de tempo')

# ===================== MÉTRICAS PRÉ-CALCULADAS =====================
total_lig = len(df)
cham_ativas = int((df["duração (segundos)"] > 0).sum()) if "duração (segundos)" in df.columns else 0
tempo_total_horas = (df["duração (segundos)"].sum() / 3600) if "duração (segundos)" in df.columns else 0.0
custo_total = float(df["preço"].sum()) if "preço" in df.columns else 0.0

# ===================== PLOTLY LAYOUT =====================
BASE_LAYOUT = dict(
    paper_bgcolor=FUNDO,
    plot_bgcolor=FUNDO,
    margin=dict(l=24, r=12, t=48, b=36),
    font=dict(family="Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif", size=14, color="#2c3e50"),
)

fig_top_numeros = px.bar(
    top_numeros_df, x='destino', y='Contagem',
    title='Top 10 Números Mais Chamados',
    color_discrete_sequence=PALETA
)
fig_top_numeros.update_layout(**BASE_LAYOUT, bargap=0.2, xaxis_title=None, yaxis_title=None)

fig_tipo_chamada = px.pie(
    distribuicao_df, values='Contagem', names='Região',
    title='Proporção de Ligações', hole=.35,
    color_discrete_sequence=PALETA
)
fig_tipo_chamada.update_layout(**BASE_LAYOUT, legend_title_text=None)

fig_longas = px.bar(
    ligacoes_longas_df, x='faixa de tempo', y='Contagem',
    title='Ligações com Mais de 5 Minutos',
    text='Contagem',
    hover_data={'Custo_Acumulado': True},
    color_discrete_sequence=PALETA
)
fig_longas.update_traces(
    hovertemplate='<b>Faixa:</b> %{x}<br><b>Ligações:</b> %{y}<br><b>Custo Acumulado:</b> R$ %{customdata[0]:.2f}<extra></extra>'
)
fig_longas.update_layout(**BASE_LAYOUT, xaxis_title=None, yaxis_title=None)

# ===================== LAYOUT (PROFUNDIDADE PERMANENTE) =====================
app.layout = html.Div(children=[
    dcc.Interval(id='interval-component', interval=24*60*60*1000, n_intervals=0),
    dcc.Location(id='url', refresh=False), # COMPONENTE ADICIONADO PARA ROLAGEM

    # Header de ponta a ponta
    html.Div(className='dark-header', children=[
        html.Img(src=app.get_asset_url('logo.png')),
        html.Div(html.H1('Dashboard Voip - Elosaúde'))
    ]),

    html.Div(className='container', children=[
        # Bloco principal de Análise de Tráfego de Ligações
        html.Div(className='main-section neo focusable', tabIndex=0, children=[
            html.Div(className='header', children=[
                html.H1('Análise de Tráfego de Ligações', style={'color':'#333','marginBottom':'2px'}),
                html.Div(className='badge neo', children=[
                    "Mês de referência ", html.Strong(mes_de_referencia_str)
                ])
            ]),
        ]),

        # Bloco de Resumo Geral
        html.Div(className='main-section neo focusable', tabIndex=0, children=[
            html.H2('Resumo Geral', className='section-title'),
            html.Div(className='metric-container', children=[
                html.Div(className='metric-box neo-inset', title="Total de ligações no mês.", children=[
                    html.H3('Total de Ligações'),
                    html.H2(id='total-ligacoes', children=str(total_lig))
                ]),
                html.Div(className='metric-box neo-inset', title="Ligações com duração > 0s.", children=[
                    html.H3('Chamadas Ativas'),
                    html.H2(id='chamadas-ativas', children=str(cham_ativas))
                ]),
                html.Div(className='metric-box neo-inset', title="Soma de duração convertida em horas.", children=[
                    html.H3('Tempo Total de Chamadas'),
                    html.H2(id='tempo-total-chamadas', children=f'{tempo_total_horas:.2f} horas')
                ]),
                html.Div(className='metric-box neo-inset', title="Soma de custos estimados.", children=[
                    html.H3('Custo Total Estimado'),
                    html.H2(id='custo-total-estimado', children=f'R$ {custo_total:.2f}')
                ]),
            ]),
        ]),

        # Bloco de Gráficos de Distribuição
        html.Div(className='main-section neo focusable', tabIndex=0, children=[
            html.H2('Gráficos de Distribuição', className='section-title'),
            html.Div(className='graphs-row', children=[
                html.Div(className='graph-box neo-inset focusable', tabIndex=0, title="Top 10 destinos mais chamados.", children=[
                    dcc.Graph(id='grafico-top-numeros', figure=fig_top_numeros),
                ]),
                html.Div(className='graph-box neo-inset focusable', tabIndex=0, children=[
                    html.H2('Top 10 DDDs Mais Chamados', className='section-title', style={'fontSize':'1.3rem'}),
                    dash_table.DataTable(
                        id='tabela-ddds',
                        columns=[{"name": i, "id": i} for i in top_ddds_df.columns],
                        data=top_ddds_df.to_dict('records'),
                        page_action="native",
                        page_size=10,
                        style_table={'overflowX':'auto'},
                        style_cell={'textAlign': 'left', 'padding': '8px'},
                        style_header={'backgroundColor': 'rgb(230,230,230)', 'fontWeight': 'bold'},
                    )
                ]),
            ]),
            html.Div(className='graphs-row', children=[
                html.Div(className='graph-box neo-inset focusable', tabIndex=0, title="Proporção de ligações por região.", children=[
                    dcc.Graph(id='grafico-tipo-chamada', figure=fig_tipo_chamada),
                ]),
                html.Div(className='graph-box neo-inset focusable', tabIndex=0, title="Distribuição de chamadas com duração > 5 minutos.", children=[
                    dcc.Graph(id='grafico-longas', figure=fig_longas),
                ]),
            ]),
        ]),

        # Bloco de Detalhes das Ligações
        html.Div(className='main-section neo focusable', tabIndex=0, children=[
            html.H2('Detalhes das Ligações', className='section-title'),
            html.P('Clique em qualquer gráfico para filtrar os registros correspondentes.', className='section-subtitle'),
            # Adicionado ID para poder rolar até aqui
            html.Div(id='tabela-detalhes', className='graph-box neo-inset', style={'margin':'20px auto', 'width':'auto'}),
        ]),

    ]),
    # Novo Footer da aplicação (corrigido)
    html.Div(className='app-footer', children=[
        html.P('© 2025 Dashboard Voip - Elosaúde.', style={'margin':'0'}),
        html.P('Powered by Setor de Inovação – Inovando Hoje para Conquistar o Amanhã.', style={'margin':'0'})
    ])
])

# ===================== CALLBACKS =====================
@app.callback(
    [Output('total-ligacoes','children'),
     Output('chamadas-ativas','children'),
     Output('tempo-total-chamadas','children'),
     Output('custo-total-estimado','children')],
    [Input('interval-component','n_intervals')]
)
def update_metrics_on_interval(n):
    if n is None or n < 1:
        raise PreventUpdate
    # Atualiza no 1º dia do mês
    if datetime.datetime.now().day == 1:
        df_atualizado = executar_pipeline_completa()
        if df_atualizado.empty:
            raise PreventUpdate
        total = len(df_atualizado)
        ativas = (df_atualizado["duração (segundos)"] > 0).sum()
        horas = df_atualizado["duração (segundos)"].sum()/3600
        custo = df_atualizado["preço"].sum()
        return f'{total}', f'{ativas}', f'{horas:.2f} horas', f'R$ {custo:.2f}'
    raise PreventUpdate

# CALLBACK MODIFICADO PARA ROLAGEM
@app.callback(
    [Output('tabela-detalhes','children'),
     Output('url', 'hash')], # SEGUNDA SAÍDA ADICIONADA PARA ROLAGEM
    [Input('grafico-top-numeros','clickData'),
     Input('grafico-longas','clickData'),
     Input('grafico-tipo-chamada','clickData')]
)
def update_table(click_top, click_longas, click_tipo):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate

    who = ctx.triggered[0]['prop_id'].split('.')[0]
    cols = ['data','serviço/origem','região','destino','duração','preço']
    dados_filtrados = pd.DataFrame()

    if who == 'grafico-top-numeros' and click_top:
        numero = click_top['points'][0]['x']
        dados_filtrados = df[df['destino'] == numero]
    elif who == 'grafico-longas' and click_longas:
        faixa = click_longas['points'][0]['x']
        dados_filtrados = df[df['faixa de tempo'] == faixa]
    elif who == 'grafico-tipo-chamada' and click_tipo:
        tipo = click_tipo['points'][0]['label']
        if tipo == 'Outros':
            dados_filtrados = df[~df['região'].isin(top_5_regioes_lista)]
        else:
            dados_filtrados = df[df['região'] == tipo]

    if dados_filtrados.empty:
        return html.P("Nenhum dado encontrado para a seleção.", style={'textAlign':'center'}), '#tabela-detalhes'

    dados_filtrados = dados_filtrados.copy()
    dados_filtrados['Repetições'] = dados_filtrados.groupby('destino')['destino'].transform('count')
    cols.insert(4, 'Repetições')
    dados_filtrados['destino_int'] = pd.to_numeric(dados_filtrados['destino'], errors='coerce')
    dados_filtrados.sort_values(by=['Repetições','destino_int'], ascending=[False,True], inplace=True)
    dados_filtrados.drop(columns=['destino_int'], inplace=True)

    tabela_filtrada = dash_table.DataTable(
        id='tabela-filtrada',
        columns=[
            {"name":"Data","id":"data"},
            {"name":"Serviço/Origem","id":"serviço/origem"},
            {"name":"Região","id":"região"},
            {"name":"Destino","id":"destino"},
            {"name":"Repetições","id":"Repetições"},
            {"name":"Duração","id":"duração"},
            {"name":"Preço","id":"preço"},
        ],
        data=dados_filtrados[cols].to_dict('records'),
        page_action="native", page_size=10,
        style_table={'overflowX':'auto'},
        style_cell={'textAlign':'left','padding':'8px','fontSize': '16px'},
        
        style_header={'backgroundColor':'rgb(230,230,230)','fontWeight':'bold','fontSize': '16px'}
    )
    return tabela_filtrada, '#tabela-detalhes'

# ===================== RUN =====================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=False)
