import pandas as pd
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import datetime
import os
import io
from dash.dash_table import DataTable
from dash import dash_table
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- CONFIGURAÇÃO INICIAL E VARIÁVEIS DE AMBIENTE ---
load_dotenv()
URL_LOGIN = "https://uservoz.uservoz.com.br/painel/"
USERNAME = os.environ.get("SERVICE_USERNAME")
PASSWORD = os.environ.get("SERVICE_PASSWORD")

# Define as opções para o Chrome no ambiente Docker
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-setuid-sandbox")

def preparar_dados_para_dashboard(df_raw):
    """
    Prepara o DataFrame para o dashboard, garantindo que todas as colunas
    necessárias para os gráficos e métricas existam.
    """
    df_temp = df_raw.copy()
    
    # Normalização dos nomes das colunas
    df_temp.columns = df_temp.columns.str.strip().str.lower()
    
    # Tratamento de dados (sua lógica)
    if 'data' in df_temp.columns:
        df_temp['data'] = pd.to_datetime(df_temp['data'], errors='coerce')
        df_temp['somente data'] = df_temp['data'].dt.date
        df_temp['somente hora'] = df_temp['data'].dt.time
    
    if 'preço' in df_temp.columns:
        df_temp['preço'] = df_temp['preço'].astype(str).str.replace('"', '').str.replace(',', '.')
        df_temp['preço'] = pd.to_numeric(df_temp['preço'], errors='coerce')
    
    def converter_duracao_para_segundos(duracao_str):
        if isinstance(duracao_str, str) and duracao_str.count(':') == 2:
            try:
                h, m, s = map(int, duracao_str.split(':'))
                return h * 3600 + m * 60 + s
            except ValueError:
                return 0
        return 0
    
    if 'duração' in df_temp.columns:
        df_temp['duração (segundos)'] = df_temp['duração'].apply(converter_duracao_para_segundos)
    else:
        df_temp['duração (segundos)'] = 0
    
    if 'destino' in df_temp.columns:
        df_temp['destino'] = df_temp['destino'].astype(str)
        df_temp['ddd'] = df_temp['destino'].str.extract(r'^55(\d{2})')
    
    # CRIAÇÃO DA COLUNA 'faixa de tempo'
    df_temp['faixa de tempo'] = pd.NA
    ligacoes_longas = df_temp[df_temp['duração (segundos)'] > 300].copy()
    if not ligacoes_longas.empty:
        bins = [300, 360, 420, 480, 540, 600, float('inf')]
        labels = ['5-6 min', '6-7 min', '7-8 min', '8-9 min', '9-10 min', '10+ min']
        df_temp.loc[ligacoes_longas.index, 'faixa de tempo'] = pd.cut(
            ligacoes_longas['duração (segundos)'],
            bins=bins,
            labels=labels,
            right=False,
            include_lowest=True
        )

    return df_temp

# --- FUNÇÃO PRINCIPAL: AUTOMAÇÃO E EXTRAÇÃO ---
def executar_pipeline_completa():
    """Função que executa o processo de login, extração e tratamento."""
    print(f"[{datetime.datetime.now()}] --- INÍCIO DO PROCESSO DE AUTOMAÇÃO ---")
    if not USERNAME or not PASSWORD:
        print("Erro: Variáveis de ambiente USERNAME e PASSWORD não definidas.")
        return pd.DataFrame()
    
    hoje = datetime.date.today()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
    primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
    data_inicio_str = primeiro_dia_mes_anterior.strftime("%d/%m/%Y")
    data_fim_str = ultimo_dia_mes_anterior.strftime("%d/%m/%Y")
    print(f"[{datetime.datetime.now()}] Data calculada para pesquisa: DE {data_inicio_str} A {data_fim_str}")

    dados_coletados_globais = []
    nomes_colunas = []
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print(f"[{datetime.datetime.now()}] Navegador iniciado. Acessando URL de login...")
        driver.get(URL_LOGIN)
        
        print(f"[{datetime.datetime.now()}] Preenchendo credenciais e clicando em 'Login'...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="login"]'))
        ).send_keys(USERNAME)
        driver.find_element(By.XPATH, '//*[@id="senha"]').send_keys(PASSWORD)
        driver.find_element(By.XPATH, '//*[@id="bt-login"]/input').click()
        time.sleep(5)
        
        print(f"[{datetime.datetime.now()}] Navegando para o relatório...")
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="1"]'))
        ).click()
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="1_4"]'))
        ).click()
        
        print(f"[{datetime.datetime.now()}] Preenchendo os campos de data...")
        campo_inicio = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="ui-accordion-accordion-panel-0"]/table/tbody/tr[1]/td[4]/input[1]'))
        )
        campo_inicio.clear()
        campo_inicio.send_keys(data_inicio_str)
        campo_fim = driver.find_element(By.XPATH, '//*[@id="ui-accordion-accordion-panel-0"]/table/tbody/tr[1]/td[4]/input[2]')
        campo_fim.clear()
        campo_fim.send_keys(data_fim_str)
        
        driver.find_element(By.XPATH, '//*[@id="ui-accordion-accordion-panel-0"]/table/tbody/tr[8]/td/div/input').click()
        
        print(f"[{datetime.datetime.now()}] Iniciando a extração com paginação...")
        try:
            linha_cabecalho = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="site"]/table/tbody/tr/td/table/tbody/tr[1]'))
            )
            celulas_cabecalho = linha_cabecalho.find_elements(By.TAG_NAME, 'th')
            nomes_colunas = [celula.text for celula in celulas_cabecalho]
            print(f"[{datetime.datetime.now()}] Nomes das colunas extraídos: {nomes_colunas}")
        except Exception:
            print("Erro ao extrair nomes das colunas. Usando nomes genéricos.")

        pagina_atual = 1
        while True:
            print(f"[{datetime.datetime.now()}] Extraindo dados da página {pagina_atual}...")
            tabela_principal = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="site"]/table/tbody/tr/td/table/tbody'))
            )
            linhas = tabela_principal.find_elements(By.TAG_NAME, 'tr')
            for linha in linhas[1:]:
                celulas = linha.find_elements(By.TAG_NAME, 'td')
                dados_linha = [celula.text for celula in celulas]
                dados_coletados_globais.append(dados_linha)

            try:
                botao_proxima = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="site"]/div/table/tbody/tr/td/div/span[2]/a'))
                )
                driver.execute_script("arguments[0].click();", botao_proxima)
                print(f"[{datetime.datetime.now()}] Clicou em 'Próxima'.")
                time.sleep(5)
                pagina_atual += 1
            except Exception:
                print("Botão 'Próxima' não encontrado. Fim da paginação.")
                break

        if not dados_coletados_globais:
            raise Exception("Nenhum dado extraído da tabela.")

        if nomes_colunas:
            df = pd.DataFrame(dados_coletados_globais, columns=nomes_colunas)
        else:
            colunas = [f'Coluna {i+1}' for i in range(len(dados_coletados_globais[0]))]
            df = pd.DataFrame(dados_coletados_globais, columns=colunas)

        print(f"[{datetime.datetime.now()}] Dados brutos extraídos com sucesso. Tratando...")
        df_tratado = preparar_dados_para_dashboard(df)

        if not os.path.exists("dados"):
            os.makedirs("dados")
        caminho_final = "dados/dados_tratados_final.csv"
        df_tratado.to_csv(caminho_final, index=False)
        print(f"[{datetime.datetime.now()}] Dados tratados e salvos em {caminho_final}")
        
        return df_tratado
        
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Ocorreu um erro no processo: {e}")
        return pd.DataFrame()

    finally:
        if driver is not None:
            print("Fechando o navegador.")
            driver.quit()

# --- FUNÇÃO DE CARREGAMENTO INICIAL DOS DADOS ---
def carregar_dados_iniciais():
    """Tenta carregar os dados de um arquivo local, ou executa a pipeline completa se não encontrar."""
    caminho_arquivo_local = "dados/dados_tratados_final.csv"
    if os.path.exists(caminho_arquivo_local):
        print("Lendo dados do arquivo local...")
        df_bruto = pd.read_csv(caminho_arquivo_local)
        df = preparar_dados_para_dashboard(df_bruto)
        return df
    else:
        print("Arquivo de dados local não encontrado. Executando a pipeline pela primeira vez...")
        return executar_pipeline_completa()

# --- CARREGA OS DADOS E INICIA O APP ---
df = carregar_dados_iniciais()

# Verifica se o DataFrame está vazio antes de tentar criar os gráficos
if df.empty:
    print("Erro grave: Não foi possível carregar os dados. O dashboard não será iniciado.")
    app = dash.Dash(__name__, assets_folder='assets')
    app.layout = html.Div(style={'textAlign': 'center', 'marginTop': '50px'}, children=[
        html.H1("Não foi possível carregar os dados.", style={'color': 'red'}),
        html.P("Verifique as variáveis de ambiente e a conexão com o site de origem. A automação pode ter falhado.")
    ])
    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=8050, debug=False)
    exit()

# --- CORREÇÃO FINAL E ASSERTIVA ---
# Verifica se a coluna 'Destino' existe e a renomeia para 'destino' para garantir que ela exista
# Isso é uma segurança extra para o caso do arquivo CSV salvo localmente ter 'Destino' com maiúscula
if 'Destino' in df.columns:
    df.rename(columns={'Destino': 'destino'}, inplace=True)
# Faz o mesmo para as outras colunas usadas
if 'Região' in df.columns:
    df.rename(columns={'Região': 'região'}, inplace=True)
if 'Duração' in df.columns:
    df.rename(columns={'Duração': 'duração'}, inplace=True)
if 'Preço' in df.columns:
    df.rename(columns={'Preço': 'preço'}, inplace=True)


# --- CALCULA O MÊS DE REFERÊNCIA PARA O DASHBOARD ---
hoje = datetime.date.today()
primeiro_dia_mes_atual = hoje.replace(day=1)
ultimo_dia_mes_anterior = primeiro_dia_mes_atual - datetime.timedelta(days=1)
mes_de_referencia_str = ultimo_dia_mes_anterior.strftime("%m de %Y")

app = dash.Dash(__name__, assets_folder='assets')

# Usa as colunas com os nomes normalizados
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
ligacoes_longas_df = df.dropna(subset=['faixa de tempo']).groupby('faixa de tempo').agg(
    Contagem=('faixa de tempo', 'count'),
    Custo_Acumulado=('preço', 'sum')
).reset_index()
faixas_ordenadas = ['5-6 min', '6-7 min', '7-8 min', '8-9 min', '9-10 min', '10+ min']
ligacoes_longas_df['faixa de tempo'] = pd.Categorical(ligacoes_longas['faixa de tempo'], categories=faixas_ordenadas, ordered=True)
ligacoes_longas_df = ligacoes_longas_df.sort_values('faixa de tempo')
fig_longas = px.bar(ligacoes_longas_df, x='faixa de tempo', y='Contagem', 
                     title='Ligações com Mais de 5 Minutos', 
                     text='Contagem',
                     hover_data={'Custo_Acumulado': True})
fig_longas.update_traces(hovertemplate='<b>Faixa de Tempo:</b> %{x}<br><b>Ligações:</b> %{y}<br><b>Custo Acumulado:</b> R$ %{customdata[0]:.2f}<extra></extra>')

app.layout = html.Div(className='container', children=[
    dcc.Interval(
        id='interval-component',
        interval=24 * 60 * 60 * 1000,
        n_intervals=0
    ),
    # Novo contêiner para o cabeçalho
    html.Div(className='header-section', children=[
        html.Div(className='header', children=[
            html.Img(src=app.get_asset_url('logo.png'), className='logo'),
            html.Div(style={'display': 'flex', 'flex-direction': 'column', 'align-items': 'center', 'flex-grow': '1', 'text-align': 'center'}, children=[
                html.H1(children='Análise de Tráfego de Ligações', style={'color': '#333', 'margin-bottom': '0'}),
                html.H2(children=f'Mês de referência {mes_de_referencia_str}', style={'color': '#666', 'font-size': '1.2em', 'margin-top': '5px'})
            ])
        ])
    ]),
    
    # Novo contêiner para a seção de métricas
    html.Div(className='metrics-section', children=[
        html.Div(className='metric-container', children=[
            # Métrica: Total de Ligações
            html.Div(className='metric-box', title="Mostra o número total de ligações registradas no mês de referência.", children=[
                html.H3('Total de Ligações'),
                html.H2(id='total-ligacoes', children=f'{len(df)}')
            ]),
            # Métrica: Chamadas Ativas
            html.Div(className='metric-box', title="Mostra o número de ligações com duração maior que zero segundos.", children=[
                html.H3('Chamadas Ativas'),
                html.H2(id='chamadas-ativas', children=f'{len(df[df["duração (segundos)"] > 0])}')
            ]),
            # Métrica: Tempo Total de Chamadas
            html.Div(className='metric-box', title="Mostra a soma total da duração de todas as ligações, convertida para horas.", children=[
                html.H3('Tempo Total de Chamadas'),
                html.H2(id='tempo-total-chamadas', children=f'{df["duração (segundos)"].sum() / 3600:.2f} horas')
            ]),
            # Métrica: Custo Total Estimado
            html.Div(className='metric-box', title="Mostra a soma total dos custos estimados para todas as ligações registradas.", children=[
                html.H3('Custo Total Estimado'),
                html.H2(id='custo-total-estimado', children=f'R$ {df["preço"].sum():.2f}')
            ])
        ])
    ]),
    
    html.Div(className='graphs-row', children=[
        # Gráfico Top 10 Números
        html.Div(className='graph-box', title="Gráfico de barras mostrando os 10 números de destino mais chamados.", children=[
            dcc.Graph(id='grafico-top-numeros', figure=px.bar(top_numeros_df, x='destino', y='Contagem', title='Top 10 Números Mais Chamados')),
        ]),
        html.Div(className='graph-box', children=[
            html.H2('Top 10 DDDs Mais Chamados', className='section-title', style={'fontSize': '1.5em'}),
            dash_table.DataTable(
                id='tabela-ddds',
                columns=[{"name": i, "id": i} for i in top_ddds_df.columns],
                data=top_ddds_df.to_dict('records'),
                style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                style_cell={'textAlign': 'left', 'padding': '8px'},
            )
        ]),
    ]),
    
    html.Div(className='graphs-row', children=[
        # Gráfico Proporção de Ligações
        html.Div(className='graph-box', title="Gráfico de pizza mostrando a proporção de ligações por região.", children=[
            dcc.Graph(id='grafico-tipo-chamada', figure=px.pie(distribuicao_df, values='Contagem', names='Região', title='Proporção de Ligações', hole=.3)),
        ]),
        # Gráfico Ligações Longas
        html.Div(className='graph-box', title="Gráfico de barras mostrando a contagem e custo das ligações com mais de 5 minutos.", children=[
            dcc.Graph(id='grafico-longas', figure=fig_longas),
        ]),
    ]),
    
    html.H2('Detalhes das Ligações', className='section-title'),
    html.P('Clique em uma barra ou fatia de qualquer gráfico para ver os números e detalhes correspondentes.', className='section-subtitle'),

    html.Div(id='tabela-detalhes', className='graph-box', style={'margin': '20px auto', 'width': 'auto'}),
    
    html.Div(
        'Powered by Setor de Inovação – Inovando Hoje para Conquistar o Amanhã',
        className='footer',
        style={'textAlign': 'center'}
    )
])

@app.callback(
    [Output('total-ligacoes', 'children'),
     Output('chamadas-ativas', 'children'),
     Output('tempo-total-chamadas', 'children'),
     Output('custo-total-estimado', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_metrics_on_interval(n):
    if n is None or n < 1:
        raise PreventUpdate

    if datetime.datetime.now().day == 1:
        print(f"[{datetime.datetime.now()}] É dia 1! Iniciando a atualização de dados.")
        
        df_atualizado = executar_pipeline_completa()
        
        if df_atualizado.empty:
            raise PreventUpdate

        total_ligacoes = len(df_atualizado)
        chamadas_ativas = len(df_atualizado[df_atualizado["duração (segundos)"] > 0])
        tempo_total_horas = df_atualizado["duração (segundos)"].sum() / 3600
        custo_total = df_atualizado["preço"].sum()
        
        return f'{total_ligacoes}', f'{chamadas_ativas}', f'{tempo_total_horas:.2f} horas', f'R$ {custo_total:.2f}'
    else:
        print(f"[{datetime.datetime.now()}] Não é dia de atualização. Pulando a execução.")
        raise PreventUpdate

@app.callback(
    Output('tabela-detalhes', 'children'),
    [Input('grafico-top-numeros', 'clickData'),
     Input('grafico-longas', 'clickData'),
     Input('grafico-tipo-chamada', 'clickData')]
)
def update_table(click_top_numeros, click_longas, click_tipo):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate

    id_disparador = ctx.triggered[0]['prop_id'].split('.')[0]
    dados_filtrados = pd.DataFrame()
    colunas_para_tabela = ['Data', 'Serviço/Origem', 'Região', 'Destino', 'Duração', 'Preço']

    if id_disparador == 'grafico-top-numeros':
        numero_selecionado = click_top_numeros['points'][0]['x']
        dados_filtrados = df[df['destino'] == numero_selecionado]
    elif id_disparador == 'grafico-longas':
        faixa_selecionada = click_longas['points'][0]['x']
        dados_filtrados = df[df['faixa de tempo'] == faixa_selecionada]
        
    elif id_disparador == 'grafico-tipo-chamada':
        tipo_selecionado = click_tipo['points'][0]['label']
        if tipo_selecionado == 'Outros':
            dados_filtrados = df[~df['região'].isin(top_5_regioes_lista)]
        else:
            dados_filtrados = df[df['região'] == tipo_selecionado]
    
    if dados_filtrados.empty:
        return html.P("Nenhum dado encontrado para a seleção.", style={'textAlign': 'center'})

    # Adiciona a coluna 'Repetições' e ordena em todos os casos de filtro
    dados_filtrados['Repetições'] = dados_filtrados.groupby('destino')['destino'].transform('count')
    colunas_para_tabela.insert(4, 'Repetições')
    
    # Ordena o DataFrame, primeiro por repetições (maior para menor)
    # e depois por 'Destino' (menor para maior) para os casos de empate.
    dados_filtrados['destino_int'] = pd.to_numeric(dados_filtrados['destino'], errors='coerce')
    dados_filtrados.sort_values(by=['Repetições', 'destino_int'], ascending=[False, True], inplace=True)
    dados_filtrados.drop(columns=['destino_int'], inplace=True)


    dados_para_exibir = dados_filtrados[colunas_para_tabela].to_dict('records')

    return dash_table.DataTable(
        id='tabela-filtrada',
        columns=[{"name": i, "id": i} for i in colunas_para_tabela],
        data=dados_para_exibir,
        page_action="native",
        page_size=10,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '8px'},
        style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=False)