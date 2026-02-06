import os
import time
import pandas as pd
import requests
from urllib.parse import urlparse
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
        self.images_dir = os.path.join('downloads', 'images', 'alwaysfreeamigurumi_images')
        
        # Create images directory if it doesn't exist
        os.makedirs(self.images_dir, exist_ok=True)

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

    def _download_image(self, image_url: str, pattern_slug: str) -> str:
        """Downloads an image and saves it locally with retry logic."""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not image_url or not image_url.startswith('http'):
                    return "N/A"
                
                # Create a safe filename from pattern slug
                parsed_url = urlparse(image_url)
                file_extension = os.path.splitext(parsed_url.path)[1] or '.jpg'
                # Clean the extension
                if '?' in file_extension:
                    file_extension = file_extension.split('?')[0]
                if not file_extension:
                    file_extension = '.jpg'
                    
                filename = f"{pattern_slug}{file_extension}"
                filepath = os.path.join(self.images_dir, filename)
                
                # Check if image already exists
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                    if file_size > 1000:  # At least 1KB
                        print(f"      Image already exists: {filename}")
                        return filepath
                    else:
                        # File exists but is too small, delete and retry
                        os.remove(filepath)
                        print(f"      Corrupted image found, re-downloading...")
                
                # Download the image with timeout
                print(f"      Downloading image (attempt {attempt + 1}/{max_retries})...")
                response = requests.get(
                    image_url, 
                    timeout=15,  # Increased timeout
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': self.base_url
                    },
                    stream=True  # Stream for large images
                )
                
                if response.status_code == 200:
                    # Save image
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # Verify file was saved correctly
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                        print(f"      ✓ Downloaded image: {filename} ({os.path.getsize(filepath)} bytes)")
                        return filepath
                    else:
                        print(f"      ⚠ Downloaded file too small, retrying...")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                else:
                    print(f"      Failed to download image: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return "N/A"
                    
            except requests.exceptions.Timeout:
                print(f"      ⚠ Download timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "N/A"
            except Exception as e:
                print(f"      Error downloading image: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "N/A"
        
        return "N/A"

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts details from a single recipe page with a more robust, section-aware approach."""
        print(f"\nProcessing: {url}")
        self.driver.get(url)
        time.sleep(3)  # Allow page to load
        
        # Scroll to load lazy-loaded images
        print("   Loading images...")
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        # Extract slug from URL for image naming
        pattern_slug = url.rstrip('/').split('/')[-1]

        recipe_data = {
            'titulo': '', 
            'url': url, 
            'imagem_url': 'N/A',
            'imagem_local': 'N/A',
            'materiais': '', 
            'abreviacoes': '', 
            'receita': '', 
            'origem': self.name
        }

        try:
            # 1. Flexible Title Extraction
            try:
                recipe_data['titulo'] = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            except NoSuchElementException:
                # Fallback to another common title element if h1 is not found
                recipe_data['titulo'] = self.driver.find_element(By.CLASS_NAME, "entry-title").text.strip()

            # 2. Extract main image with explicit wait
            try:
                print("   Extracting main image...")
                # Try to find the featured image with multiple selectors
                img_selectors = [
                    (By.CSS_SELECTOR, 'article img'),
                    (By.CSS_SELECTOR, '.entry-content img'),
                    (By.CSS_SELECTOR, '.wp-post-image'),
                    (By.CSS_SELECTOR, 'img[src*="alwaysfreeamigurumi"]'),
                    (By.TAG_NAME, 'img'),
                ]
                
                img_elem = None
                for by, selector in img_selectors:
                    try:
                        # Wait for image to be present
                        img_elem = WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located((by, selector))
                        )
                        
                        # Get image source
                        imagem_url = img_elem.get_attribute('src')
                        
                        # Skip small images, logos, icons, and placeholders
                        if imagem_url and not any(skip in imagem_url.lower() for skip in 
                                                   ['logo', 'icon', 'avatar', 'button', 'badge', '1x1']):
                            # Check if image has reasonable dimensions
                            try:
                                width = img_elem.get_attribute('width')
                                height = img_elem.get_attribute('height')
                                if width and height:
                                    w = int(width) if width.isdigit() else 0
                                    h = int(height) if height.isdigit() else 0
                                    # Skip very small images
                                    if w > 100 and h > 100:
                                        print(f"      Found image: {imagem_url[:80]}...")
                                        recipe_data['imagem_url'] = imagem_url
                                        # Download the image
                                        recipe_data['imagem_local'] = self._download_image(imagem_url, pattern_slug)
                                        if recipe_data['imagem_local'] != "N/A":
                                            break
                                else:
                                    # No dimensions specified, try downloading anyway
                                    print(f"      Found image: {imagem_url[:80]}...")
                                    recipe_data['imagem_url'] = imagem_url
                                    recipe_data['imagem_local'] = self._download_image(imagem_url, pattern_slug)
                                    if recipe_data['imagem_local'] != "N/A":
                                        break
                            except:
                                # If we can't check dimensions, try downloading
                                print(f"      Found image: {imagem_url[:80]}...")
                                recipe_data['imagem_url'] = imagem_url
                                recipe_data['imagem_local'] = self._download_image(imagem_url, pattern_slug)
                                if recipe_data['imagem_local'] != "N/A":
                                    break
                    except TimeoutException:
                        continue
                    except Exception as e:
                        continue
                
                if recipe_data['imagem_local'] == "N/A" and recipe_data['imagem_url'] == "N/A":
                    print("      ⚠ No suitable image found")
                    
            except Exception as e:
                print(f"      Error extracting image: {e}")

            # 3. Robust Content Extraction
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

        max_pages = args.get('max_pages') or 50  # Default to 10 if None
        urls_to_process = self.collect_recipe_urls(max_pages=max_pages)
        
        if not urls_to_process:
            print(f"{self.name} scraper: No recipe URLs found. Halting.")
            return

        with open(self.url_file_path, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_to_process)):
                f.write(f"{url}\n")

        print(f"\nStarting detail extraction for {len(urls_to_process)} recipes...")
        all_recipes_data = [self.extract_recipe_details(url) for url in urls_to_process]
        
        if all_recipes_data:
            df = pd.DataFrame(all_recipes_data, columns=['titulo', 'url', 'imagem_url', 'imagem_local', 'materiais', 'abreviacoes', 'receita', 'origem'])
            df.to_csv(self.csv_file_path, sep=';', index=False, encoding='utf-8-sig')
            print(f"\n✓ Data saved successfully to '{self.csv_file_path}'")
        else:
            print("No recipe data was extracted.")
