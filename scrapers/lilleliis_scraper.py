import os
import time
import pandas as pd
import requests
from urllib.parse import urlparse
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
        self.images_dir = os.path.join('downloads', 'images', 'lilleliis_images')
        os.makedirs(self.images_dir, exist_ok=True)

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
                        'Referer': 'https://www.lilleliis.com/'
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
            time.sleep(2)
            
            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Extract pattern slug from URL for image filename
            pattern_slug = url.rstrip('/').split('/')[-1]
            
            # Extract title first (needed for image matching)
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
            
            # Image extraction with keyword matching
            imagem_url = "N/A"
            imagem_local = "N/A"
            
            print(f"   Searching for images for: {titulo}")
            
            # Extract keywords from title
            stop_words = ['pattern', 'free', 'crochet', 'amigurumi', 'the', 'a', 'an', 'and', 'or', 'for', 'with', 'tutorial']
            title_words = [w.lower() for w in titulo.split() if w.lower() not in stop_words and len(w) > 3]
            print(f"   Keywords from title: {title_words[:5]}")
            
            try:
                all_imgs = self.driver.find_elements(By.TAG_NAME, 'img')
                print(f"   Found {len(all_imgs)} total images")
                
                candidates = []
                
                for img in all_imgs:
                    try:
                        # Get src from different possible attributes (priority order)
                        src = (img.get_attribute('data-lazy-src') or 
                               img.get_attribute('data-src') or 
                               img.get_attribute('data-srcset') or
                               img.get_attribute('src'))
                        
                        # Skip placeholder images
                        if not src or src.startswith('data:'):
                            continue
                        
                        # Handle srcset - get the largest image
                        if ' ' in src:
                            src = src.split(' ')[0].split(',')[-1]
                        
                        # Handle relative URLs
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://www.lilleliis.com' + src
                        
                        # Skip common non-pattern images
                        skip_keywords = ['cookieyes', 'cookie-', 'favicon', 'icon-', 'avatar', 'button', 'badge', 'banner-', 'social-', 'pixel', 'tracking']
                        src_lower = src.lower()
                        img_class_lower = (img.get_attribute('class') or '').lower()
                        
                        # Filter logos by class
                        if 'logo' in img_class_lower or 'header-logo' in img_class_lower:
                            if debug_count <= 3:
                                print(f"      → Skipped: logo class found")
                            continue
                        
                        if any(keyword in src_lower for keyword in skip_keywords):
                            if debug_count <= 3:
                                print(f"      → Skipped: skip keyword found")
                            continue
                        
                        # Get image dimensions - try to trigger lazy load first
                        try:
                            # Scroll to image to trigger lazy loading
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                            time.sleep(0.3)
                            
                            # Wait for image to load
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
                            if (not width or not height):
                                width = int(img.get_attribute('width') or 0)
                                height = int(img.get_attribute('height') or 0)
                            
                            # Skip very small images (thumbnails, icons)
                            if not width or not height or width < 80 or height < 80:
                                if debug_count <= 3:
                                    print(f"      → Skipped: dimensions {width}x{height} too small")
                                continue
                            
                            if debug_count <= 3:
                                print(f"      → Valid candidate: {width}x{height}, area={width*height}")
                            
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
                            'height': height,
                            'title': img_title,
                            'alt': img_alt
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
                    
                    imagem_url = candidate['src']
                    imagem_local = self._download_image(imagem_url, pattern_slug)
                    
                    if imagem_local != "N/A":
                        break
                
                if imagem_local == "N/A":
                    print("   ⚠ Could not download any suitable image")
            except Exception as e:
                print(f"   Error extracting images: {e}")
            
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
                'imagem_url': imagem_url,
                'imagem_local': imagem_local,
                'materiais': materiais,
                'receita': receita,
                'origem': 'Lilleliis'
            }
            
        except Exception as e:
            print(f"   ✗ Error processing URL: {e}")
            return {
                'titulo': "ERROR",
                'url': url,
                'imagem_url': "ERROR",
                'imagem_local': "ERROR",
                'materiais': "ERROR",
                'receita': str(e),
                'origem': 'Lilleliis'
            }

    def _save_results_to_csv(self, results: list):
        """Saves scraping results to CSV."""
        results_dir = os.path.join(self.db_dir, 'resultados')
        os.makedirs(results_dir, exist_ok=True)
        
        df = pd.DataFrame(results)
        
        # Reorder columns to match standard format
        columns_order = ['titulo', 'url', 'imagem_url', 'imagem_local', 'materiais', 'receita', 'origem']
        df = df[columns_order]
        
        df.to_csv(self.csv_file_path, index=False, encoding='utf-8-sig', sep=';')
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
