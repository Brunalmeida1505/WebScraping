import os
import time
import pandas as pd
from urllib.parse import urlparse, parse_qs, urlencode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers.base_scraper import ScraperStrategy

class CirculoScraper(ScraperStrategy):
    """Scraper for recipes from circulo.com.br."""

    def __init__(self, driver):
        super().__init__(driver)
        self.wait = WebDriverWait(driver, 8)
        self.name = "Circulo"
        self.url_produto = "https://www.circulo.com.br/receitas?termo=&dificuldade=&categoria=&tecnica=&peca=&produto=2286"
        self.diretorio_db = 'db'
        self.arquivo_urls = os.path.join(self.diretorio_db, 'circulo_urls.txt')
        self.diretorio_resultados = os.path.join(self.diretorio_db, 'resultados')
        self.arquivo_saida_csv = os.path.join(self.diretorio_resultados, 'circulo_dados.csv')

        # --- Selectors ---
        self.seletores_links_receitas = [
            "//a[contains(@href, '/receitas/') and not(contains(@href, '?')) and not(contains(@href, '#'))]", # Most generic
            "//article[contains(@class, 'recipe-card')]//a[contains(@href, '/receitas/') and not(contains(@href, '?')) and not(contains(@href, '#'))]",
            "//div[contains(@class, 'recipe-item')]//a[contains(@href, '/receitas/') and not(contains(@href, '?')) and not(contains(@href, '#'))]",
            "//div[contains(@class, 'card-receita')]//a[contains(@href, '/receitas/') and not(contains(@href, '?')) and not(contains(@href, '#'))]", # Kept from old for backward compatibility
        ]
        self.xpath_paginacao_links = "//ul[@class='pagination']//a[@class='page-link']"
        self.tag_titulo = "h2"
        self.class_materiais = "receita-detalhe__conteudo"
        self.class_execucao = "receita-detalhe__execucao"

    def get_name(self) -> str:
        return self.name

    def _obter_links_pagina(self, wait: WebDriverWait) -> set:
        """Tries different selectors to collect recipe links from the current page."""
        urls_encontradas = set()
        for i, seletor in enumerate(self.seletores_links_receitas):
            try:
                # Use a shorter timeout for subsequent selectors
                timeout_local = 3 if i > 0 else 8
                wait_local = WebDriverWait(self.driver, timeout_local)
                
                links = wait_local.until(EC.presence_of_all_elements_located((By.XPATH, seletor)))
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        # Basic validation to ensure it's a unique recipe URL
                        if href and '/receitas/' in href and '?' not in href and '#' not in href:
                            urls_encontradas.add(href)
                    except Exception:
                        continue # Skip invalid links
                
                if urls_encontradas:
                    # Return as soon as links are found with any selector
                    return urls_encontradas
            except TimeoutException:
                # If a selector times out, try the next one
                continue
            except NoSuchElementException:
                # If a selector returns no elements, try the next one
                continue
            except Exception as e:
                print(f"  [!] Error with selector {seletor}: {e}")
                continue

        return urls_encontradas

    def estimate_recipe_count(self) -> dict:
        """Estimates the total number of recipes."""
        print("Estimating total number of recipes for Circulo...")
        self.driver.get(self.url_produto)

        # Handle cookie consent banner
        try:
            time.sleep(2) # Wait for the banner to appear
            cookie_button = self.wait.until(EC.element_to_be_clickable(
                (By.ID, "CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll")
            ))
            cookie_button.click()
            print("Cookie consent accepted.")
            time.sleep(1) # Wait for banner to disappear
        except TimeoutException:
            print("Cookie consent banner not found or already accepted.")
            pass # Banner not found, continue
        
        num_paginas = 1
        found_pagination_numbers = False
        try:
            page_links = self.wait.until(EC.presence_of_all_elements_located((By.XPATH, self.xpath_paginacao_links)))
            page_numbers = [int(link.text) for link in page_links if link.text.isdigit()]
            if page_numbers:
                num_paginas = max(page_numbers)
                found_pagination_numbers = True
        except TimeoutException:
            pass # Assumes 1 page if pagination not found or no numbers

        if not found_pagination_numbers:
            # Fallback: check for a "Next" button if numbered pagination is not found
            try:
                # Look for a common "Next" button pattern
                next_button = self.driver.find_element(By.XPATH, "//a[contains(@class, 'next') or contains(text(), 'Próxima') or @aria-label='Next']")
                if next_button.is_displayed():
                    # Set a high number to indicate pagination by "Next" button
                    num_paginas = 9999
            except NoSuchElementException:
                pass # No "Next" button found, assume 1 page


        urls_primeira_pagina = self._obter_links_pagina(self.wait)
        itens_primeira_pagina = len(urls_primeira_pagina)

        if num_paginas == 1:
            total_estimado = itens_primeira_pagina
        else:
            # Simplified estimation
            total_estimado = num_paginas * itens_primeira_pagina

        return {'total_estimado': total_estimado, 'num_paginas': num_paginas}

    def collect_recipe_urls(self, num_paginas: int) -> set:
        """Collects all URLs by iterating through all pages using either numbered pages or a 'Next' button."""
        print(f"Collecting URLs for Circulo (estimated {num_paginas} pages)...")
        urls_encontradas = set()

        if num_paginas == 9999: # Indicates "Next" button pagination
            print("Using 'Next' button pagination strategy.")
            self.driver.get(self.url_produto)
            # Initial collection from the first page
            urls_encontradas.update(self._obter_links_pagina(self.wait))

            current_page_num = 1
            while True:
                current_page_num += 1
                print(f"Collecting from page (via 'Next' button) {current_page_num}...")
                try:
                    # Try to find and click the "Next" button
                    next_button = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//a[contains(@class, 'next') or contains(text(), 'Próxima') or @aria-label='Next']")
                    ))
                    
                    if "disabled" in next_button.get_attribute("class"):
                        print("  'Next' button is disabled. Finishing pagination.")
                        break
                    
                    next_button.click()
                    time.sleep(2) # Wait for the next page to load
                    
                    urls_encontradas.update(self._obter_links_pagina(self.wait))
                except (TimeoutException, NoSuchElementException):
                    print("  'Next' button not found or not clickable. Finishing pagination.")
                    break
                except Exception as e:
                    print(f"  [!] Error clicking 'Next' button: {e}. Finishing pagination.")
                    break

        else: # Numbered pagination strategy
            print(f"Using numbered pagination strategy for {num_paginas} pages.")
            parsed_url = urlparse(self.url_produto)
            query_params = parse_qs(parsed_url.query)

            for page in range(1, num_paginas + 1):
                query_params['page'] = [str(page)]
                next_page_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{urlencode(query_params, doseq=True)}"
                print(f"Collecting from page {page}/{num_paginas}...")
                self.driver.get(next_page_url)
                time.sleep(2) # Give some time for content to load
                urls_encontradas.update(self._obter_links_pagina(self.wait))
        
        return urls_encontradas

    def extract_recipe_details(self, url_receita: str) -> dict:
        """Extracts details from a single recipe page."""
        self.driver.get(url_receita)
        detalhes = {'url': url_receita, 'origem': self.name}

        try:
            # Extract title
            try:
                detalhes['titulo'] = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, self.tag_titulo))).text.strip()
            except TimeoutException:
                detalhes['titulo'] = "Título não encontrado"

            # Extract materials
            try:
                materiais_element = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, self.class_materiais)))
                detalhes['materiais'] = materiais_element.text.strip()
            except TimeoutException:
                detalhes['materiais'] = "Materiais não encontrados"

            # Extract recipe
            try:
                receita_element = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, self.class_execucao)))
                detalhes['receita'] = receita_element.text.strip()
            except TimeoutException:
                detalhes['receita'] = "Receita não encontrada"

        except Exception as e:
            print(f"  [!] An unexpected error occurred while processing {url_receita}: {e}")
            detalhes['receita'] = "Erro ao extrair conteúdo."
        
        return detalhes
        
    def run(self, args: dict):
        os.makedirs(self.diretorio_resultados, exist_ok=True)
        
        is_force_mode = args.get('force', False)
        if not os.path.exists(self.arquivo_saida_csv) and not is_force_mode:
            print(f"Data file '{self.arquivo_saida_csv}' not found. Activating forced first run mode.")
            is_force_mode = True

        urls_locais = set()
        if os.path.exists(self.arquivo_urls):
            with open(self.arquivo_urls, 'r', encoding='utf-8') as f:
                urls_locais = set(line.strip() for line in f if line.strip())

        info_estimativa = self.estimate_recipe_count()
        total_estimado = info_estimativa['total_estimado']

        needs_update = is_force_mode or (total_estimado != len(urls_locais))
        
        if not needs_update:
            print("Circulo scraper: No updates needed.")
            return

        print("Circulo scraper: Update needed, collecting all URLs...")
        urls_remotas = self.collect_recipe_urls(info_estimativa['num_paginas'])

        with open(self.arquivo_urls, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_remotas)):
                f.write(url + '\n')
        
        if args.get('update_urls_only'):
            print("Circulo scraper: URLs updated. Halting as requested.")
            return
            
        urls_to_extract = sorted(list(urls_remotas)) if is_force_mode else sorted(list(urls_remotas - urls_locais))

        if not urls_to_extract:
            print("Circulo scraper: No new recipes to extract.")
            return

        print(f"Circulo scraper: Starting extraction of {len(urls_to_extract)} recipes...")
        new_data = [self.extract_recipe_details(url) for url in urls_to_extract]

        df_novos = pd.DataFrame(new_data, columns=['titulo', 'url', 'materiais', 'receita', 'origem'])
        
        if is_force_mode or not os.path.exists(self.arquivo_saida_csv):
            df_novos.to_csv(self.arquivo_saida_csv, sep=';', encoding='utf-8-sig', index=False)
        else:
            df_novos.to_csv(self.arquivo_saida_csv, mode='a', sep=';', encoding='utf-8-sig', index=False, header=False)
            
        print(f"Circulo scraper: Successfully processed {len(new_data)} recipes.")
