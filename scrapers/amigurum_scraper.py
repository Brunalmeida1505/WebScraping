import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from scrapers.base_scraper import ScraperStrategy

class AmigurumScraper(ScraperStrategy):
    """Scraper for recipes from amigurum.com."""

    def __init__(self, driver):
        super().__init__(driver)
        self.wait = WebDriverWait(driver, 10)
        self.name = "Amigurum"
        self.base_url = "https://amigurum.com"
        self.db_dir = "db"
        self.url_file_path = os.path.join(self.db_dir, "amigurum_urls.txt")
        self.csv_file_path = os.path.join(self.db_dir, "resultados", "amigurum_dados.csv")

    def get_name(self) -> str:
        return self.name

    def collect_recipe_urls(self, max_pages=None) -> set:
        """Collects recipe URLs by navigating through numbered pages."""
        print(f"Starting URL collection for {self.name}...")
        recipe_urls = set()

        page_num = 1
        consecutive_empty_pages = 0
        consecutive_no_new_recipes = 0
        max_consecutive_no_new = 3  # Stop after 3 pages with no new recipes
        
        while True:
            if max_pages and page_num > max_pages:
                print(f"   Reached maximum page limit ({max_pages})")
                break
            
            # Build URL for current page
            if page_num == 1:
                page_url = self.base_url
            else:
                page_url = f"{self.base_url}/page/{page_num}/"
            
            print(f"   Accessing page {page_num}: {page_url}")
            
            try:
                self.driver.get(page_url)
                time.sleep(2)
                
                # Handle cookie consent on first page
                if page_num == 1:
                    try:
                        cookie_selectors = [
                            (By.XPATH, '//button[contains(text(), "Accept")]'),
                            (By.XPATH, '//button[contains(text(), "Aceitar")]'),
                            (By.ID, "cookie-accept"),
                        ]
                        for by, selector in cookie_selectors:
                            try:
                                cookie_btn = WebDriverWait(self.driver, 3).until(
                                    EC.element_to_be_clickable((by, selector))
                                )
                                cookie_btn.click()
                                print("   Cookie consent accepted.")
                                time.sleep(1)
                                break
                            except:
                                continue
                    except:
                        pass
                
                # Check if page exists (404 or redirect to homepage)
                current_url = self.driver.current_url
                if page_num > 1 and (current_url == self.base_url or current_url == f"{self.base_url}/"):
                    print(f"   Page {page_num} redirected to home. Reached end of pagination.")
                    break
                
                # Collect recipe links from current page
                links = self.driver.find_elements(
                    By.XPATH, 
                    "//a[contains(@href, '/20') and contains(@href, '.html')]"
                )
                
                page_recipes = set()
                for link in links:
                    href = link.get_attribute("href")
                    if href and href.startswith(self.base_url) and '.html' in href:
                        # Remove comment anchors (#comment-xxx)
                        if '#' in href:
                            href = href.split('#')[0]
                        page_recipes.add(href)
                
                # Check if we found new recipes
                if page_recipes:
                    new_recipes = page_recipes - recipe_urls
                    
                    if new_recipes:
                        recipe_urls.update(page_recipes)
                        print(f"   Page {page_num}: Found {len(page_recipes)} recipes ({len(new_recipes)} new) | Total: {len(recipe_urls)}")
                        consecutive_empty_pages = 0
                        consecutive_no_new_recipes = 0
                    else:
                        recipe_urls.update(page_recipes)
                        consecutive_no_new_recipes += 1
                        print(f"   Page {page_num}: Found {len(page_recipes)} recipes (0 new - all duplicates) | Total: {len(recipe_urls)}")
                        
                        if consecutive_no_new_recipes >= max_consecutive_no_new:
                            print(f"   ⚠ No new recipes found for {max_consecutive_no_new} consecutive pages. Stopping collection.")
                            break
                else:
                    consecutive_empty_pages += 1
                    consecutive_no_new_recipes += 1
                    print(f"   Page {page_num}: No recipes found")
                    
                    if consecutive_empty_pages >= 2:
                        print(f"   No content found for {consecutive_empty_pages} consecutive pages. Ending collection.")
                        break
                
                page_num += 1
                
            except Exception as e:
                print(f"   Error accessing page {page_num}: {e}")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 2:
                    break
                page_num += 1

        print(f"\n✓ URL collection finished: {len(recipe_urls)} recipes found across {page_num - 1} pages.")
        return recipe_urls

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts details from a single recipe page."""
        print(f"   Processing: {url}")
        self.driver.get(url)
        time.sleep(2)

        recipe_data = {
            'titulo': '',
            'url': url,
            'materiais': '',
            'receita': '',
            'origem': self.name
        }

        try:
            # Extract title
            try:
                title_element = self.wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                recipe_data['titulo'] = title_element.text.strip()
            except TimeoutException:
                recipe_data['titulo'] = "Título não encontrado"

            # Extract main content
            try:
                # Try to find the main article content
                content_selectors = [
                    (By.CLASS_NAME, "entry-content"),
                    (By.CLASS_NAME, "post-content"),
                    (By.TAG_NAME, "article"),
                ]
                
                content_element = None
                for by, selector in content_selectors:
                    try:
                        content_element = self.driver.find_element(by, selector)
                        break
                    except NoSuchElementException:
                        continue

                if content_element:
                    # Get all text from paragraphs and lists
                    all_text = []
                    
                    # Get text from paragraphs
                    paragraphs = content_element.find_elements(By.TAG_NAME, "p")
                    for p in paragraphs:
                        text = p.text.strip()
                        if text:
                            all_text.append(text)
                    
                    # Get text from lists (often used for materials)
                    lists = content_element.find_elements(By.TAG_NAME, "ul")
                    for ul in lists:
                        items = ul.find_elements(By.TAG_NAME, "li")
                        for item in items:
                            text = item.text.strip()
                            if text:
                                all_text.append(f"• {text}")

                    full_text = "\n".join(all_text)
                    
                    # Try to separate materials and pattern
                    materials_section = []
                    pattern_section = []
                    is_pattern = False
                    
                    for line in all_text:
                        lower_line = line.lower()
                        
                        # Check if we're entering the pattern section
                        if any(keyword in lower_line for keyword in ['pattern', 'abbreviations', 'r 1:', 'r1:', 'round 1']):
                            is_pattern = True
                        
                        # Check if we're in materials section
                        if any(keyword in lower_line for keyword in ['materials', 'yarn:', 'hook:', 'you will need']):
                            is_pattern = False
                        
                        if is_pattern:
                            pattern_section.append(line)
                        else:
                            materials_section.append(line)
                    
                    recipe_data['materiais'] = "\n".join(materials_section)
                    recipe_data['receita'] = "\n".join(pattern_section)
                    
                    # If separation failed, put everything in recipe
                    if not recipe_data['receita']:
                        recipe_data['receita'] = full_text
                else:
                    recipe_data['receita'] = "Conteúdo não encontrado"

            except Exception as e:
                print(f"      Error extracting content: {e}")
                recipe_data['receita'] = "Erro ao extrair conteúdo"

        except Exception as e:
            print(f"      Unexpected error: {e}")
            recipe_data['receita'] = "Erro ao processar página"

        return recipe_data

    def run(self, args: dict):
        """Main orchestration method for Amigurum scraper."""
        os.makedirs(os.path.join(self.db_dir, "resultados"), exist_ok=True)

        is_force_mode = args.get('force', False)
        max_scrolls = args.get('max_pages')  # None if not specified = collect all

        # Load existing URLs
        urls_locais = set()
        if os.path.exists(self.url_file_path):
            with open(self.url_file_path, 'r', encoding='utf-8') as f:
                urls_locais = set(line.strip() for line in f if line.strip())

        # Collect URLs from site
        if max_scrolls:
            print(f"\nAmigurum scraper: Collecting URLs (max {max_scrolls} pages)...")
        else:
            print(f"\nAmigurum scraper: Collecting ALL URLs from all pages...")
        
        urls_remotas = self.collect_recipe_urls(max_pages=max_scrolls)

        # Save all URLs
        with open(self.url_file_path, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_remotas)):
                f.write(f"{url}\n")
        print(f"✓ URLs saved to '{self.url_file_path}'")

        if args.get('update_urls_only'):
            print("Amigurum scraper: URLs updated. Halting as requested.")
            return

        # Determine which URLs to process
        if is_force_mode:
            urls_to_extract = sorted(list(urls_remotas))
            print(f"\nForce mode: Processing all {len(urls_to_extract)} recipes...")
        else:
            urls_to_extract = sorted(list(urls_remotas - urls_locais))
            if not urls_to_extract:
                print("Amigurum scraper: No new recipes to extract.")
                return
            print(f"\nAmigurum scraper: Processing {len(urls_to_extract)} new recipes...")

        # Extract recipe details
        all_recipes_data = []
        for i, url in enumerate(urls_to_extract):
            print(f"[{i+1}/{len(urls_to_extract)}]")
            recipe_data = self.extract_recipe_details(url)
            if recipe_data and recipe_data.get('titulo'):
                all_recipes_data.append(recipe_data)

        # Save to CSV
        if all_recipes_data:
            df = pd.DataFrame(all_recipes_data, columns=['titulo', 'url', 'materiais', 'receita', 'origem'])
            
            if is_force_mode or not os.path.exists(self.csv_file_path):
                df.to_csv(self.csv_file_path, sep=';', index=False, encoding='utf-8-sig')
            else:
                df.to_csv(self.csv_file_path, mode='a', sep=';', index=False, encoding='utf-8-sig', header=False)
            
            print(f"\n✓ Successfully processed {len(all_recipes_data)} recipes.")
            print(f"✓ Data saved to '{self.csv_file_path}'")
        else:
            print("No recipe data was extracted.")
