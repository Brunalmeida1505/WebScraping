import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from scrapers.circulo_scraper import CirculoScraper
from scrapers.mariskavos_scraper import MariskavosScraper
from scrapers.always_free_amigurumi_scraper import AlwaysFreeAmigurumiScraper
from scrapers.lovecrafts_scraper import LovecraftsScraper
from scrapers.amigurum_scraper import AmigurumScraper
from scrapers.ravelry_scraper import RavelryScraper
from scrapers.scribd_scraper import ScribdScraper

# Maps scraper names to their classes
AVAILABLE_SCRAPERS = {
    "circulo": CirculoScraper,
    "mariskavos": MariskavosScraper,
    "alwaysfreeamigurumi": AlwaysFreeAmigurumiScraper,
    "lovecrafts": LovecraftsScraper,
    "amigurum": AmigurumScraper,
    "ravelry": RavelryScraper,
    "scribd": ScribdScraper,
}

def setup_driver(headless: bool = True, scraper_name: str = None, use_profile: bool = False) -> webdriver.Chrome:
    """Configures and initializes the Chrome WebDriver."""
    import os
    
    # Ravelry usa API, não precisa de WebDriver
    if scraper_name == "ravelry":
        return None
    
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
    
    # Special configuration for Scribd (needs PDF download)
    if scraper_name == "scribd":
        download_dir = os.path.join(os.getcwd(), "downloads", "scribd")
        os.makedirs(download_dir, exist_ok=True)
        
        # Option 1: Use real Chrome profile (recommended for Scribd)
        if use_profile:
            import getpass
            username = getpass.getuser()
            profile_path = f"C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data"
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            print(f"✓ Using Chrome profile from: {profile_path}")
        else:
            # Option 2: Stealth mode configuration (usar perfil temporário)
            import tempfile
            temp_profile = tempfile.mkdtemp()
            options.add_argument(f"--user-data-dir={temp_profile}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            print(f"✓ Using temporary profile: {temp_profile}")
        
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_experimental_option("prefs", {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "safebrowsing.enabled": False,  # Disabled safe browsing
            "profile.default_content_setting_values.automatic_downloads": 1,
        })
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # For Scribd without profile, hide automation flags
    if scraper_name == "scribd" and not use_profile:
        print("✓ Applying anti-detection measures...")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    if scraper_name == "scribd":
        print("✓ Chrome initialized successfully for Scribd")
    
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
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='(Scribd, Lovecrafts) Limit the number of documents/recipes to process.'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Process only URLs that are not yet present in the results CSV (scribd_dados.csv).'
    )
    parser.add_argument(
        '--use-profile',
        action='store_true',
        help='(Scribd) Use your existing Chrome profile (avoids "not secure" warnings).'
    )

    args = parser.parse_args()
    args_dict = vars(args)

    driver = None
    try:
        # 1. Select the strategy based on user input
        scraper_class = AVAILABLE_SCRAPERS[args.scraper]
        
        print(f"Setting up WebDriver for '{scraper_class.__name__}'...")
        
        # Decide whether to run headless. For Scribd, it's often necessary to show 
        # the browser (manual login / anti-bot checks).
        # Open browser in visible mode for Scribd unless user explicitly passed --no-headless
        headless_flag = not args.no_headless
        if args.scraper == 'scribd' and headless_flag:
            print("⚠️  Scribd detected: opening browser in visible mode.")
            headless_flag = False

        driver = setup_driver(headless=headless_flag, scraper_name=args.scraper, use_profile=args_dict.get('use_profile', False))
        
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
