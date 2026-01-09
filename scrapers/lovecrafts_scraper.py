import os
import time
import traceback
import getpass  # Para ler a senha de forma segura no terminal
import csv
import pdfplumber

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# --- CONSTANTES ---
LOGIN_URL = "https://www.lovecrafts.com/en-gb/account/auth/sign-in"
SEARCH_URL = 'https://www.lovecrafts.com/en-gb/search?q=free%20amigurumi'

# --- FUNÇÕES AUXILIARES ---

def setup_driver():
    """Configura e retorna uma instância do Chrome WebDriver."""
    print("1. Configurando o navegador (Chrome)...")
    
    download_dir = os.path.join(os.getcwd(), "downloads")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        print(f"✓ Diretório de downloads criado em: {download_dir}")

    service = Service()
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    })

    driver = webdriver.Chrome(service=service, options=options)
    print("✓ Navegador configurado.")
    return driver

def type_text(driver, by, value, text, timeout=10):
    """Encontra um campo e digita o texto nele."""
    try:
        wait = WebDriverWait(driver, timeout)
        element = wait.until(EC.visibility_of_element_located((by, value)))
        element.clear()
        element.send_keys(text)
        print(f"✓ Texto digitado no campo: ({by}, {value})")
        return True
    except TimeoutException:
        print(f"✗ Campo de texto não encontrado a tempo: ({by}, {value})")
        return False

def click_element(driver, by, value, timeout=10):
    """Aguarda um elemento ser clicável e clica nele."""
    try:
        wait = WebDriverWait(driver, timeout)
        element = wait.until(EC.element_to_be_clickable((by, value)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5)
        element.click()
        print(f"✓ Elemento clicado: ({by}, {value})")
        return True
    except TimeoutException:
        print(f"✗ Elemento não encontrado ou não clicável a tempo: ({by}, {value})")
        return False

def setup_csv(filename="receitas.csv"):
    """Cria o arquivo CSV com o cabeçalho se ele não existir."""
    fieldnames = ['titulo', 'abreviacoes', 'receita', 'origem']
    if not os.path.exists(filename):
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
        print(f"✓ Arquivo CSV '{filename}' criado com sucesso.")

def append_to_csv(data, filename="receitas.csv"):
    """Adiciona uma linha de dados ao arquivo CSV."""
    fieldnames = ['titulo', 'abreviacoes', 'receita', 'origem']
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow(data)
    print(f"✓ Dados da receita '{data.get('titulo', 'N/A')}' salvos no CSV.")

def parse_pdf(pdf_path):
    """
    Extrai o conteúdo de um arquivo PDF e tenta separar em
    título, abreviações e receita.
    """
    print(f"   - Lendo o arquivo PDF: {os.path.basename(pdf_path)}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"

            titulo = os.path.basename(pdf_path).replace('.pdf', '').replace('_', ' ').strip()
            abreviacoes = ""
            receita = full_text

            lower_text = full_text.lower()
            abbreviations_kw = "abbreviations"
            pattern_kw = "pattern"

            abbrev_pos = lower_text.find(abbreviations_kw)
            pattern_pos = lower_text.find(pattern_kw)

            if abbrev_pos != -1 and pattern_pos != -1 and abbrev_pos < pattern_pos:
                abreviacoes = full_text[abbrev_pos : pattern_pos]
                receita = full_text[pattern_pos:]
            elif abbrev_pos != -1:
                 abreviacoes = full_text[abbrev_pos:]
                 receita = ""
            
            lines = full_text.split('\n')
            if lines and len(lines[0].strip()) > 3:
                titulo = lines[0].strip()

            print("   - ✓ Leitura do PDF concluída.")
            return {
                "titulo": titulo,
                "abreviacoes": abreviacoes.strip(),
                "receita": receita.strip(),
                "origem": "lovecrafts"
            }
    except Exception as e:
        print(f"   - ✗ Erro ao ler ou processar o PDF: {e}")
        return None

def wait_for_download_complete(download_dir, timeout=60):
    """
    Espera um download ser concluído em um diretório, monitorando
    arquivos '.crdownload'. Retorna o path do novo arquivo.
    """
    print("   - Aguardando o download ser concluído...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        in_progress_downloads = [f for f in os.listdir(download_dir) if f.endswith('.crdownload')]
        if not in_progress_downloads:
            pdf_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir) if f.lower().endswith('.pdf')]
            if pdf_files:
                latest_file = max(pdf_files, key=os.path.getmtime)
                if time.time() - os.path.getmtime(latest_file) < 15: # Arquivo modificado nos últimos 15s
                    print(f"   - ✓ Download concluído: {os.path.basename(latest_file)}")
                    return latest_file
        
        time.sleep(1)
    
    print("   - ✗ Tempo de espera para o download excedido.")
    return None



def fazer_login(driver, email, password):
    """Navega para a página de login e executa o login."""
    print("\n--- INICIANDO PROCESSO DE LOGIN ---")
    print(f"2. Acessando a página de login: {LOGIN_URL}")
    driver.get(LOGIN_URL)

    # --- Etapa 2.5: Tentar fechar o banner de cookies/promoção ---
    print("\n2.5. Procurando por banners (cookies/promoções) para fechar...")
    
    accept_selectors = [
        (By.ID, "onetrust-accept-btn-handler"),
        (By.XPATH, '//button[contains(text(), "Accept")]'),
        (By.XPATH, '//button[contains(text(), "Accept All")]'),
        (By.XPATH, '//button[contains(text(), "I agree")]'),
    ]
    
    banner_closed = False
    for by, selector in accept_selectors:
        if click_element(driver, by, selector, timeout=3):
            print(f"   ✓ Banner fechado com sucesso usando o seletor: ({by}, {selector})")
            banner_closed = True
            time.sleep(1)
            break

    if not banner_closed:
        print("   ! Aviso: Nenhum banner de cookies foi encontrado ou fechado. O script continuará.")

    print("\n3. Preenchendo o formulário de login...")
    if not type_text(driver, By.ID, "email", email):
        return False
    
    if not type_text(driver, By.ID, "password", password):
        return False
        
    print("4. Clicando no botão 'Sign In & Continue'...")
    if not click_element(driver, By.XPATH, '//button[@type="submit" and contains(., "Sign In & Continue")]'):
        print("   - FALHA: Não foi possível clicar no botão de login.")
        return False
    
    # Aguarda o login ser processado
    try:
        WebDriverWait(driver, 15).until(EC.url_changes(LOGIN_URL))
        print("✓ Login parece ter sido bem-sucedido (URL mudou).")
        print("--- FIM DO PROCESSO DE LOGIN ---")
        return True
    except TimeoutException:
        print("✗ FALHA NO LOGIN: A página não redirecionou após a tentativa de login.")
        print("   - Verifique se o email e a senha estão corretos.")
        print("--- FIM DO PROCESSO DE LOGIN ---")
        return False

# --- SCRIPT PRINCIPAL ---
def main():



    """Função principal que faz login, busca todas as receitas,



    baixa os PDFs e salva as informações em um CSV."""

    # --- Coleta de Credenciais ---



    lc_email = os.environ.get('LOVECRAFTS_EMAIL')


    lc_password = os.environ.get('LOVECRAFTS_PASSWORD')







    if not lc_email:



        lc_email = input("Digite seu email da Lovecrafts: ")



    if not lc_password:



        lc_password = getpass.getpass("Digite sua senha da Lovecrafts: ")







    driver = setup_driver()



    download_dir = os.path.join(os.getcwd(), "downloads")



    



    try:



        # --- Etapa 1: Fazer Login ---



        if not fazer_login(driver, lc_email, lc_password):



            return  # Encerra se o login falhar







        # --- Etapa 2: Coletar URLs de todas as receitas da busca ---



        print(f"\n--- INICIANDO COLETA DE RECEITAS ---")



        print(f"5. Acessando a página de busca: {SEARCH_URL}")



        driver.get(SEARCH_URL)



        



        recipe_urls = []



        page_num = 1



        while True:



            print(f"\n6. Lendo receitas da página {page_num}...")



            try:



                WebDriverWait(driver, 15).until(



                    EC.visibility_of_element_located((By.XPATH, "//ul[contains(@class, 'products')]"))



                )



            except TimeoutException:



                print("✗ A lista de produtos não carregou. Encerrando coleta de URLs.")



                break







            product_links = driver.find_elements(By.XPATH, "//ul[contains(@class, 'products')]/li//a")



            page_urls = list(set([link.get_attribute('href') for link in product_links if link.get_attribute('href')]))



            new_urls = [url for url in page_urls if url not in recipe_urls]



            recipe_urls.extend(new_urls)



            print(f"   - {len(new_urls)} novas receitas encontradas na página.")







            try:



                next_button = driver.find_element(By.XPATH, '//a[@aria-label="Next"]')



                if next_button.is_displayed() and next_button.is_enabled():



                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)



                    time.sleep(0.5)



                    next_button.click()



                    page_num += 1



                    time.sleep(3)



                else:



                    print("✓ Fim da paginação (botão 'Next' desabilitado).")



                    break



            except Exception:



                print("✓ Fim da paginação (botão 'Next' não encontrado).")



                break



        



        print(f"\n--- COLETA FINALIZADA: {len(recipe_urls)} RECEITAS ENCONTRADAS ---")







        # --- Etapa 3: Processar cada receita ---



        print("\n--- INICIANDO DOWNLOAD E PROCESSAMENTO DOS PDFS ---")



        setup_csv()







        for i, url in enumerate(recipe_urls):



            print(f"\n[{i+1}/{len(recipe_urls)}] Processando receita: {url}")



            driver.get(url)



            time.sleep(2)







            possible_selectors = [



                (By.XPATH, '//button[contains(translate(., "DOWNLOAD", "download"), "download")]'),



                (By.XPATH, '//a[contains(translate(., "DOWNLOAD", "download"), "download")]'),



                (By.XPATH, '//button[contains(translate(., "ADD TO LIBRARY", "add to library"), "add to library")]'),



                (By.XPATH, '//button[contains(translate(., "FREE", "free"), "free")]'),



            ]



            button_clicked = False



            for by, selector in possible_selectors:



                if click_element(driver, by, selector, timeout=5):



                    button_clicked = True



                    break



            



            if not button_clicked:



                print("   - FALHA: Nenhum botão de download encontrado. Pulando.")



                continue







            time.sleep(3)



            



            in_library_selector = (By.XPATH, '//*[contains(text(), "In your library")]')



            download_link_selector_str = '//a[contains(@href, ".pdf")] | //a[contains(translate(., "DOWNLOAD", "download"), "download")]'







            try:



                WebDriverWait(driver, 3).until(EC.visibility_of_element_located(in_library_selector))



                print("   - Receita adicionada à biblioteca. Tentando clicar no download final.")



                if not click_element(driver, By.XPATH, download_link_selector_str):



                    print("   - AVISO: Não foi possível clicar no link de download final.")



            except TimeoutException:



                pass 



            



            downloaded_pdf = wait_for_download_complete(download_dir)



            if downloaded_pdf:



                pdf_data = parse_pdf(downloaded_pdf)



                if pdf_data:



                    append_to_csv(pdf_data)



            else:



                print("   - FALHA: O download do PDF não foi concluído ou não foi encontrado.")







        print("\n--- PROCESSO FINALIZADO ---")







    except Exception:



        print("\n✗ Ocorreu um erro inesperado no script!")



        traceback.print_exc()



        



    finally:



        print("\n10. Fechando o navegador.")



        driver.quit()







if __name__ == "__main__":



    main()


