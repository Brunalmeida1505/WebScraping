import os
import time
import pandas as pd
import requests
from urllib.parse import urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from dotenv import load_dotenv

from scrapers.base_scraper import ScraperStrategy

# Load environment variables from .env file
load_dotenv()


class AmigurumiTodayScraper(ScraperStrategy):
    """Scraper for free amigurumi patterns from Amigurumi Today with image download support."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "Amigurumi Today"
        self.base_url = "https://amigurumi.today/"
        self.login_url = "https://amigurumi.today/sign-in/"
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'amigurumitoday_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'amigurumitoday_dados.csv')
        self.images_dir = os.path.join('downloads', 'images', 'amigurumitoday_images')
        os.makedirs(self.images_dir, exist_ok=True)
        self.is_logged_in = False

    def get_name(self) -> str:
        return self.name

    def _login(self, email: str = None, password: str = None):
        """Performs login to Amigurumi Today."""
        if self.is_logged_in:
            print("   Already logged in")
            return True
        
        print(f"\n--- Performing login to {self.name} ---")
        
        # Get credentials from environment or use provided ones
        if not email:
            email = os.environ.get('AMIGURUMITODAY_EMAIL')
        if not password:
            password = os.environ.get('AMIGURUMITODAY_PASSWORD')
        
        if not email or not password:
            print("   ⚠ Login credentials not provided!")
            print("   Please set AMIGURUMITODAY_EMAIL and AMIGURUMITODAY_PASSWORD environment variables")
            print("   Or create a file 'AMIGURUMITODAY_CREDENCIAIS.txt' with email and password")
            
            # Try to read from credentials file
            cred_file = 'AMIGURUMITODAY_CREDENCIAIS.txt'
            if os.path.exists(cred_file):
                try:
                    with open(cred_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        if len(lines) >= 2:
                            email = lines[0].strip()
                            password = lines[1].strip()
                            print(f"   ✓ Credentials loaded from {cred_file}")
                except:
                    pass
        
        if not email or not password:
            print("   ✗ Cannot proceed without credentials")
            return False
        
        try:
            print(f"   Accessing login page: {self.login_url}")
            
            # Mascarar webdriver para evitar detecção do Cloudflare
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            self.driver.get(self.login_url)
            
            # Aguardar a página e o JavaScript carregarem completamente
            # O site usa uma SPA (Single Page Application) que precisa de tempo para inicializar
            print("   Waiting for page to load and Cloudflare check to complete...")
            time.sleep(8)  # Tempo maior para o Cloudflare liberar e o JavaScript carregar
            
            # Aguardar explicitamente pelo container da aplicação aparecer
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.ID, "amt-app"))
                )
                print("   ✓ Application loaded (Cloudflare passed)")
            except:
                print("   ⚠ Application container not found - Cloudflare may be blocking")
                # Salvar screenshot para debug
                try:
                    self.driver.save_screenshot("debug_cloudflare.png")
                    print("   Screenshot saved: debug_cloudflare.png")
                except:
                    pass
                return False
            
            time.sleep(3)  # Tempo adicional para elementos renderizarem
            
            # PASSO 1: Primeiro precisamos clicar no botão "Continue with email and password"
            # O site usa uma SPA (Single Page Application) que mostra opções primeiro
            print("   Looking for 'Continue with email and password' button...")
            
            continue_button_selectors = [
                (By.XPATH, '//button[contains(text(), "Continue with email and password")]'),
                (By.CSS_SELECTOR, 'button.amt-btn.amt-btn-primary'),
                (By.XPATH, '//button[@class="amt-btn amt-btn-primary"]'),
            ]
            
            continue_button = None
            for by, selector in continue_button_selectors:
                try:
                    continue_button = WebDriverWait(self.driver, 12).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if continue_button and continue_button.is_displayed():
                        print(f"   ✓ Found button: '{continue_button.text}'")
                        break
                except Exception as e:
                    print(f"   Trying next selector...")
                    continue
            
            if not continue_button:
                print("   ✗ Could not find 'Continue with email and password' button")
                # Salvar screenshot para debug
                try:
                    self.driver.save_screenshot("debug_no_button.png")
                    print("   Screenshot saved: debug_no_button.png")
                    # Também salvar o HTML
                    with open("debug_page_source.html", "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    print("   Page source saved: debug_page_source.html")
                except:
                    pass
                return False
            
            print("   Clicking 'Continue with email and password' button...")
            continue_button.click()
            time.sleep(3)  # Aguardar o formulário aparecer
            
            # PASSO 2: Agora procurar pelos campos de email que aparecem dinamicamente
            print("   Looking for email field...")
            email_selectors = [
                (By.CSS_SELECTOR, 'input[type="email"]'),
                (By.CSS_SELECTOR, 'input[name="email"]'),
                (By.CSS_SELECTOR, 'input#email'),
                (By.XPATH, '//input[@type="email"]'),
            ]
            
            email_field = None
            for by, selector in email_selectors:
                try:
                    email_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if email_field:
                        print(f"   ✓ Found email field")
                        break
                except:
                    continue
            
            if not email_field:
                print("   ✗ Could not find email field after clicking button")
                # Salvar screenshot para debug
                try:
                    self.driver.save_screenshot("debug_no_email_field.png")
                    print("   Screenshot saved: debug_no_email_field.png")
                except:
                    pass
                return False
            
            print("   Filling email...")
            email_field.clear()
            email_field.send_keys(email)
            time.sleep(1)
            
            # PASSO 3: Procurar e preencher o campo de senha
            print("   Looking for password field...")
            password_selectors = [
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.CSS_SELECTOR, 'input[name="password"]'),
                (By.CSS_SELECTOR, 'input#password'),
                (By.XPATH, '//input[@type="password"]'),
            ]
            
            password_field = None
            for by, selector in password_selectors:
                try:
                    password_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    if password_field:
                        print(f"   ✓ Found password field")
                        break
                except:
                    continue
            
            if not password_field:
                print("   ✗ Could not find password field")
                return False
            
            print("   Filling password...")
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(1)
            
            # PASSO 4: Procurar e clicar no botão de submit (pode ser diferente do primeiro botão)
            print("   Looking for submit button...")
            button_selectors = [
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.CSS_SELECTOR, 'input[type="submit"]'),
                (By.CSS_SELECTOR, 'button.amt-btn-primary'),
                (By.XPATH, '//button[contains(text(), "Sign in")]'),
                (By.XPATH, '//button[contains(text(), "Sign In")]'),
                (By.XPATH, '//button[contains(text(), "Log in")]'),
                (By.XPATH, '//button[contains(text(), "Continue")]'),
            ]
            
            login_button = None
            for by, selector in button_selectors:
                try:
                    login_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if login_button:
                        print(f"   ✓ Found submit button")
                        break
                except:
                    continue
            
            if not login_button:
                print("   ⚠ Could not find submit button, trying Enter key...")
                # Tentar enviar Enter no campo de senha
                password_field.send_keys(Keys.RETURN)
                time.sleep(6)
            else:
                print("   Clicking submit button...")
                login_button.click()
                time.sleep(6)  # Wait for login to complete
            
            # Verify login success by checking if we're redirected or if user menu appears
            try:
                # Check if we're no longer on the login page
                current_url = self.driver.current_url
                if 'sign-in' not in current_url.lower() and 'login' not in current_url.lower():
                    print("   ✓ Login successful!")
                    self.is_logged_in = True
                    return True
                else:
                    print("   ⚠ Still on login page - login may have failed")
                    return False
            except:
                print("   ⚠ Could not verify login status")
                return False
                
        except Exception as e:
            print(f"   ✗ Login error: {e}")
            return False

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
                        'Referer': 'https://amigurumi.today/'
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

    def collect_recipe_urls(self) -> set:
        """Collects all recipe URLs from all pages with pagination."""
        print(f"\n--- Starting URL collection from {self.name} ---")
        
        # Perform login first
        if not self._login():
            print("   ✗ Failed to login. Cannot collect URLs.")
            return set()
        
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
                time.sleep(3)  # Wait for page load
                
                # Scroll to load dynamic content
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
                time.sleep(1)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
                # Find all article links
                link_selectors = [
                    (By.CSS_SELECTOR, 'article h2 a'),
                    (By.CSS_SELECTOR, '.entry-title a'),
                    (By.CSS_SELECTOR, 'h2 a'),
                    (By.XPATH, '//article//h2//a'),
                    (By.XPATH, '//h2//a'),
                ]
                
                links = []
                for by, selector in link_selectors:
                    try:
                        links = self.driver.find_elements(by, selector)
                        if links:
                            print(f"   Found {len(links)} links using: {selector}")
                            break
                    except:
                        continue
                
                if not links:
                    # Try alternative: get all links and filter
                    print("   Trying alternative link collection...")
                    try:
                        all_links = self.driver.find_elements(By.TAG_NAME, 'a')
                        for link in all_links:
                            try:
                                href = link.get_attribute('href')
                                text = link.text.strip()
                                # Links with text that look like pattern titles
                                if href and text and len(text) > 10 and 'amigurumi.today/' in href:
                                    links.append(link)
                            except:
                                continue
                        if links:
                            print(f"   Found {len(links)} links via filtering")
                    except:
                        pass
                
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
                            # Filter out non-pattern URLs
                            if 'amigurumi.today/' in href and not any(x in href for x in [
                                '/tag/', '/category/', '/page/', '/premium-crochet-patterns',
                                '/crochet-tips-and-tricks', '/tutorials', '/how-to-access'
                            ]):
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
        """Extracts recipe details from a pattern URL, excluding comments."""
        print(f"\nProcessing: {url}")
        
        try:
            # Ensure we're logged in before extracting individual recipe pages
            if not getattr(self, 'is_logged_in', False):
                print("   Not logged in; attempting to login before extraction...")
                if not self._login():
                    print("   ✗ Could not login before extracting recipe. Skipping this URL.")
                    return {
                        'titulo': 'N/A',
                        'url': url,
                        'imagem_url': 'N/A',
                        'imagem_local': 'N/A',
                        'materiais': 'N/A',
                        'receita': 'N/A',
                        'origem': 'Amigurumi Today'
                    }

            self.driver.get(url)
            time.sleep(4)  # Increased wait time for page load
            
            # Scroll the page to trigger lazy-loaded images
            print("   Loading images...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)  # Additional time for images to load
            
            # Extract slug from URL for image naming
            pattern_slug = url.rstrip('/').split('/')[-1]
            
            # Extract title
            titulo = "N/A"
            try:
                title_selectors = [
                    (By.CSS_SELECTOR, 'h1.entry-title'),
                    (By.CSS_SELECTOR, 'h1'),
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
            
            # Extract main image with explicit wait
            imagem_url = "N/A"
            imagem_local = "N/A"
            try:
                print("   Extracting main image...")
                # Try to find the featured image with multiple selectors
                img_selectors = [
                    (By.CSS_SELECTOR, 'article img'),
                    (By.CSS_SELECTOR, '.entry-content img'),
                    (By.CSS_SELECTOR, '.wp-post-image'),
                    (By.CSS_SELECTOR, 'img[src*="amigurumi"]'),
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
                                        # Download the image
                                        imagem_local = self._download_image(imagem_url, pattern_slug)
                                        if imagem_local != "N/A":
                                            break
                                else:
                                    # No dimensions specified, try downloading anyway
                                    print(f"      Found image: {imagem_url[:80]}...")
                                    imagem_local = self._download_image(imagem_url, pattern_slug)
                                    if imagem_local != "N/A":
                                        break
                            except:
                                # If we can't check dimensions, try downloading
                                print(f"      Found image: {imagem_url[:80]}...")
                                imagem_local = self._download_image(imagem_url, pattern_slug)
                                if imagem_local != "N/A":
                                    break
                    except TimeoutException:
                        continue
                    except Exception as e:
                        continue
                
                if imagem_local == "N/A" and imagem_url == "N/A":
                    print("      ⚠ No suitable image found")
                    
            except Exception as e:
                print(f"      Error extracting image: {e}")
            
            # Extract content (materiais + receita) following specific rules
            materiais = "N/A"
            receita = "N/A"
            
            try:
                print("   Extracting materials and recipe...")
                
                # Find the main content area
                content_elem = None
                content_selectors = [
                    (By.CSS_SELECTOR, '.entry-content'),
                    (By.CSS_SELECTOR, '.post-content'),
                    (By.CSS_SELECTOR, 'article'),
                ]
                
                for by, selector in content_selectors:
                    try:
                        content_elem = self.driver.find_element(by, selector)
                        if content_elem:
                            print(f"      Found content area with: {selector}")
                            break
                    except:
                        continue
                
                if not content_elem:
                    print("      ⚠ Content area not found")
                else:
                    # EXTRAÇÃO DE MATERIAIS
                    # Começa em <p> com texto "To crochet the amigurumi..." até antes de "Skill level"
                    try:
                        print("      Extracting materials (from 3rd <p> until before 'Skill level')...")
                        materials_paragraphs = []

                        # Encontrar todos os parágrafos dentro do conteúdo
                        all_paragraphs = content_elem.find_elements(By.TAG_NAME, 'p')

                        # Start from the 3rd <p> tag (index 2) if available
                        start_index = 2 if len(all_paragraphs) >= 3 else 0
                        for p in all_paragraphs[start_index:]:
                            try:
                                p_text = p.text.strip()
                            except:
                                p_text = ''

                            # Stop if we reach a paragraph that contains 'Skill level'
                            if p_text and 'skill level' in p_text.lower():
                                print("         Found 'Skill level', stopping materials")
                                break

                            # Skip empty paragraphs
                            if p_text:
                                materials_paragraphs.append(p_text)

                        if materials_paragraphs:
                            materiais = '\n\n'.join(materials_paragraphs)
                            print(f"      ✓ Materials extracted: {len(materiais)} characters")
                        else:
                            print("      ⚠ No materials found starting at 3rd <p>")
                            materiais = "N/A"

                    except Exception as e:
                        print(f"      Error extracting materials: {e}")
                        materiais = "N/A"
                    
                    # EXTRAÇÃO DE RECEITA
                    # Começa na primeira <h2> até a última <p>
                    try:
                        print("      Extracting recipe...")
                        recipe_parts = []
                        
                        # Encontrar todos os elementos h2, h3, h4, p após o primeiro h2
                        all_h2 = content_elem.find_elements(By.TAG_NAME, 'h2')
                        
                        if all_h2:
                            # Pegar o primeiro h2 como início
                            first_h2 = all_h2[0]
                            first_h2_text = first_h2.text.strip()
                            
                            # Pular h2 que não são títulos de receita
                            skip_h2 = ['related', 'share', 'comment', 'leave a reply', 'about']
                            if not any(skip in first_h2_text.lower() for skip in skip_h2):
                                recipe_parts.append(f"## {first_h2_text}")
                                print(f"         Found recipe start: {first_h2_text[:50]}...")
                            
                            # Agora coletar TODOS os elementos após o primeiro h2 até o fim
                            # Usar JavaScript para pegar todos os elementos
                            script = """
                            var content = arguments[0];
                            var h2 = arguments[1];
                            var elements = [];
                            var started = false;
                            
                            // Pegar todos os filhos do content
                            var children = content.querySelectorAll('h2, h3, h4, p, ul, ol');
                            
                            for (var i = 0; i < children.length; i++) {
                                var elem = children[i];
                                
                                // Começar quando encontrar o primeiro h2
                                if (!started && elem === h2) {
                                    started = true;
                                    continue;  // Pular o próprio h2 (já adicionamos)
                                }
                                
                                if (started) {
                                    var text = elem.innerText.trim();
                                    
                                    // Parar em seções de comentários
                                    if (text.toLowerCase().includes('leave a reply') || 
                                        text.toLowerCase().includes('leave a comment')) {
                                        break;
                                    }
                                    
                                    if (text) {
                                        var tag = elem.tagName.toLowerCase();
                                        elements.push({tag: tag, text: text});
                                    }
                                }
                            }
                            
                            return elements;
                            """
                            
                            elements = self.driver.execute_script(script, content_elem, first_h2)
                            
                            print(f"         Found {len(elements)} recipe elements")
                            
                            for elem in elements:
                                tag = elem['tag']
                                text = elem['text']
                                
                                # Formatar de acordo com o tipo de elemento
                                if tag == 'h2':
                                    recipe_parts.append(f"\n## {text}")
                                elif tag == 'h3':
                                    recipe_parts.append(f"\n### {text}")
                                elif tag == 'h4':
                                    recipe_parts.append(f"\n#### {text}")
                                elif tag in ['ul', 'ol']:
                                    recipe_parts.append(f"\n{text}")
                                else:  # p
                                    recipe_parts.append(text)
                            
                            if recipe_parts:
                                receita = '\n\n'.join(recipe_parts)
                                print(f"      ✓ Recipe extracted: {len(receita)} characters")
                            else:
                                print("      ⚠ No recipe content found")
                                receita = "N/A"
                        else:
                            print("      ⚠ No h2 tags found in content")
                            # Fallback: pegar todo o conteúdo em texto
                            receita = content_elem.text.strip() if content_elem.text else "N/A"
                    
                    except Exception as e:
                        print(f"      Error extracting recipe: {e}")
                        import traceback
                        traceback.print_exc()
                        receita = "N/A"
                
            except Exception as e:
                print(f"   ⚠ Error extracting content: {e}")
                import traceback
                traceback.print_exc()
            
            return {
                'titulo': titulo,
                'url': url,
                'imagem_url': imagem_url,
                'imagem_local': imagem_local,
                'materiais': materiais,
                'receita': receita,
                'origem': 'Amigurumi Today'
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
                'origem': 'Amigurumi Today'
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
        
        # Make sure we're logged in before processing recipes
        print(f"\n{'='*60}")
        print("Ensuring login before processing recipes...")
        print(f"{'='*60}")
        
        if not self._login():
            print("\n✗ Failed to login. Cannot extract recipe details.")
            print("   Recipe extraction requires authentication.")
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
        print(f"   Images saved to: {self.images_dir}")
        print(f"{'='*60}\n")
