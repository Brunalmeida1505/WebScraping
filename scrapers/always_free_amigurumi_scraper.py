import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrapers.base_scraper import ScraperStrategy

class AlwaysFreeAmigurumiScraper(ScraperStrategy):
    """Scraper for recipes from alwaysfreeamigurumi.com."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "AlwaysFreeAmigurumi"
        self.base_url = "https://www.alwaysfreeamigurumi.com/"
        self.db_dir = "db"
        self.url_file_path = os.path.join(self.db_dir, "always_free_amigurumi_urls.txt")
        self.csv_file_path = os.path.join(self.db_dir, "resultados", "always_free_amigurumi_data.csv")

    def get_name(self) -> str:
        return self.name

    def collect_recipe_urls(self, max_pages=50) -> set:
        """Collects recipe URLs from the site by iterating through numbered pages."""
        print(f"Starting URL collection for {self.name}...")
        recipe_urls = set()

        # Handle cookie consent on the main page first
        self.driver.get(self.base_url)
        time.sleep(2)
        try:
            cookie_accept_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Accept')]"))
            )
            cookie_accept_button.click()
            print("Accepted cookie consent.")
            time.sleep(1)
        except Exception:
            print("Cookie consent banner not found or already accepted.")

        # Iterate through numbered pages
        for page_num in range(1, max_pages + 1):
            page_url = f"{self.base_url}page/{page_num}/"
            print(f"--- Analyzing page {page_num}: {page_url} ---")
            
            try:
                self.driver.get(page_url)
                time.sleep(2)

                # If page number is in title, it's a valid page. If not, it might be a 404 redirect.
                if page_num > 1 and str(page_num) not in self.driver.title:
                    print("Page not found or redirected. Finishing URL collection.")
                    break
                
                # Scroll down to load all content
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                for _ in range(3):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height

                articles = self.driver.find_elements(By.TAG_NAME, "article")
                if not articles and page_num > 1:
                    print("No articles found on this page. Finishing URL collection.")
                    break
                
                page_links = set()
                for article in articles:
                    try:
                        link_element = article.find_element(By.CSS_SELECTOR, "h2.entry-title a")
                        href = link_element.get_attribute("href")
                        # Additional filtering based on user's example
                        if href and not any(x in href.lower() for x in ['category', 'tag', 'author']):
                            page_links.add(href)
                    except NoSuchElementException:
                        continue
                
                if not page_links:
                    print("No new recipe links found on this page.")
                else:
                    print(f"Found {len(page_links)} recipe links on this page.")
                    recipe_urls.update(page_links)

            except Exception as e:
                print(f"  [!] An unexpected error occurred while processing page {page_num}: {e}")
                break
        
        print(f"\nFound {len(recipe_urls)} unique recipe URLs after scanning up to {max_pages} pages.")
        return recipe_urls

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts details from a single recipe page with a more robust, section-aware approach."""
        self.driver.get(url)
        time.sleep(2)  # Allow page to load

        recipe_data = {
            'titulo': '', 'url': url, 'materiais': '', 'abreviacoes': '', 'receita': '', 'origem': self.name
        }

        try:
            # 1. Flexible Title Extraction
            try:
                recipe_data['titulo'] = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            except NoSuchElementException:
                # Fallback to another common title element if h1 is not found
                recipe_data['titulo'] = self.driver.find_element(By.CLASS_NAME, "entry-title").text.strip()

            # 2. Robust Content Extraction
            try:
                content_container = self.driver.find_element(By.CLASS_NAME, "entry-content")
            except NoSuchElementException:
                print(f"  [!] Page {url} does not have an '.entry-content' div. Skipping.")
                return recipe_data

            # Define keywords for section identification
            materials_kw = ['materials', 'you will need', 'supplies']
            abbreviations_kw = ['abbreviations', 'stitches used']
            recipe_kw = ['pattern', 'instruction', 'head', 'body', 'arm', 'leg', 'ear', 'tail', 'round 1']

            materials_text = []
            abbreviations_text = []
            recipe_text = []

            # Find all major block elements within the content area
            all_elements = content_container.find_elements(By.XPATH, "./*")
            
            # Default to 'recipe' section, as instructions often start without a clear header
            current_section = 'recipe' 

            for element in all_elements:
                # Skip empty or non-visible elements
                try:
                    text = element.text.strip()
                    if not text:
                        continue
                except Exception:
                    continue 

                lower_text = text.lower()
                tag_name = element.tag_name.lower()
                is_heading = tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

                # Determine section based on heading text
                if is_heading:
                    if any(kw in lower_text for kw in materials_kw):
                        current_section = 'materials'
                    elif any(kw in lower_text for kw in abbreviations_kw):
                        current_section = 'abbreviations'
                    # More likely to be part of the recipe itself, so check for recipe keywords
                    elif any(kw in lower_text for kw in recipe_kw):
                        current_section = 'recipe'

                # Append text to the currently active section
                if current_section == 'materials':
                    materials_text.append(text)
                elif current_section == 'abbreviations':
                    abbreviations_text.append(text)
                elif current_section == 'recipe':
                    recipe_text.append(text)
                else:
                    # Fallback for text that doesn't fall under a detected section, likely part of the recipe
                    recipe_text.append(text)

            # Join the collected texts
            recipe_data['materiais'] = "\n".join(materials_text).strip()
            recipe_data['abreviacoes'] = "\n".join(abbreviations_text).strip()
            recipe_data['receita'] = "\n".join(recipe_text).strip()

        except NoSuchElementException as e:
            print(f"  [!] Error processing {url}: Could not find a required element - {e}")
        except Exception as e:
            print(f"  [!] An unexpected error occurred while processing {url}: {e}")

        return recipe_data

    def run(self, args: dict):
        os.makedirs(os.path.join(self.db_dir, "resultados"), exist_ok=True)

        urls_to_process = self.collect_recipe_urls(max_pages=args.get('max_pages', 10))
        
        if not urls_to_process:
            print(f"{self.name} scraper: No recipe URLs found. Halting.")
            return

        with open(self.url_file_path, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_to_process)):
                f.write(f"{url}\n")

        print(f"\nStarting detail extraction for {len(urls_to_process)} recipes...")
        all_recipes_data = [self.extract_recipe_details(url) for url in urls_to_process]
        
        if all_recipes_data:
            df = pd.DataFrame(all_recipes_data, columns=['titulo', 'url', 'materiais', 'abreviacoes', 'receita', 'origem'])
            df.to_csv(self.csv_file_path, sep=';', index=False, encoding='utf-8-sig')
            print(f"\n✓ Data saved successfully to '{self.csv_file_path}'")
        else:
            print("No recipe data was extracted.")
