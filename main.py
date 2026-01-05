"""
Script para raspar dados de receitas do site circulo.com.br.

Funcionalidades:
- Extração inicial: Se o arquivo 'db/resultados/dados.csv' não existir,
uma extração completa é forçada para criar o banco de dados inicial.
- Extração incremental: Anexa novas receitas ao arquivo CSV existente.
- Cache de URLs: Salva as URLs em 'db/urls.txt' para controle.
- Verificação rápida: Compara quantidade estimada (páginas × itens) antes de coletar URLs.

Estratégias de Validação:
- Padrão: Atualiza se a contagem estimada de receitas for diferente da do cache.
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
TEMPO_ESPERA_MAXIMO = 8  # Reduzido de 10 para 8
TEMPO_ESPERA_RECEITA = 0.5  # Reduzido de 1 para 0.5

# --- Seletores (XPATH, CSS, etc.) ---
# Lista de seletores para tentar (do mais específico ao mais genérico)
SELETORES_LINKS_RECEITAS = [
    "//div[contains(@class, 'card-receita')]//a[contains(@href, '/receitas/')]",
    "//article[contains(@class, 'receita')]//a[contains(@href, '/receitas/')]",
    "//a[contains(@class, 'receita')]",
    "//a[contains(@href, '/receitas/')][@title]",
    "//a[contains(@href, '/receitas/') and not(contains(@href, '?'))]"
]
XPATH_PAGINACAO_LINKS = "//ul[@class='pagination']//a[@class='page-link']"
TAG_TITULO = "h2"
CLASS_MATERIAIS = "receita-detalhe__conteudo"
CLASS_EXECUCAO = "receita-detalhe__execucao"


def configurar_driver(headless: bool = True) -> webdriver.Chrome:
    """Configura e inicializa o WebDriver do Chrome."""
    service = Service()
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.page_load_strategy = 'eager'  # Não espera todos os recursos carregarem
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def obter_links_pagina(driver: webdriver.Chrome, wait: WebDriverWait) -> set:
    """Tenta diferentes seletores para coletar links de receitas da página atual."""
    urls_encontradas = set()
    
    for i, seletor in enumerate(SELETORES_LINKS_RECEITAS):
        try:
            # Timeout mais curto para seletores que já sabemos que não funcionam
            timeout_local = 3 if i > 0 else TEMPO_ESPERA_MAXIMO
            wait_local = WebDriverWait(driver, timeout_local)
            
            links = wait_local.until(EC.presence_of_all_elements_located((By.XPATH, seletor)))
            for link in links:
                try:
                    if link.is_displayed():
                        href = link.get_attribute("href")
                        if href and '/receitas/' in href and '?' not in href:
                            urls_encontradas.add(href)
                except:
                    continue
            
            if urls_encontradas:
                if i == 0:  # Só mostra na primeira vez que funciona
                    print(f"  ✓ Seletor funcionou: {seletor[:60]}...")
                print(f"  ✓ {len(urls_encontradas)} URLs únicas encontradas")
                return urls_encontradas
        except TimeoutException:
            continue
    
    if not urls_encontradas:
        print("  ✗ Nenhum seletor conseguiu encontrar links de receitas")
    
    return urls_encontradas


def estimar_quantidade_receitas(driver: webdriver.Chrome, url_inicial: str) -> dict:
    """Estima a quantidade total de receitas sem percorrer todas as páginas.
    
    Retorna um dicionário com:
    - total_estimado: número estimado de receitas ÚNICAS
    - num_paginas: número total de páginas
    - itens_por_pagina: quantidade de itens únicos na primeira página
    """
    print("Estimando quantidade total de receitas...")
    driver.get(url_inicial)
    wait = WebDriverWait(driver, TEMPO_ESPERA_MAXIMO)

    # Descobrir número da última página
    num_paginas = 1
    try:
        page_links = wait.until(EC.presence_of_all_elements_located((By.XPATH, XPATH_PAGINACAO_LINKS)))
        page_numbers = [int(link.text) for link in page_links if link.text.isdigit()]
        if page_numbers:
            num_paginas = max(page_numbers)
        print(f"Número de páginas encontradas: {num_paginas}")
    except TimeoutException:
        print("Paginação não encontrada. Assumindo que há apenas 1 página.")

    # Coletar URLs ÚNICAS da primeira página
    print("Coletando links da primeira página...")
    urls_primeira_pagina = obter_links_pagina(driver, wait)
    itens_primeira_pagina = len(urls_primeira_pagina)
    
    if itens_primeira_pagina == 0:
        print("Atenção: não foi possível coletar itens na primeira página.")
        return {'total_estimado': 0, 'num_paginas': 1, 'itens_por_pagina': 0}
    
    print(f"Itens únicos na primeira página: {itens_primeira_pagina}")
    if itens_primeira_pagina > 0:
        print(f"Exemplo de URL: {list(urls_primeira_pagina)[0]}")

    # Se houver apenas 1 página, o total é exato
    if num_paginas == 1:
        total_estimado = itens_primeira_pagina
    else:
        # Verificar última página para cálculo preciso
        parsed_url = urlparse(url_inicial)
        query_params = parse_qs(parsed_url.query)
        query_params['page'] = [str(num_paginas)]
        ultima_pagina_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{urlencode(query_params, doseq=True)}"
        
        print(f"Verificando última página ({num_paginas}) para cálculo preciso...")
        driver.get(ultima_pagina_url)
        
        urls_ultima_pagina = obter_links_pagina(driver, wait)
        itens_ultima_pagina = len(urls_ultima_pagina)
        
        if itens_ultima_pagina == 0:
            print("Atenção: não foi possível contar itens na última página. Usando valor da primeira.")
            itens_ultima_pagina = itens_primeira_pagina
        else:
            print(f"Itens únicos na última página: {itens_ultima_pagina}")
        
        # Total = (páginas - 1) × itens_primeira_pagina + itens_ultima_pagina
        total_estimado = (num_paginas - 1) * itens_primeira_pagina + itens_ultima_pagina

    print(f"Total estimado de receitas únicas: {total_estimado}")
    return {
        'total_estimado': total_estimado,
        'num_paginas': num_paginas,
        'itens_por_pagina': itens_primeira_pagina
    }


def obter_todas_urls(driver: webdriver.Chrome, url_inicial: str, num_paginas: int) -> set:
    """Coleta todas as URLs percorrendo todas as páginas."""
    print(f"Coletando URLs de todas as {num_paginas} páginas...")
    
    parsed_url = urlparse(url_inicial)
    query_params = parse_qs(parsed_url.query)
    wait = WebDriverWait(driver, TEMPO_ESPERA_MAXIMO)
    
    urls_encontradas = set()
    
    for page in range(1, num_paginas + 1):
        query_params['page'] = [str(page)]
        next_page_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{urlencode(query_params, doseq=True)}"
        print(f"Coletando da página {page}/{num_paginas}...")
        driver.get(next_page_url)
        
        urls_pagina = obter_links_pagina(driver, wait)
        if urls_pagina:
            urls_encontradas.update(urls_pagina)
        else:
            print(f"  ✗ Aviso: Nenhuma receita encontrada na página {page}.")
    
    print(f"\nTotal de URLs únicas coletadas: {len(urls_encontradas)}")
    return urls_encontradas


def extrair_detalhes_receita(driver: webdriver.Chrome, url_receita: str) -> dict:
    """Extrai os detalhes de uma única página de receita."""
    driver.get(url_receita)
    wait = WebDriverWait(driver, TEMPO_ESPERA_MAXIMO)
    detalhes = {'url': url_receita, 'origem': 'Circulo'}
    
    try:
        detalhes['titulo'] = wait.until(EC.presence_of_element_located((By.TAG_NAME, TAG_TITULO))).text
    except TimeoutException:
        detalhes['titulo'] = "Título não encontrado"
    
    try:
        detalhes['materiais'] = driver.find_element(By.CLASS_NAME, CLASS_MATERIAIS).text
    except NoSuchElementException:
        detalhes['materiais'] = ""
    
    try:
        detalhes['receita'] = driver.find_element(By.CLASS_NAME, CLASS_EXECUCAO).text
    except NoSuchElementException:
        detalhes['receita'] = ""
    
    time.sleep(TEMPO_ESPERA_RECEITA)
    return detalhes


def main():
    """Orquestra o processo de web scraping com lógicas de cache, force e filtros."""
    parser = argparse.ArgumentParser(
        description="Web scraper de receitas com funcionalidade de cache.", 
        formatter_class=argparse.RawTextHelpFormatter
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--force', action='store_true', 
                      help='Força a raspagem completa, ignorando o cache.')
    group.add_argument('--update-urls-only', action='store_true', 
                      help='Apenas busca e atualiza a lista de URLs, sem extrair os detalhes.')
    group.add_argument('--strict-sync', action='store_true', 
                      help='Sincroniza se houver qualquer diferença (add/remove) entre o cache e o site.')
    
    parser.add_argument('--limit', type=int, 
                       help='Limita o número de receitas a serem extraídas para testes.')
    parser.add_argument('--range', nargs=2, type=int, metavar=('INICIO', 'FIM'), 
                       help='Define um intervalo de receitas a serem extraídas.')
    parser.add_argument('--no-headless', action='store_true',
                       help='Desativa o modo headless (mostra o navegador).')
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
        print(f"Arquivo de dados '{ARQUIVO_SAIDA_CSV}' não encontrado.")
        print("Ativando modo de primeira execução forçada.")
        args.force = True

    driver = configurar_driver(headless=not args.no_headless)
    try:
        # 1. Carregar cache local de URLs
        urls_locais = set()
        if os.path.exists(ARQUIVO_URLS):
            with open(ARQUIVO_URLS, 'r', encoding='utf-8') as f:
                urls_locais = set(line.strip() for line in f if line.strip())
            print(f"URLs no cache local: {len(urls_locais)}")
        else:
            print("Nenhum cache local encontrado.")

        # 2. Estimar quantidade de receitas no site
        info_estimativa = estimar_quantidade_receitas(driver, URL_PRODUTO)
        total_estimado = info_estimativa['total_estimado']
        num_paginas = info_estimativa['num_paginas']
        
        # 3. Decidir se precisa atualizar
        precisa_atualizar = False
        
        if args.force:
            print("\nModo --force ativado. Forçando coleta completa.")
            precisa_atualizar = True
        elif args.strict_sync:
            # No modo strict, precisamos coletar todas as URLs para comparar
            print("\nModo --strict-sync: coletando todas as URLs para comparação...")
            urls_remotas = obter_todas_urls(driver, URL_PRODUTO, num_paginas)
            precisa_atualizar = (urls_locais != urls_remotas)
            if precisa_atualizar:
                print(f"Diferença detectada: {len(urls_remotas)} remoto vs {len(urls_locais)} local")
            else:
                print("Nenhuma diferença encontrada. Cache sincronizado.")
        else:
            # Modo padrão: compara apenas a quantidade estimada
            if total_estimado != len(urls_locais):
                print(f"\nDiferença na quantidade detectada!")
                print(f"  Estimado no site: {total_estimado}")
                print(f"  No cache local: {len(urls_locais)}")
                precisa_atualizar = True
            else:
                print(f"\nQuantidades iguais ({total_estimado}). Nenhuma atualização necessária.")

        # 4. Se não precisa atualizar, encerra
        if not precisa_atualizar:
            print("Encerrando sem fazer alterações.")
            return

        # 5. Coletar todas as URLs (se ainda não coletou)
        if args.strict_sync:
            # Já coletamos no passo 3
            pass
        elif 'urls_remotas' not in locals():
            # Se não coletou ainda (diferença > 1), coletar agora
            print("\nIniciando coleta completa de URLs...")
            urls_remotas = obter_todas_urls(driver, URL_PRODUTO, num_paginas)

        # 6. Sincronizar o arquivo de cache de URLs
        with open(ARQUIVO_URLS, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_remotas)):
                f.write(url + '\n')
        print(f"\nArquivo de URLs '{ARQUIVO_URLS}' foi atualizado com {len(urls_remotas)} URLs.")
        
        if args.update_urls_only:
            print("\n--update-urls-only ativado. Script encerrado.")
            return

        # 7. Determinar quais URLs extrair
        if args.force:
            urls_alvo_base = sorted(list(urls_remotas))
            print(f"\nModo força: extraindo todas as {len(urls_alvo_base)} receitas.")
        else:
            urls_alvo_base = sorted(list(urls_remotas - urls_locais))
            print(f"\nNovas receitas a extrair: {len(urls_alvo_base)}")
        
        # 8. Aplicar filtros (limit/range)
        urls_para_extrair = urls_alvo_base
        if args.range:
            inicio, fim = args.range
            if inicio >= fim or inicio < 0:
                print(f"Erro: Intervalo inválido [{inicio}:{fim}].")
                return
            print(f"Aplicando filtro de intervalo: dos índices {inicio} a {fim}.")
            urls_para_extrair = urls_alvo_base[inicio:fim]
        elif args.limit:
            if args.limit <= 0:
                print("Erro: --limit deve ser um número positivo.")
                return
            print(f"Aplicando filtro de limite: extraindo as primeiras {args.limit} receitas.")
            urls_para_extrair = urls_alvo_base[:args.limit]

        # 9. Extrair receitas
        if not urls_para_extrair:
            print("\nNenhuma receita nova para extrair.")
        else:
            print(f"\nIniciando extração de {len(urls_para_extrair)} receitas...")
            dados_novos = []
            total = len(urls_para_extrair)
            
            inicio_extracao = time.time()
            for i, url in enumerate(urls_para_extrair, 1):
                if i % 10 == 0 or i == 1:  # Mostra progresso a cada 10 ou na primeira
                    tempo_decorrido = time.time() - inicio_extracao
                    if i > 1:
                        tempo_medio = tempo_decorrido / (i - 1)
                        tempo_restante = tempo_medio * (total - i + 1)
                        print(f"Progresso: {i}/{total} | Tempo médio: {tempo_medio:.1f}s/receita | Restante: ~{tempo_restante/60:.1f}min")
                    else:
                        print(f"Extraindo {i}/{total}...")
                dados_novos.append(extrair_detalhes_receita(driver, url))
            
            tempo_total = time.time() - inicio_extracao
            print(f"\n✓ Extração concluída em {tempo_total/60:.1f} minutos ({tempo_total/total:.1f}s por receita)")
            
            df_novos = pd.DataFrame(dados_novos, columns=['titulo', 'url', 'materiais', 'receita', 'origem'])
            
            if args.force or not os.path.exists(ARQUIVO_SAIDA_CSV):
                df_novos.to_csv(ARQUIVO_SAIDA_CSV, sep=';', encoding='utf-8-sig', index=False)
                print(f"\nDados salvos em '{ARQUIVO_SAIDA_CSV}' (modo sobrescrita).")
            else:
                df_novos.to_csv(ARQUIVO_SAIDA_CSV, mode='a', sep=';', 
                              encoding='utf-8-sig', index=False, header=False)
                print(f"\nNovos dados adicionados em '{ARQUIVO_SAIDA_CSV}' (modo acréscimo).")
            
            print(f"Total de receitas processadas: {len(dados_novos)}")
            
    finally:
        if driver:
            driver.quit()
            print("\nDriver finalizado.")

if __name__ == "__main__":
    main()