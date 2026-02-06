import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers.base_scraper import ScraperStrategy


class MenagerieScraper(ScraperStrategy):
    """Scraper for free amigurumi patterns from A Menagerie of Stitches blog."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "A Menagerie of Stitches"
        self.base_url = "https://amenagerieofstitchesblog.com/category/free-patterns/"
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'menagerie_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'menagerie_dados.csv')

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
        """Collects all recipe URLs from the blog with pagination."""
        print(f"\n--- Starting URL collection from {self.name} ---")
        all_urls = set()
        page = 1
        max_pages = 100  # Safety limit
        consecutive_empty = 0
        max_consecutive_empty = 3
        
        while page <= max_pages:
            # Construct page URL
            if page == 1:
                page_url = self.base_url
            else:
                page_url = f"{self.base_url}page/{page}/"
            
            print(f"\nPage {page}: {page_url}")
            
            try:
                self.driver.get(page_url)
                time.sleep(2)  # Wait for page load
                
                # Find all post links
                # Try multiple selectors
                link_selectors = [
                    (By.CSS_SELECTOR, 'article h2 a'),
                    (By.CSS_SELECTOR, 'article .entry-title a'),
                    (By.CSS_SELECTOR, '.post-title a'),
                    (By.XPATH, '//article//h2//a'),
                    (By.XPATH, '//article//a[contains(@class, "entry-title")]'),
                ]
                
                links = []
                for by, selector in link_selectors:
                    try:
                        links = self.driver.find_elements(by, selector)
                        if links:
                            print(f"   Found links using: {selector}")
                            break
                    except:
                        continue
                
                if not links:
                    consecutive_empty += 1
                    print(f"   No results found on page {page}.")
                    if consecutive_empty >= max_consecutive_empty:
                        print(f"   ⚠ {max_consecutive_empty} consecutive empty pages. Stopping.")
                        break
                    page += 1
                    continue
                
                # Extract URLs
                page_urls = set()
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and href not in all_urls:
                            page_urls.add(href)
                    except:
                        continue
                
                if not page_urls:
                    consecutive_empty += 1
                    print(f"   No new URLs found on page {page}.")
                    if consecutive_empty >= max_consecutive_empty:
                        print(f"   ⚠ {max_consecutive_empty} consecutive pages with no new URLs. Stopping.")
                        break
                else:
                    consecutive_empty = 0  # Reset counter
                
                all_urls.update(page_urls)
                print(f"   Found {len(page_urls)} new URLs (Total: {len(all_urls)})")
                
                # Check for "Next" button or pagination end
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, '.nav-previous a, .next a')
                    if not next_button:
                        print("   ✓ No next button found. Reached last page.")
                        break
                except:
                    # Try to detect if we're on the last page
                    try:
                        pagination = self.driver.find_element(By.CSS_SELECTOR, '.pagination, .nav-links')
                        if not pagination:
                            break
                    except:
                        # If no pagination found after several pages, we might be done
                        if page > 5:
                            break
                
                page += 1
                time.sleep(1)  # Delay between pages
                
            except Exception as e:
                print(f"   Error on page {page}: {e}")
                consecutive_empty += 1
                if consecutive_empty >= max_consecutive_empty:
                    break
                page += 1
        
        print(f"\n✓ Total URLs collected: {len(all_urls)} from {page-1} pages")
        return all_urls

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts recipe details from a blog post URL."""
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
                # Try to find the main content area
                content_selectors = [
                    (By.CSS_SELECTOR, '.entry-content'),
                    (By.CSS_SELECTOR, '.post-content'),
                    (By.CSS_SELECTOR, 'article .content'),
                    (By.XPATH, '//article//div[contains(@class, "content")]'),
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
                    # Look for common section headers
                    text_lower = full_text.lower()
                    
                    # Find materials section
                    materials_keywords = ['materials:', 'materials needed:', 'you will need:', 'supplies:', 'what you need:']
                    instructions_keywords = ['instructions:', 'pattern:', 'how to:', 'directions:']
                    
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
                        # Both sections found
                        materiais = full_text[materials_start:instructions_start].strip()
                        receita = full_text[instructions_start:].strip()
                    elif materials_start != -1:
                        # Only materials found
                        materiais = full_text[materials_start:].strip()
                        receita = full_text
                    elif instructions_start != -1:
                        # Only instructions found
                        receita = full_text[instructions_start:].strip()
                        materiais = full_text[:instructions_start].strip()
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
                'origem': 'A Menagerie of Stitches'
            }
            
        except Exception as e:
            print(f"   ✗ Error processing URL: {e}")
            return {
                'titulo': "ERROR",
                'url': url,
                'materiais': "ERROR",
                'receita': str(e),
                'origem': 'A Menagerie of Stitches'
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
