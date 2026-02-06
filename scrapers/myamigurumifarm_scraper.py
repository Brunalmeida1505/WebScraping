import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers.base_scraper import ScraperStrategy


class MyAmigurumiFarmScraper(ScraperStrategy):
    """Scraper for free amigurumi patterns from My Amigurumi Farm."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "My Amigurumi Farm"
        self.base_url = "https://www.myamigurumifarm.com/free-crochet-patterns"
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'myamigurumifarm_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'myamigurumifarm_dados.csv')

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

    def _scroll_to_load_all_content(self):
        """Scrolls down the page to trigger infinite scroll loading."""
        print("   Scrolling to load all content...")
        
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_change_count = 0
        max_no_change = 5  # Stop after 5 scrolls with no new content
        
        while no_change_count < max_no_change:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for content to load
            
            # Calculate new scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                no_change_count += 1
                print(f"   No new content ({no_change_count}/{max_no_change})")
            else:
                no_change_count = 0
                print(f"   Page height: {last_height} -> {new_height}")
            
            last_height = new_height
        
        print("   ✓ Finished loading all content")

    def collect_recipe_urls(self) -> set:
        """Collects all recipe URLs from the page with infinite scroll."""
        print(f"\n--- Starting URL collection from {self.name} ---")
        all_urls = set()
        
        try:
            print(f"\nAccessing: {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(3)  # Initial page load
            
            # Close any cookie banners or popups
            try:
                cookie_buttons = [
                    (By.XPATH, "//button[contains(text(), 'Accept')]"),
                    (By.XPATH, "//button[contains(text(), 'Got it')]"),
                    (By.XPATH, "//button[contains(text(), 'OK')]"),
                    (By.CSS_SELECTOR, '.cookie-close'),
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
            
            # Scroll to load all content
            self._scroll_to_load_all_content()
            
            # Find all pattern links
            link_selectors = [
                (By.CSS_SELECTOR, 'article a[href*="myamigurumifarm.com"]'),
                (By.CSS_SELECTOR, '.post-title a'),
                (By.CSS_SELECTOR, 'h2 a'),
                (By.CSS_SELECTOR, '.entry-title a'),
                (By.XPATH, '//article//a[contains(@href, "myamigurumifarm.com")]'),
            ]
            
            links = []
            for by, selector in link_selectors:
                try:
                    found_links = self.driver.find_elements(by, selector)
                    if found_links:
                        print(f"   Found {len(found_links)} links using: {selector}")
                        links = found_links
                        break
                except:
                    continue
            
            if not links:
                print("   ⚠ No links found with standard selectors, trying alternative...")
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, 'a')
                    for link in all_links:
                        try:
                            href = link.get_attribute('href')
                            if href and 'myamigurumifarm.com' in href and 'free-crochet-patterns' not in href:
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
                        excluded = ['category/', 'tag/', '#', 'author/', 'page/', 'shop', 'contact', 'about']
                        if not any(x in href for x in excluded):
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
            
            # Site uses Wix and loads content dynamically - need longer wait
            time.sleep(5)  # Wait for dynamic content to load
            
            # Scroll down to ensure all content is loaded
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Extract title
            titulo = "N/A"
            try:
                title_selectors = [
                    (By.CSS_SELECTOR, 'h1'),
                    (By.XPATH, '//h1'),
                    (By.CSS_SELECTOR, '[data-testid="post-title"]'),
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
                # Wix sites use different structure - try to get all text from body
                # First try to find the main content container
                content_selectors = [
                    (By.CSS_SELECTOR, '[data-testid="post-content"]'),
                    (By.CSS_SELECTOR, '.blog-post-description'),
                    (By.CSS_SELECTOR, 'article'),
                    (By.XPATH, '//article'),
                    (By.TAG_NAME, 'body'),
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
                    
                    # If content is too short, it probably didn't load
                    if len(full_text) < 100:
                        print(f"   ⚠ Content too short ({len(full_text)} chars), trying alternative extraction")
                        # Try getting all paragraphs
                        try:
                            paragraphs = self.driver.find_elements(By.TAG_NAME, 'p')
                            full_text = '\n\n'.join([p.text for p in paragraphs if p.text.strip()])
                        except:
                            pass
                    
                    # Try to separate materials from instructions
                    text_lower = full_text.lower()
                    
                    # Find materials section
                    materials_keywords = [
                        'tools & materials:', 'tools & materials', 'materials:', 
                        'materials needed:', 'you will need:', 'supplies:', 
                        'what you need:', 'yarn:', 'materials and tools:',
                        'materials & tools:'
                    ]
                    instructions_keywords = [
                        'instructions:', 'pattern:', 'how to:', 'directions:',
                        'abbreviations:', 'let\'s start:', 'start:', 'body:',
                        'r 1', 'rnd 1', 'round 1', 'row 1'
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
                            receita = full_text[instructions_start:].strip()
                            materiais = full_text[:instructions_start].strip()
                    elif materials_start != -1:
                        # Only materials found, extract section
                        materiais = full_text[materials_start:].strip()
                        # Use a portion as receita
                        receita = full_text
                    elif instructions_start != -1:
                        # Only instructions found
                        receita = full_text[instructions_start:].strip()
                        # Try to extract materials from the beginning
                        materiais = full_text[:instructions_start].strip() if instructions_start > 100 else "N/A"
                    else:
                        # No clear sections found
                        if len(full_text) > 200:
                            # Has content, use it all
                            receita = full_text
                            materiais = "See recipe content"
                        else:
                            receita = full_text if full_text else "N/A"
                            materiais = "N/A"
                
            except Exception as e:
                print(f"   ⚠ Error extracting content: {e}")
            
            return {
                'titulo': titulo,
                'url': url,
                'materiais': materiais,
                'receita': receita,
                'origem': 'My Amigurumi Farm'
            }
            
        except Exception as e:
            print(f"   ✗ Error processing URL: {e}")
            return {
                'titulo': "ERROR",
                'url': url,
                'materiais': "ERROR",
                'receita': str(e),
                'origem': 'My Amigurumi Farm'
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
