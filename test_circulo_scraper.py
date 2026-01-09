
import pprint
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from scrapers.circulo_scraper import CirculoScraper

def setup_driver(headless: bool = True) -> webdriver.Chrome:
    """Configures and initializes the Chrome WebDriver."""
    service = Service()
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.page_load_strategy = 'eager'
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def test_single_recipe():
    """
    Tests the extraction of a single recipe to debug selectors.
    """
    driver = None
    try:
        driver = setup_driver(headless=False) 
        scraper = CirculoScraper(driver)
        
        # Test with a single URL
        # test_url = "https://www.circulo.com.br/receitas/amigurumi-coracao"
        test_url = "https://www.circulo.com.br/receitas/bicho-bola-gato"
        
        
        print(f"Testing extraction from: {test_url}")
        
        details = scraper.extract_recipe_details(test_url)
        
        print("\n--- Extracted Details ---")
        pprint.pprint(details)
        print("-------------------------\n")

    except Exception as e:
        print(f"An error occurred during the test: {e}")
    finally:
        if driver:
            # Add a small delay so you can see the browser before it closes
            input("Press Enter to close the browser...")
            driver.quit()

if __name__ == "__main__":
    test_single_recipe()
