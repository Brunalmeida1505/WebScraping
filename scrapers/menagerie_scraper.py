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


class MenagerieScraper(ScraperStrategy):
    """Scraper for free amigurumi patterns from A Menagerie of Stitches blog."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "A Menagerie of Stitches"
        self.base_url = "https://amenagerieofstitchesblog.com/category/free-patterns/"
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'menagerie_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'menagerie_dados.csv')
        self.images_dir = os.path.join('downloads', 'images', 'menagerie_images')
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
                        'Referer': 'https://amenagerieofstitchesblog.com/'
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
            time.sleep(2)
            
            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Extract pattern slug from URL for image filename
            pattern_slug = url.rstrip('/').split('/')[-1]
            
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
            
            # Image extraction - get first valid image from content
            imagem_url = "N/A"
            imagem_local = "N/A"
            
            print(f"   Searching for first content image...")
            
            try:
                # Try to find images within the content area first
                content_selectors = [
                    (By.CSS_SELECTOR, '.entry-content img'),
                    (By.CSS_SELECTOR, '.post-content img'),
                    (By.CSS_SELECTOR, 'article .content img'),
                    (By.XPATH, '//article//div[contains(@class, "content")]//img'),
                ]
                
                content_images = []
                for by, selector in content_selectors:
                    try:
                        content_images = self.driver.find_elements(by, selector)
                        if content_images:
                            print(f"   Found {len(content_images)} images in content area")
                            break
                    except:
                        continue
                
                # If no content images found, try all images
                if not content_images:
                    content_images = self.driver.find_elements(By.TAG_NAME, 'img')
                    print(f"   Found {len(content_images)} total images")
                
                # Try each image until we find a valid one
                for img in content_images:
                    try:
                        # Get src from different possible attributes
                        src = (img.get_attribute('data-lazy-src') or 
                               img.get_attribute('data-src') or 
                               img.get_attribute('data-srcset') or
                               img.get_attribute('src'))
                        
                        if not src or src.startswith('data:'):
                            continue
                        
                        # Handle srcset - get the first URL
                        if ' ' in src:
                            src = src.split(' ')[0].split(',')[0]
                        
                        # Handle relative URLs
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = 'https://amenagerieofstitchesblog.com' + src
                        
                        # Skip common non-pattern images
                        skip_keywords = ['logo', 'icon', 'avatar', 'gravatar', 'badge', 'banner', 'social', 'pixel', 'tracking', 'header', 'footer']
                        src_lower = src.lower()
                        img_class_lower = (img.get_attribute('class') or '').lower()
                        img_alt_lower = (img.get_attribute('alt') or '').lower()
                        
                        # Skip if matches any skip keyword
                        if any(keyword in src_lower or keyword in img_class_lower or keyword in img_alt_lower for keyword in skip_keywords):
                            continue
                        
                        # Get image dimensions
                        try:
                            # Scroll to image
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", img)
                            time.sleep(0.3)
                            
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
                            
                            # If dimensions are still 0, try attributes
                            if not width or not height:
                                try:
                                    width = int(img.get_attribute('width') or 0)
                                    height = int(img.get_attribute('height') or 0)
                                except:
                                    width = 0
                                    height = 0
                            
                            # Skip very small images (likely icons/thumbnails)
                            if not width or not height or width < 200 or height < 200:
                                print(f"   Skipping small image: {width}x{height}")
                                continue
                            
                            print(f"   Found valid image: {width}x{height}")
                            
                            # This is our first valid image, download it
                            imagem_url = src
                            imagem_local = self._download_image(imagem_url, pattern_slug)
                            
                            if imagem_local != "N/A":
                                break  # Successfully downloaded, stop looking
                            
                        except Exception as e:
                            print(f"   Error checking image dimensions: {e}")
                            continue
                            
                    except Exception as e:
                        continue
                
                if imagem_local == "N/A":
                    print("   ⚠ Could not find/download a valid image")
                    
            except Exception as e:
                print(f"   Error extracting images: {e}")
            
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
                'imagem_url': imagem_url,
                'imagem_local': imagem_local,
                'materiais': materiais,
                'receita': receita,
                'origem': 'A Menagerie of Stitches'
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
                'origem': 'A Menagerie of Stitches'
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
