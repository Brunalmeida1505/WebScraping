"""
Script para raspar dados de receitas do site circulo.com.br.

Funcionalidades:
- Extração inicial: Se o arquivo 'db/resultados/dados.csv' não existir,
uma extração completa é forçada para criar o banco de dados inicial.
- Extração incremental: Anexa novas receitas ao arquivo CSV existente.
- Cache de URLs: Salva as URLs em 'db/urls.txt' para controle.

Estratégias de Validação:
- Padrão: Atualiza se a contagem de receitas no site for maior que a do cache.
- --strict-sync: Atualiza se houver QUALQUER diferença entre o site e o cache.

Outras Flags:
- --update-urls-only: Apenas atualiza a lista de URLs e encerra.
- --force: Força uma nova extração de TODAS as receitas.
- --limit [N] / --range [INICIO] [FIM]: Para testes.
"""
import os
import time
import argparse
import pandas as pd
from urllib.parse import urlparse, parse_qs, urlencode
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# --- Constantes ---
URL_PRODUTO = "https://www.circulo.com.br/receitas?termo=&dificuldade=&categoria=&tecnica=&peca=&produto=2286"
DIRETORIO_DB = 'db'
ARQUIVO_URLS = os.path.join(DIRETORIO_DB, 'urls.txt')
DIRETORIO_RESULTADOS = os.path.join(DIRETORIO_DB, 'resultados')
ARQUIVO_SAIDA_CSV = os.path.join(DIRETORIO_RESULTADOS, 'dados.csv')
TEMPO_ESPERA_MAXIMO = 10
TEMPO_ESPERA_RECEITA = 1

# --- Seletores (XPATH, CSS, etc.) ---
XPATH_LINKS_RECEITAS = "//a[contains(@href, '/receitas/') and not(contains(@href, '?'))]"
XPATH_PAGINACAO_LINKS = "//ul[@class='pagination']//a[@class='page-link']"
TAG_TITULO = "h2"
CLASS_MATERIAIS = "receita-detalhe__conteudo"
CLASS_EXECUCAO = "receita-detalhe__execucao"


def configurar_driver() -> webdriver.Chrome:
    """Configura e inicializa o WebDriver do Chrome."""
    service = Service()
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")
    # options.add_argument("--log-level=3")
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def obter_urls_remotas(driver: webdriver.Chrome, url_inicial: str, mode: str = 'full'):
    """Coleta URLs das receitas.

    Modos:
    - 'estimate': não percorre página a página. Retorna um dict com a estimativa total de
      receitas baseada na contagem da primeira página e da última página encontrada na
      paginação, além dos conjuntos de links da primeira/última página e o número da última página.
    - 'full': percorre todas as páginas e retorna um conjunto com todas as URLs encontradas.
    """
    print("Iniciando busca de URLs remotas (modo: %s)..." % mode)
    driver.get(url_inicial)
    wait = WebDriverWait(driver, TEMPO_ESPERA_MAXIMO)

    # Descobrir número da última página
    last_page_num = 1
    try:
        page_links = wait.until(EC.presence_of_all_elements_located((By.XPATH, XPATH_PAGINACAO_LINKS)))
        page_numbers = [int(link.text) for link in page_links if link.text.isdigit()]
        if page_numbers:
            last_page_num = max(page_numbers)
        print(f"Total de páginas de receitas encontrado: {last_page_num}")
    except TimeoutException:
        print("Paginação não encontrada. Assumindo que há apenas 1 página.")

    parsed_url = urlparse(url_inicial)
    query_params = parse_qs(parsed_url.query)

    # Coletar links da primeira página
    first_links = set()
    try:
        links = wait.until(EC.presence_of_all_elements_located((By.XPATH, XPATH_LINKS_RECEITAS)))
        for link in links:
            if link.is_displayed():
                first_links.add(link.get_attribute("href"))
    except TimeoutException:
        print("Atenção: não foi possível coletar links da primeira página.")

    if mode == 'estimate':
        # Se só queremos estimativa, buscar também a última página e fazer a conta
        if last_page_num == 1:
            total = len(first_links)
            return {'total': total, 'first_links': first_links, 'last_links': first_links, 'last_page': 1}

        query_params['page'] = [str(last_page_num)]
        last_page_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{urlencode(query_params, doseq=True)}"
        print(f"Buscando apenas a última página ({last_page_num}) para estimativa...")
        driver.get(last_page_url)
        last_links = set()
        try:
            links = wait.until(EC.presence_of_all_elements_located((By.XPATH, XPATH_LINKS_RECEITAS)))
            for link in links:
                if link.is_displayed():
                    last_links.add(link.get_attribute("href"))
        except TimeoutException:
            print("Atenção: não foi possível coletar links da última página.")

        n_first = len(first_links)
        n_last = len(last_links)
        total = n_first * (last_page_num - 1) + n_last
        return {'total': total, 'first_links': first_links, 'last_links': last_links, 'last_page': last_page_num}

    # Modo 'full': iterar por todas as páginas (apenas quando realmente necessário)
    urls_encontradas = set()
    for page in range(1, last_page_num + 1):
        query_params['page'] = [str(page)]
        next_page_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{urlencode(query_params, doseq=True)}"
        print(f"Coletando da página {page}/{last_page_num}...")
        driver.get(next_page_url)
        try:
            links = wait.until(EC.presence_of_all_elements_located((By.XPATH, XPATH_LINKS_RECEITAS)))
            for link in links:
                if link.is_displayed():
                    urls_encontradas.add(link.get_attribute("href"))
        except TimeoutException:
            print(f"Aviso: Não foi possível carregar receitas da página {page}.")
    return urls_encontradas


def extrair_detalhes_receita(driver: webdriver.Chrome, url_receita: str) -> dict:
    """Extrai os detalhes de uma única página de receita."""
    driver.get(url_receita)
    wait = WebDriverWait(driver, TEMPO_ESPERA_MAXIMO)
    detalhes = {'url': url_receita}
    try:
        detalhes['titulo'] = wait.until(EC.presence_of_element_located((By.TAG_NAME, TAG_TITULO))).text
    except TimeoutException:
        detalhes['titulo'] = "Título não encontrado"
    try:
        detalhes['materiais'] = wait.until(EC.presence_of_element_located((By.CLASS_NAME, CLASS_MATERIAIS))).text
    except TimeoutException:
        detalhes['materiais'] = ""
    try:
        detalhes['receita'] = wait.until(EC.presence_of_element_located((By.CLASS_NAME, CLASS_EXECUCAO))).text
    except TimeoutException:
        detalhes['receita'] = ""
    time.sleep(TEMPO_ESPERA_RECEITA)
    return detalhes


def main():
    """Orquestra o processo de web scraping com lógicas de cache, force e filtros."""
    parser = argparse.ArgumentParser(description="Web scraper de receitas com funcionalidade de cache.", formatter_class=argparse.RawTextHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--force', action='store_true', help='Força a raspagem completa, ignorando o cache.')
    group.add_argument('--update-urls-only', action='store_true', help='Apenas busca e atualiza a lista de URLs, sem extrair os detalhes.')
    group.add_argument('--strict-sync', action='store_true', help='Sincroniza se houver qualquer diferença (add/remove) entre o cache e o site.')
    
    parser.add_argument('--limit', type=int, help='Limita o número de receitas a serem extraídas para testes.')
    parser.add_argument('--range', nargs=2, type=int, metavar=('INICIO', 'FIM'), help='Define um intervalo de receitas a serem extraídas.')
    args = parser.parse_args()

    # Validação de argumentos e criação de diretórios
    if (args.limit or args.range) and args.update_urls_only:
        print("Erro: --update-urls-only não pode ser usado com --limit ou --range.")
        return
    if args.limit and args.range:
        print("Erro: As flags --limit e --range não podem ser usadas ao mesmo tempo.")
        return
    os.makedirs(DIRETORIO_RESULTADOS, exist_ok=True)

    # Lógica de primeira execução: força a extração se o arquivo de dados não existe
    if not os.path.exists(ARQUIVO_SAIDA_CSV) and not args.force:
        print(f"Arquivo de dados '{ARQUIVO_SAIDA_CSV}' não encontrado. Ativando modo de primeira execução forçada.")
        args.force = True

    driver = configurar_driver()
    try:
        # 1. Obter estimativa de total de URLs e decidir se precisamos coletá-las completamente
        info = obter_urls_remotas(driver, URL_PRODUTO, mode='estimate')
        total_estimate = info.get('total', 0)
        print(f"Estimativa de receitas no site: {total_estimate}")

        urls_locais = set()
        if os.path.exists(ARQUIVO_URLS):
            with open(ARQUIVO_URLS, 'r', encoding='utf-8') as f:
                urls_locais = set(line.strip() for line in f if line.strip())

        urls_remotas = set()
        estimated_increase = False
        # Em modo strict precisamos da lista completa para comparar conjuntos
        if args.strict_sync:
            print("Modo strict: coletando todas as URLs para comparação detalhada...")
            urls_remotas = obter_urls_remotas(driver, URL_PRODUTO, mode='full')
        elif args.force:
            print("Forçando coleta completa de URLs (modo --force)...")
            urls_remotas = obter_urls_remotas(driver, URL_PRODUTO, mode='full')
        else:
            estimated_increase = total_estimate > len(urls_locais)
            if not estimated_increase:
                print("Nenhuma atualização necessária de acordo com a contagem. Evitando percorrer página a página.")
                urls_remotas = urls_locais
            else:
                print("Diferença de contagem detectada. Coletando todas as URLs...")
                urls_remotas = obter_urls_remotas(driver, URL_PRODUTO, mode='full')
                # Se a coleta completa não trouxe mais URLs (p.ex. por falhas), tentar novamente e usar links da estimativa como fallback
                if len(urls_remotas) <= len(urls_locais):
                    print("A coleta completa não retornou mais URLs que o cache local. Tentando nova coleta...")
                    urls_remotas = obter_urls_remotas(driver, URL_PRODUTO, mode='full')
                if len(urls_remotas) <= len(urls_locais):
                    # usar os links da primeira/última página coletados na estimativa para tentar ampliar o conjunto
                    print("Fallback: incorporando links da primeira/última página coletados na estimativa para ampliar os resultados.")
                    urls_remotas = set(urls_remotas) | set(info.get('first_links', set())) | set(info.get('last_links', set()))

        # 2. Decidir se uma atualização é necessária
        if args.strict_sync:
            needs_update = urls_locais != urls_remotas
            print("\nModo de sincronia estrita ativado.")
        else:
            # considerar também a estimativa inicial se indicou aumento
            needs_update = len(urls_remotas) > len(urls_locais) or estimated_increase
        
        if not needs_update and not args.force:
            print("\nNenhuma atualização necessária de acordo com a estratégia de verificação. Encerrando.")
            return

        # A partir daqui, uma atualização é necessária ou foi forçada
        if args.force:
             print("\nOpção --force ativada. Sincronização forçada.")
        elif args.strict_sync:
             print("\nDiferença detectada entre cache e site. Iniciando sincronização estrita.")
        else:
             print(f"\nNovas receitas detectadas ({len(urls_remotas)} remoto vs. {len(urls_locais)} local). Iniciando atualização.")

        # 3. Sincronizar o arquivo de cache de URLs
        if urls_remotas and (urls_locais != urls_remotas or estimated_increase):
            with open(ARQUIVO_URLS, 'w', encoding='utf-8') as f:
                for url in sorted(list(urls_remotas)): f.write(url + '\n')
            print(f"Arquivo de URLs '{ARQUIVO_URLS}' foi sincronizado com o site.")
        elif estimated_increase and not urls_remotas:
            print("Aviso: estimativa indicou mais receitas, mas não foi possível coletar URLs para atualizar o cache.")
        
        if args.update_urls_only:
            print("\n--update-urls-only ativado. Script encerrado.")
            return

        # 4. Determinar e filtrar URLs para extrair
        urls_alvo_base = sorted(list(urls_remotas - urls_locais)) if not args.force else sorted(list(urls_remotas))
        
        urls_para_extrair = urls_alvo_base
        if args.range:
            inicio, fim = args.range
            if inicio >= fim or inicio < 0:
                print(f"Erro: Intervalo inválido [{inicio}:{fim}]."); return
            print(f"Aplicando filtro de intervalo: dos índices {inicio} a {fim}.")
            urls_para_extrair = urls_alvo_base[inicio:fim]
        elif args.limit:
            if args.limit <= 0:
                print("Erro: --limit deve ser um número positivo."); return
            print(f"Aplicando filtro de limite: extraindo as primeiras {args.limit} receitas.")
            urls_para_extrair = urls_alvo_base[:args.limit]

        # 5. Iniciar extração
        if not urls_para_extrair:
            print("\nNenhuma receita nova para extrair.")
        else:
            print(f"\nIniciando extração de {len(urls_para_extrair)} receitas.")
            dados_novos = [extrair_detalhes_receita(driver, url) for url in urls_para_extrair]
            df_novos = pd.DataFrame(dados_novos, columns=['titulo', 'url', 'materiais', 'receita'])
            if args.force or not os.path.exists(ARQUIVO_SAIDA_CSV):
                df_novos.to_csv(ARQUIVO_SAIDA_CSV, sep=';', encoding='utf-8-sig', index=False)
                print(f"\nDados salvos em '{ARQUIVO_SAIDA_CSV}' (modo sobrescrita).")
            else:
                df_novos.to_csv(ARQUIVO_SAIDA_CSV, mode='a', sep=';', encoding='utf-8-sig', index=False, header=False)
                print(f"\nNovos dados adicionados em '{ARQUIVO_SAIDA_CSV}' (modo acréscimo).")
    finally:
        if driver:
            driver.quit()
            print("Driver finalizado.")

if __name__ == "__main__":
    main()
