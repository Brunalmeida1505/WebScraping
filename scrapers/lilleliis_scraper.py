import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers.base_scraper import ScraperStrategy


class LillelisScraper(ScraperStrategy):
    """Scraper for free amigurumi patterns from Lilleliis blog."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "Lilleliis"
        self.base_url = "https://www.lilleliis.com/amigurumi-crochet-freebies/"
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'lilleliis_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'lilleliis_dados.csv')

    def get_name(self) -> str:
        return self.name

    def _save_urls_to_file(self, urls: set):
        """Saves collected URLs to a text file."""
        os.makedirs(self.db_dir, exist_ok=True)
        with open(self.url_file_path, 'w', encoding='utf-8') as f:
            for url in sorted(urls):
                f.write(url + '\n')
        print(f"✓ URLs saved to: {self.url_file_path}")

    def _load_urls_from_file(self) -> set:
        """Loads URLs from the text file."""
        if not os.path.exists(self.url_file_path):
            return set()
        with open(self.url_file_path, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())

    def collect_recipe_urls(self) -> set:
        """Collects all recipe URLs from the freebies page."""
        print(f"\n--- Starting URL collection from {self.name} ---")
        all_urls = set()
        
        try:
            print(f"\nAccessing: {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(3)  # Wait for page load
            
            # Close any cookie banners or popups
            try:
                # Try to close cookie consent
                cookie_buttons = [
                    (By.XPATH, "//button[contains(text(), 'Accept')]"),
                    (By.XPATH, "//button[contains(text(), 'Skip')]"),
                    (By.CSS_SELECTOR, '.cookie-consent-close'),
                    (By.CSS_SELECTOR, '.popup-close'),
                ]
                for by, selector in cookie_buttons:
                    try:
                        button = self.driver.find_element(by, selector)
                        button.click()
                        time.sleep(1)
                        print("   ✓ Closed popup/banner")
                        break
                    except:
                        continue
            except:
                pass
            
            # Find all pattern links on the page
            # The page shows pattern cards with links
            link_selectors = [
                (By.CSS_SELECTOR, 'article a[href*="lilleliis.com/amigurumi-crochet-freebies/"]'),
                (By.CSS_SELECTOR, '.pattern-item a'),
                (By.CSS_SELECTOR, '.entry-content a[href*="/amigurumi-crochet-freebies/"]'),
                (By.XPATH, '//article//a[contains(@href, "/amigurumi-crochet-freebies/")]'),
                (By.XPATH, '//div[contains(@class, "entry-content")]//a[contains(@href, "/amigurumi-crochet-freebies/")]'),
            ]
            
            links = []
            for by, selector in link_selectors:
                try:
                    found_links = self.driver.find_elements(by, selector)
                    if found_links:
                        print(f"   Found {len(found_links)} links using: {selector}")
                        links.extend(found_links)
                        break
                except:
                    continue
            
            if not links:
                print("   ⚠ No links found with standard selectors, trying alternative approach...")
                # Try to find all links and filter
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, 'a')
                    for link in all_links:
                        try:
                            href = link.get_attribute('href')
                            if href and '/amigurumi-crochet-freebies/' in href and href != self.base_url:
                                links.append(link)
                        except:
                            continue
                    print(f"   Found {len(links)} links via filtering")
                except:
                    pass
            
            # Extract URLs
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href and href != self.base_url and href.startswith('http'):
                        # Exclude non-pattern pages
                        if not any(x in href for x in ['page/', '#', 'tag/', 'category/']):
                            all_urls.add(href)
                except:
                    continue
            
            print(f"\n✓ Total URLs collected: {len(all_urls)}")
            
        except Exception as e:
            print(f"   ✗ Error collecting URLs: {e}")
        
        return all_urls

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts recipe details from a pattern URL."""
        print(f"\nProcessing: {url}")
        
        try:
            self.driver.get(url)
            time.sleep(2)  # Wait for page load
            
            # Extract title
            titulo = "N/A"
            try:
                title_selectors = [
                    (By.CSS_SELECTOR, 'h1.entry-title'),
                    (By.CSS_SELECTOR, 'h1.post-title'),
                    (By.CSS_SELECTOR, 'article h1'),
                    (By.TAG_NAME, 'h1'),
                ]
                for by, selector in title_selectors:
                    try:
                        title_elem = self.driver.find_element(by, selector)
                        titulo = title_elem.text.strip()
                        if titulo:
                            break
                    except:
                        continue
            except:
                pass
            
            # Extract content (materiais + receita)
            materiais = "N/A"
            receita = "N/A"
            
            try:
                # Find the main content area
                content_selectors = [
                    (By.CSS_SELECTOR, '.entry-content'),
                    (By.CSS_SELECTOR, '.post-content'),
                    (By.CSS_SELECTOR, 'article .content'),
                    (By.CSS_SELECTOR, '.pattern-content'),
                ]
                
                content_elem = None
                for by, selector in content_selectors:
                    try:
                        content_elem = self.driver.find_element(by, selector)
                        if content_elem:
                            break
                    except:
                        continue
                
                if content_elem:
                    # Get all text from content
                    full_text = content_elem.text.strip()
                    
                    # Try to separate materials from instructions
                    text_lower = full_text.lower()
                    
                    # Find materials section
                    materials_keywords = [
                        'materials:', 'materials needed:', 'you will need:', 
                        'supplies:', 'what you need:', 'yarn:', 'materials and tools:'
                    ]
                    instructions_keywords = [
                        'instructions:', 'pattern:', 'how to:', 'directions:',
                        'abbreviations:', 'let\'s start:', 'start:'
                    ]
                    
                    materials_start = -1
                    instructions_start = -1
                    
                    for keyword in materials_keywords:
                        pos = text_lower.find(keyword)
                        if pos != -1:
                            materials_start = pos
                            break
                    
                    for keyword in instructions_keywords:
                        pos = text_lower.find(keyword)
                        if pos != -1:
                            instructions_start = pos
                            break
                    
                    # Extract sections
                    if materials_start != -1 and instructions_start != -1:
                        if materials_start < instructions_start:
                            # Materials come first
                            materiais = full_text[materials_start:instructions_start].strip()
                            receita = full_text[instructions_start:].strip()
                        else:
                            # Instructions come first
                            receita = full_text[materials_start:].strip()
                            materiais = full_text[:materials_start].strip()
                    elif materials_start != -1:
                        # Only materials found
                        materiais = full_text[materials_start:].strip()
                        receita = full_text
                    elif instructions_start != -1:
                        # Only instructions found
                        receita = full_text[instructions_start:].strip()
                        # Try to extract materials from the beginning
                        materiais = full_text[:instructions_start].strip() if instructions_start > 100 else "N/A"
                    else:
                        # No clear sections, use entire content
                        receita = full_text
                        materiais = "N/A"
                
            except Exception as e:
                print(f"   ⚠ Error extracting content: {e}")
            
            return {
                'titulo': titulo,
                'url': url,
                'materiais': materiais,
                'receita': receita,
                'origem': 'Lilleliis'
            }
            
        except Exception as e:
            print(f"   ✗ Error processing URL: {e}")
            return {
                'titulo': "ERROR",
                'url': url,
                'materiais': "ERROR",
                'receita': str(e),
                'origem': 'Lilleliis'
            }

    def _save_results_to_csv(self, results: list):
        """Saves scraping results to CSV."""
        results_dir = os.path.join(self.db_dir, 'resultados')
        os.makedirs(results_dir, exist_ok=True)
        
        df = pd.DataFrame(results)
        df.to_csv(self.csv_file_path, index=False, encoding='utf-8-sig')
        print(f"✓ Results saved to: {self.csv_file_path}")

    def run(self, args: dict):
        """Main orchestration method for the scraper."""
        print(f"\n{'='*60}")
        print(f"Starting {self.name} Scraper")
        print(f"{'='*60}")
        
        # Collect URLs
        force = args.get('force', False)
        update_urls_only = args.get('update_urls_only', False)
        
        if force or not os.path.exists(self.url_file_path):
            urls = self.collect_recipe_urls()
            if urls:
                self._save_urls_to_file(urls)
        else:
            print(f"\nLoading existing URLs from: {self.url_file_path}")
            urls = self._load_urls_from_file()
            print(f"✓ Loaded {len(urls)} URLs")
        
        if update_urls_only:
            print("\n✓ URL collection completed (--update-urls-only flag set)")
            return
        
        if not urls:
            print("\n✗ No URLs to process.")
            return
        
        # Process recipes
        print(f"\n{'='*60}")
        print(f"Processing {len(urls)} recipes...")
        print(f"{'='*60}")
        
        results = []
        for i, url in enumerate(sorted(urls), 1):
            print(f"\n[{i}/{len(urls)}]")
            details = self.extract_recipe_details(url)
            results.append(details)
            time.sleep(0.5)  # Delay between requests
        
        # Save results
        if results:
            self._save_results_to_csv(results)
        
        print(f"\n{'='*60}")
        print(f"✓ Scraping completed!")
        print(f"   Total recipes: {len(results)}")
        print(f"{'='*60}\n")
