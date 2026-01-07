

import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# --- CONSTANTS ---
BASE_URL = "https://www.mariskavos.nl"
DB_DIR = "db"
URL_FILE_PATH = os.path.join(DB_DIR, "found_urls.txt")
CSV_FILE_PATH = os.path.join(DB_DIR, "receitas_crochet.csv")
MAX_PAGES_TO_SCRAPE = 5 # Defina o número de páginas para raspar

def setup_driver():
    """Configura e retorna uma instância do Chrome WebDriver."""
    service = Service()
    options = Options()
    # options.add_argument("--headless")  # Descomente para executar em modo headless
    return webdriver.Chrome(service=service, options=options)

def collect_recipe_urls(driver, base_url, max_pages):
    """
    Coleta URLs de receitas de um site, navegando por um número definido de páginas.
    """
    print("Iniciando a coleta de URLs de receitas...\n")
    recipe_urls = set()

    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            page_url = base_url
        else:
            page_url = f"{base_url}/page/{page_num}/"

        print(f"\n--- Analisando página {page_num}: {page_url} ---")
        
        try:
            driver.get(page_url)
            time.sleep(3)  # Aguarde o carregamento da página

            links = driver.find_elements(By.TAG_NAME, "a")
            print(f"Encontrados {len(links)} links na página.")

            for link in links:
                href = link.get_attribute("href")
                if (href and 
                    base_url in href and 
                    'free-' in href and 
                    'pattern' in href and 
                    not any(ignore in href for ignore in ['/page/', '#', '?'])):
                    
                    cleaned_url = href.rstrip('/')
                    if cleaned_url not in recipe_urls:
                        print(f"  [+] Nova receita encontrada: {cleaned_url}")
                        recipe_urls.add(cleaned_url)
        
        except Exception as e:
            print(f"  [!] Erro ao acessar a página {page_num}: {e}")
            continue # Pula para a próxima página em caso de erro

    print(f"\n{'='*60}")
    print(f"Coleta de URLs finalizada. Total de receitas únicas: {len(recipe_urls)}")
    print(f"{ '='*60}\n")
    
    return sorted(list(recipe_urls))

def save_urls_to_file(urls, file_path):
    """Salva uma lista de URLs em um arquivo de texto."""
    print(f"Salvando {len(urls)} URLs em '{file_path}'...")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(f"{url}\n")
        print("✓ URLs salvas com sucesso.")
    except IOError as e:
        print(f"  [!] Erro ao salvar o arquivo de URLs: {e}")

def extract_recipe_details(driver, url):
    """
    Extrai os detalhes de uma única página de receita.
    """
    driver.get(url)
    time.sleep(3)
    
    recipe_data = {
        'titulo': '', 'url': url, 'materiais': [], 'abreviacoes': '', 
        'instrucoes': [], 'origem': BASE_URL.split('//')[1]
    }
    
    try:
        recipe_data['titulo'] = driver.find_element(By.CLASS_NAME, "entry-title").text
        
        content_container = driver.find_element(By.CLASS_NAME, "entry-content")
        
        # Lógica para extrair materiais e abreviações
        # Esta parte é complexa e depende da estrutura do site.
        # A implementação original foi mantida com pequenas melhorias.
        elements = content_container.find_elements(By.XPATH, "./*[not(contains(@class, 'wp-block-list'))]")
        current_section = None
        for elem in elements:
            if "lwptoc" in (elem.get_attribute("class") or ""):
                continue

            text = elem.text.strip()
            if not text:
                continue
            
            lower_text = text.lower()
            
            if any(term in lower_text for term in ['share this', 'related posts', 'leave a comment']):
                current_section = None
                continue

            search_text = lower_text
            try:
                strong_text = elem.find_element(By.TAG_NAME, 'strong').text.lower().strip()
                if len(strong_text) > 2:
                    search_text = strong_text
            except:
                pass

            is_new_section = False
            if 'materials' in search_text:
                current_section = 'materiais'
                is_new_section = True
            elif 'abbreviations' in search_text:
                current_section = 'abreviacoes'
                is_new_section = True
            elif any(w in search_text for w in ['pattern', 'instructions']) or any(w in lower_text for w in ['round 1', 'rnd 1', 'row 1']):
                current_section = None

            if current_section:
                content_to_add = text
                if is_new_section:
                    content_to_add = '\n'.join([line for line in text.split('\n') if 'materials' not in line.lower() and 'abbreviations' not in line.lower()]).strip()
                
                if content_to_add:
                    if current_section == 'materiais':
                        recipe_data['materiais'].append(content_to_add)
                    elif current_section == 'abreviacoes':
                        recipe_data['abreviacoes'] += content_to_add + '\n'

        # Lógica para extrair instruções
        instruction_blocks = content_container.find_elements(By.CSS_SELECTOR, ".wp-block-list")
        for block in instruction_blocks:
            try:
                # Tenta encontrar um título no parágrafo anterior
                title_element = block.find_element(By.XPATH, "preceding-sibling::p[1]")
                title = title_element.text.strip()
                content = block.text.strip()
                recipe_data['instrucoes'].append(f"{title}\n{content}" if title else content)
            except:
                # Se falhar, adiciona apenas o conteúdo do bloco
                recipe_data['instrucoes'].append(block.text.strip())

    except Exception as e:
        print(f"  [!] Erro ao processar {url}: {e}")
    
    # Limpeza final dos dados extraídos
    recipe_data['materiais'] = sorted(list(set(m for m in recipe_data['materiais'] if m)))
    recipe_data['abreviacoes'] = recipe_data['abreviacoes'].strip()
    recipe_data['instrucoes'] = sorted(list(set(i for i in recipe_data['instrucoes'] if i)))
    
    return recipe_data

def main():
    """
    Função principal para orquestrar a raspagem de dados.
    """
    # Garante que o diretório de banco de dados exista
    os.makedirs(DB_DIR, exist_ok=True)
    
    driver = setup_driver()
    
    try:
        # 1. Coletar todas as URLs
        recipe_urls = collect_recipe_urls(driver, BASE_URL, MAX_PAGES_TO_SCRAPE)
        
        # 2. Salvar as URLs em um arquivo de texto
        if recipe_urls:
            save_urls_to_file(recipe_urls, URL_FILE_PATH)
        else:
            print("Nenhuma URL de receita foi encontrada. O script será encerrado.")
            return

        # 3. Extrair detalhes de cada receita
        print(f"\nIniciando extração de detalhes de {len(recipe_urls)} receitas...")
        all_recipes_data = []
        for i, url in enumerate(recipe_urls, 1):
            print(f"\n--- Processando [{i}/{len(recipe_urls)}]: {url} ---")
            recipe_data = extract_recipe_details(driver, url)
            all_recipes_data.append(recipe_data)
            time.sleep(1) # Pausa para não sobrecarregar o servidor
        
        # 4. Salvar os dados compilados em um arquivo CSV
        if all_recipes_data:
            print(f"\nSalvando {len(all_recipes_data)} receitas em '{CSV_FILE_PATH}'...")
            df = pd.DataFrame(all_recipes_data)
            df.to_csv(CSV_FILE_PATH, sep=';', index=False, encoding='utf-8-sig')
            print(f"✓ Dados salvos com sucesso em '{CSV_FILE_PATH}'")
        else:
            print("Nenhum dado de receita foi extraído.")

    finally:
        print("\nFinalizando o script e fechando o WebDriver.")
        driver.quit()

if __name__ == "__main__":
    main()
