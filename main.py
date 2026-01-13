import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from scrapers.circulo_scraper import CirculoScraper
from scrapers.mariskavos_scraper import MariskavosScraper
from scrapers.always_free_amigurumi_scraper import AlwaysFreeAmigurumiScraper
from scrapers.lovecrafts_scraper import LovecraftsScraper
from scrapers.amigurum_scraper import AmigurumScraper

# Maps scraper names to their classes
AVAILABLE_SCRAPERS = {
    "circulo": CirculoScraper,
    "mariskavos": MariskavosScraper,
    "alwaysfreeamigurumi": AlwaysFreeAmigurumiScraper,
    "lovecrafts": LovecraftsScraper,
    "amigurum": AmigurumScraper,
}

def setup_driver(headless: bool = True, scraper_name: str = None) -> webdriver.Chrome:
    """Configures and initializes the Chrome WebDriver."""
    import os
    
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
    
    # Special configuration for Lovecrafts (needs PDF download)
    if scraper_name == "lovecrafts":
        download_dir = os.path.join(os.getcwd(), "downloads")
        options.add_argument("--start-maximized")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
        options.add_experimental_option("prefs", {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        })
    
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def main():
    """
    Main entry point for the web scraping application.
    It uses a Strategy pattern to select and run the appropriate scraper.
    """
    parser = argparse.ArgumentParser(
        description="A multi-site web scraper for recipes.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "scraper", 
        choices=AVAILABLE_SCRAPERS.keys(), 
        help="The name of the scraper to run."
    )
    parser.add_argument(
        '--force', 
        action='store_true', 
        help='Forces a full scrape, ignoring any caches.'
    )
    parser.add_argument(
        '--update-urls-only', 
        action='store_true', 
        help='Only updates the URL list without extracting recipe details.'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Disables headless mode to show the browser UI.'
    )
    # Argument specific to Mariskavos scraper, but harmless for others
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='(Mariskavos, AlwaysFreeAmigurumi & Amigurum) Max number of pages/scrolls to scrape. If not specified, Amigurum will collect ALL recipes.'
    )

    args = parser.parse_args()
    args_dict = vars(args)

    driver = None
    try:
        # 1. Select the strategy based on user input
        scraper_class = AVAILABLE_SCRAPERS[args.scraper]
        
        print(f"Setting up WebDriver for '{scraper_class.__name__}'...")
        driver = setup_driver(headless=not args.no_headless, scraper_name=args.scraper)
        
        # 2. Instantiate the scraper strategy
        scraper_strategy = scraper_class(driver)
        
        print(f"Running scraper: {scraper_strategy.get_name()}...")
        
        # 3. Execute the scraper's run method
        scraper_strategy.run(args_dict)
        
        print(f"\nScraper '{scraper_strategy.get_name()}' finished successfully.")

    except KeyError:
        print(f"Error: Scraper '{args.scraper}' is not available.")
        print(f"Available scrapers are: {', '.join(AVAILABLE_SCRAPERS.keys())}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if driver:
            driver.quit()
            print("\nWebDriver has been closed.")

if __name__ == "__main__":
    main()
