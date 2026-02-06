import os
import time
import pandas as pd
import requests
from urllib.parse import urlparse
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
        self.images_dir = os.path.join('downloads', 'images', 'mariskavos_images')
        os.makedirs(self.images_dir, exist_ok=True)

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

    def _download_image(self, image_url: str, pattern_slug: str) -> str:
        """Downloads an image and saves it locally with retry logic."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if not image_url or not image_url.startswith('http'):
                    return "N/A"
                
                parsed_url = urlparse(image_url)
                file_extension = os.path.splitext(parsed_url.path)[1] or '.jpg'
                file_extension = file_extension.split('?')[0] if '?' in file_extension else file_extension
                file_extension = file_extension if file_extension else '.jpg'
                    
                filename = f"{pattern_slug}{file_extension}"
                filepath = os.path.join(self.images_dir, filename)
                
                if os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                    if file_size > 1000:
                        print(f"      Image already exists: {filename}")
                        return filepath
                    else:
                        os.remove(filepath)
                        print(f"      Corrupted image found, re-downloading...")
                
                print(f"      Downloading image (attempt {attempt + 1}/{max_retries})...")
                response = requests.get(
                    image_url, 
                    timeout=15,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': 'https://www.mariskavos.nl/'
                    },
                    stream=True
                )
                
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
                        print(f"      ✓ Downloaded image: {filename} ({os.path.getsize(filepath)} bytes)")
                        return filepath
                    else:
                        print(f"      ⚠ Downloaded file too small, retrying...")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            continue
                else:
                    print(f"      Failed to download image: HTTP {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return "N/A"
                    
            except requests.exceptions.Timeout:
                print(f"      ⚠ Download timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return "N/A"
            except Exception as e:
                print(f"      Error downloading image: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return "N/A"
        
        return "N/A"

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts details from a single recipe page."""
        print(f"\nProcessing: {url}")
        
        self.driver.get(url)
        time.sleep(2)
        
        # Scroll to trigger lazy loading
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(1)
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        # Extract pattern slug from URL for image filename
        pattern_slug = url.rstrip('/').split('/')[-1]
        
        recipe_data = {
            'titulo': '', 'url': url, 'imagem_url': 'N/A', 'imagem_local': 'N/A',
            'materiais': '', 'receita': '', 'origem': self.name
        }
        
        try:
            recipe_data['titulo'] = self.driver.find_element(By.CLASS_NAME, "entry-title").text
            print(f"   Title: {recipe_data['titulo']}")
            
            # Image extraction with keyword matching
            print(f"   Searching for images...")
            
            # Extract keywords from title
            stop_words = ['pattern', 'free', 'crochet', 'amigurumi', 'the', 'a', 'an', 'and', 'or', 'for', 'with', 'tutorial']
            title_words = [w.lower() for w in recipe_data['titulo'].split() if w.lower() not in stop_words and len(w) > 3]
            print(f"   Keywords from title: {title_words[:5]}")
            
            try:
                all_imgs = self.driver.find_elements(By.TAG_NAME, 'img')
                print(f"   Found {len(all_imgs)} total images")
                
                candidates = []
                
                for img in all_imgs:
                    try:
                        # Get src from different possible attributes
                        src = (img.get_attribute('data-lazy-src') or 
                               img.get_attribute('data-src') or 
                               img.get_attribute('data-srcset') or
                               img.get_attribute('src'))
                        
                        if not src or src.startswith('data:'):
                            continue
                        
                        # Handle srcset - get the largest image
                        if ' ' in src:
                            src = src.split(' ')[0].split(',')[-1]
                        
                        # Handle relative URLs
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://www.mariskavos.nl' + src
                        
                        # Skip common non-pattern images
                        skip_keywords = ['cookieyes', 'cookie-', 'favicon', 'icon-', 'avatar', 'button', 'badge', 'banner-', 'social-', 'pixel', 'tracking']
                        src_lower = src.lower()
                        img_class_lower = (img.get_attribute('class') or '').lower()
                        
                        # Filter logos by class
                        if 'logo' in img_class_lower or 'header-logo' in img_class_lower:
                            continue
                        
                        if any(keyword in src_lower for keyword in skip_keywords):
                            continue
                        
                        # Scroll image into view to trigger lazy loading
                        try:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                            time.sleep(0.3)
                        except:
                            pass
                        
                        # Get image dimensions
                        try:
                            width = self.driver.execute_script("""
                                var img = arguments[0];
                                if (img.complete && img.naturalWidth > 0) {
                                    return img.naturalWidth;
                                }
                                return img.width || 0;
                            """, img)
                            
                            height = self.driver.execute_script("""
                                var img = arguments[0];
                                if (img.complete && img.naturalHeight > 0) {
                                    return img.naturalHeight;
                                }
                                return img.height || 0;
                            """, img)
                            
                            # If dimensions are still 0, try to get from attributes
                            if not width or not height:
                                width = int(img.get_attribute('width') or 0)
                                height = int(img.get_attribute('height') or 0)
                            
                            # Skip very small images
                            if not width or not height or width < 80 or height < 80:
                                continue
                            
                            area = width * height
                        except:
                            continue
                        
                        # Get image attributes for matching
                        img_title = (img.get_attribute('title') or '').lower()
                        img_alt = (img.get_attribute('alt') or '').lower()
                        img_class = (img.get_attribute('class') or '').lower()
                        
                        # Calculate match score
                        match_score = 0
                        for word in title_words:
                            if word in img_title:
                                match_score += 5
                            if word in img_alt:
                                match_score += 5
                            if word in src.lower():
                                match_score += 2
                        
                        # Check parent context
                        try:
                            parent_class = img.find_element(By.XPATH, './..').get_attribute('class') or ''
                            if 'entry-content' in parent_class or 'post-content' in parent_class or 'article' in parent_class:
                                match_score += 3
                        except:
                            pass
                        
                        # Bonus for specific classes
                        if 'featured' in img_class or 'main' in img_class or 'pattern' in img_class:
                            match_score += 2
                        
                        candidates.append({
                            'src': src,
                            'area': area,
                            'match_score': match_score,
                            'width': width,
                            'height': height
                        })
                    except:
                        continue
                
                # Sort by match score first, then by area
                candidates.sort(key=lambda x: (x['match_score'], x['area']), reverse=True)
                
                print(f"   Found {len(candidates)} valid image candidates")
                if candidates:
                    print(f"   Top candidate: {candidates[0]['width']}x{candidates[0]['height']}, match_score={candidates[0]['match_score']}")
                
                # Try top 15 candidates
                for i, candidate in enumerate(candidates[:15]):
                    # Skip small images unless they have good match score
                    if candidate['area'] < 5000 and candidate['match_score'] < 3:
                        continue
                    
                    print(f"   Trying candidate {i+1}: {candidate['width']}x{candidate['height']}, score={candidate['match_score']}")
                    
                    recipe_data['imagem_url'] = candidate['src']
                    recipe_data['imagem_local'] = self._download_image(recipe_data['imagem_url'], pattern_slug)
                    
                    if recipe_data['imagem_local'] != "N/A":
                        break
                
                if recipe_data['imagem_local'] == "N/A":
                    print("   ⚠ Could not download any suitable image")
            except Exception as e:
                print(f"   Error extracting images: {e}")
            
            # Extract content
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

        max_pages = args.get('max_pages') or 5  # Default to 5 if None
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
            df = pd.DataFrame(all_recipes_data, columns=['titulo', 'url', 'imagem_url', 'imagem_local', 'materiais', 'receita', 'origem'])
            df.to_csv(self.csv_file_path, sep=';', index=False, encoding='utf-8-sig')
            print(f"\n✓ Data saved successfully to '{self.csv_file_path}'")
        else:
            print("No recipe data was extracted.")
