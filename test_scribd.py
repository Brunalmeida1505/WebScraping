"""
Script de teste rápido para o Scribd Scraper
Execute este arquivo para testar o scraper com configurações mínimas
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from scrapers.scribd_scraper import ScribdScraper
import os

def setup_driver():
    """Configura o driver do Chrome para o Scribd"""
    import getpass
    service = Service()
    options = webdriver.ChromeOptions()
    
    # Configurações para download de PDF
    download_dir = os.path.join(os.getcwd(), "downloads", "scribd")
    os.makedirs(download_dir, exist_ok=True)
    
    # Criar um diretório temporário para perfil
    import tempfile
    temp_profile = tempfile.mkdtemp()
    options.add_argument(f"--user-data-dir={temp_profile}")
    
    print(f"✓ Usando perfil temporário: {temp_profile}")
    
    # Anti-detecção
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Importante: remover headless para ver o processo
    # options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # User agent realista
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Configurações de download
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": False,  # Desabilitar safe browsing
        "profile.default_content_setting_values.automatic_downloads": 1,
    })
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # Esconder indicadores de automação
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    print("✓ Chrome iniciado com proteções anti-detecção")
    print("")
    
    return driver

def main():
    """Executa um teste rápido do Scribd scraper"""
    print("="*60)
    print("TESTE RÁPIDO - Scribd Scraper")
    print("="*60)
    print("\nEste script irá:")
    print("1. Fazer login no Scribd com suas credenciais")
    print("2. Coletar URLs de 1 página de resultados")
    print("3. Processar apenas 2 documentos (para teste)")
    print("4. Fazer download dos PDFs")
    print("5. Converter para base64")
    print("\n" + "="*60 + "\n")
    
    driver = None
    try:
        # Setup
        driver = setup_driver()
        scraper = ScribdScraper(driver)
        
        # Executar com limites para teste
        scraper.run({
            'force': True,      # Forçar nova coleta (ignorar cache)
            'limit': 2,         # Processar apenas 2 documentos
            # Descomente as linhas abaixo para usar credenciais diretas
            # 'email': 'seu_email@exemplo.com',
            # 'password': 'sua_senha'
        })
        
        print("\n" + "="*60)
        print("✓ TESTE CONCLUÍDO COM SUCESSO!")
        print("="*60)
        print("\nVerifique os resultados em:")
        print(f"  - URLs: db/scribd_urls.txt")
        print(f"  - Dados: db/resultados/scribd_dados.csv")
        print(f"  - PDFs: downloads/scribd/")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n✗ ERRO NO TESTE: {e}")
        print("\nDicas:")
        print("  - Verifique se suas credenciais estão corretas no .env")
        print("  - Certifique-se que sua conta Scribd está ativa")
        print("  - Execute com --no-headless para ver o navegador")
        
    finally:
        if driver:
            input("\nPressione ENTER para fechar o navegador...")
            driver.quit()
            print("✓ Navegador fechado.")

if __name__ == "__main__":
    main()
