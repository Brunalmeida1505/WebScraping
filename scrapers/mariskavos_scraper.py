import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from scrapers.base_scraper import ScraperStrategy

class MariskavosScraper(ScraperStrategy):
    """Scraper for recipes from mariskavos.nl."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "Mariskavos"
        self.base_url = "https://www.mariskavos.nl"
        self.db_dir = "db"
        self.url_file_path = os.path.join(self.db_dir, "mariskavos_urls.txt")
        self.csv_file_path = os.path.join(self.db_dir, "resultados", "mariskavos_dados.csv")

    def get_name(self) -> str:
        return self.name

    def collect_recipe_urls(self, max_pages=5) -> set:
        """Collects recipe URLs from the site by navigating through pages."""
        print(f"Starting URL collection for {self.name}...")
        recipe_urls = set()

        for page_num in range(1, max_pages + 1):
            page_url = f"{self.base_url}/page/{page_num}/" if page_num > 1 else self.base_url
            print(f"--- Analyzing page {page_num}: {page_url} ---")
            
            try:
                self.driver.get(page_url)
                time.sleep(3)
                links = self.driver.find_elements(By.TAG_NAME, "a")

                for link in links:
                    href = link.get_attribute("href")
                    if (href and self.base_url in href and 'free-' in href and 'pattern' in href and 
                        not any(ignore in href for ignore in ['/page/', '#', '?'])):
                        recipe_urls.add(href.rstrip('/'))
            
            except Exception as e:
                print(f"  [!] Error accessing page {page_num}: {e}")
                continue

        return recipe_urls

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts details from a single recipe page."""
        self.driver.get(url)
        time.sleep(3)
        
        recipe_data = {
            'titulo': '', 'url': url, 'materiais': '', 'receita': '', 'origem': self.name
        }
        
        try:
            recipe_data['titulo'] = self.driver.find_element(By.CLASS_NAME, "entry-title").text
            content_container = self.driver.find_element(By.CLASS_NAME, "entry-content")
            
            # This logic is specific and brittle, adapted from original script
            materials_text = []
            recipe_text = []
            # Simplified extraction logic
            paragraphs = content_container.find_elements(By.TAG_NAME, "p")
            is_recipe_section = False
            for p in paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                lower_text = text.lower()
                
                if 'materials' in lower_text:
                    materials_text.append(text)
                elif 'abbreviations' in lower_text or 'pattern' in lower_text or 'instructions' in lower_text:
                    is_recipe_section = True
                    recipe_text.append(text)
                elif is_recipe_section:
                    recipe_text.append(text)
                else:
                    materials_text.append(text)
                    
            recipe_data['materiais'] = "\n".join(materials_text)
            recipe_data['receita'] = "\n".join(recipe_text)

        except NoSuchElementException as e:
            print(f"  [!] Error processing {url}: Could not find element - {e}")
        except Exception as e:
            print(f"  [!] An unexpected error occurred while processing {url}: {e}")
            
        return recipe_data

    def run(self, args: dict):
        os.makedirs(os.path.join(self.db_dir, "resultados"), exist_ok=True)

        urls_to_process = self.collect_recipe_urls(max_pages=args.get('max_pages', 5))
        
        if not urls_to_process:
            print(f"{self.name} scraper: No recipe URLs found. Halting.")
            return

        with open(self.url_file_path, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_to_process)):
                f.write(f"{url}\n")

        print(f"\nStarting detail extraction for {len(urls_to_process)} recipes...")
        all_recipes_data = [self.extract_recipe_details(url) for url in urls_to_process]
        
        if all_recipes_data:
            df = pd.DataFrame(all_recipes_data, columns=['titulo', 'url', 'materiais', 'receita', 'origem'])
            df.to_csv(self.csv_file_path, sep=';', index=False, encoding='utf-8-sig')
            print(f"\n✓ Data saved successfully to '{self.csv_file_path}'")
        else:
            print("No recipe data was extracted.")
