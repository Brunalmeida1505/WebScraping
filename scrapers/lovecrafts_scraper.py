import os
import time
import getpass
import pandas as pd
import pdfplumber
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from scrapers.base_scraper import ScraperStrategy

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path, override=True)  # override=True to overwrite existing env vars
except ImportError:
    pass  # python-dotenv not installed, will use environment variables or prompt

class LovecraftsScraper(ScraperStrategy):
    """Scraper for recipes from lovecrafts.com (requires login and PDF download)."""

    def __init__(self, driver):
        super().__init__(driver)
        self.wait = WebDriverWait(driver, 10)
        self.name = "Lovecrafts"
        self.login_url = "https://www.lovecrafts.com/en-gb/account/auth/sign-in"
        self.search_url = 'https://www.lovecrafts.com/en-gb/search?q=free%20amigurumi'
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'lovecrafts_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'lovecrafts_dados.csv')
        self.download_dir = os.path.join(os.getcwd(), "downloads", "pdfs", "lovecrafts")
        self.is_logged_in = False

    def get_name(self) -> str:
        return self.name

    def _setup_download_dir(self):
        """Creates the download directory if it doesn't exist."""
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            print(f"✓ Download directory created: {self.download_dir}")

    def _handle_cookie_banner(self):
        """Attempts to close cookie consent banner."""
        print("Checking for cookie consent banner...")
        accept_selectors = [
            (By.ID, "onetrust-accept-btn-handler"),
            (By.XPATH, '//button[contains(text(), "Accept")]'),
            (By.XPATH, '//button[contains(text(), "Accept All")]'),
            (By.XPATH, '//button[contains(text(), "I agree")]'),
        ]
        
        for by, selector in accept_selectors:
            try:
                element = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((by, selector))
                )
                element.click()
                print("✓ Cookie banner closed.")
                time.sleep(1)
                return True
            except (TimeoutException, NoSuchElementException):
                continue
        
        print("Cookie banner not found or already accepted.")
        return False

    def _perform_login(self, email: str, password: str) -> bool:
        """Performs login to Lovecrafts."""
        print(f"\n--- Starting login process ---")
        print(f"Accessing login page: {self.login_url}")
        self.driver.get(self.login_url)
        time.sleep(2)

        self._handle_cookie_banner()

        print("Filling login form...")
        try:
            # Email field
            email_field = self.wait.until(EC.visibility_of_element_located((By.ID, "email")))
            email_field.clear()
            email_field.send_keys(email)
            time.sleep(0.5)
            print(f"   ✓ Email entered: {email}")
            
            # Password field
            password_field = self.wait.until(EC.visibility_of_element_located((By.ID, "password")))
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)
            print(f"   ✓ Password entered")
            
            # Submit button
            submit_button = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//button[@type="submit" and contains(., "Sign In & Continue")]')
            ))
            print("   Clicking login button...")
            submit_button.click()
            time.sleep(1)
            
            # Wait for redirect after login or check for error messages
            try:
                # Check if login was successful by waiting for URL change
                WebDriverWait(self.driver, 15).until(EC.url_changes(self.login_url))
                print("✓ Login successful.")
                self.is_logged_in = True
                return True
            except TimeoutException:
                # Check if there's an error message on the page
                try:
                    error_element = self.driver.find_element(By.XPATH, '//*[contains(@class, "error") or contains(@class, "alert")]')
                    error_msg = error_element.text
                    print(f"✗ Login failed: {error_msg}")
                except NoSuchElementException:
                    # Check current URL to see if we're still on login page
                    current_url = self.driver.current_url
                    if self.login_url in current_url:
                        print("✗ Login failed: Still on login page after 15 seconds.")
                        print("   Possible reasons:")
                        print("   - Incorrect email or password")
                        print("   - Account locked or requires verification")
                        print("   - Site might require additional verification (CAPTCHA, 2FA)")
                    else:
                        print(f"✓ Login appears successful (redirected to: {current_url})")
                        self.is_logged_in = True
                        return True
                return False
            
        except TimeoutException as e:
            print(f"✗ Login error: Element not found - {e}")
            print("   The login page structure might have changed.")
            return False
        except Exception as e:
            print(f"✗ Login error: {e}")
            return False

    def collect_recipe_urls(self) -> set:
        """Collects all recipe URLs from search results with pagination."""
        if not self.is_logged_in:
            print("✗ Cannot collect URLs: Not logged in.")
            return set()

        print(f"\n--- Starting URL collection ---")
        print(f"Accessing search page: {self.search_url}")
        self.driver.get(self.search_url)
        time.sleep(2)
        
        recipe_urls = set()
        page_num = 1
        
        while True:
            print(f"Collecting URLs from page {page_num}...")
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//ul[contains(@class, 'products')]"))
                )
                
                product_links = self.driver.find_elements(By.XPATH, "//ul[contains(@class, 'products')]/li//a")
                page_urls = set([link.get_attribute('href') for link in product_links if link.get_attribute('href')])
                new_urls = page_urls - recipe_urls
                recipe_urls.update(new_urls)
                print(f"   Found {len(new_urls)} new recipes on this page.")
                
                # Try to click "Next" button
                try:
                    next_button = self.driver.find_element(By.XPATH, '//a[@aria-label="Next"]')
                    if next_button.is_displayed() and next_button.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                        time.sleep(0.3)
                        next_button.click()
                        page_num += 1
                        time.sleep(2)
                    else:
                        print("✓ Pagination ended (Next button disabled).")
                        break
                except NoSuchElementException:
                    print("✓ Pagination ended (Next button not found).")
                    break
                    
            except TimeoutException:
                print("✗ Product list did not load. Ending URL collection.")
                break
        
        print(f"\n✓ URL collection finished: {len(recipe_urls)} recipes found.")
        return recipe_urls

    def _wait_for_download_complete(self, timeout=30):
        """Waits for a PDF download to complete and returns the file path."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            in_progress = [f for f in os.listdir(self.download_dir) if f.endswith('.crdownload')]
            if not in_progress:
                pdf_files = [os.path.join(self.download_dir, f) 
                            for f in os.listdir(self.download_dir) if f.lower().endswith('.pdf')]
                if pdf_files:
                    latest_file = max(pdf_files, key=os.path.getmtime)
                    if time.time() - os.path.getmtime(latest_file) < 10:
                        print(f"   ✓ Download complete: {os.path.basename(latest_file)}")
                        return latest_file
            time.sleep(0.3)  # Check more frequently
        
        print("   ✗ Download timeout exceeded.")
        return None

    def _parse_pdf(self, pdf_path: str) -> dict:
        """Extracts content from a PDF and separates into title, abbreviations, and recipe."""
        print(f"   Reading PDF: {os.path.basename(pdf_path)}")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"

                # Extract title from filename or first line
                titulo = os.path.basename(pdf_path).replace('.pdf', '').replace('_', ' ').strip()
                lines = full_text.split('\n')
                if lines and len(lines[0].strip()) > 3:
                    titulo = lines[0].strip()

                # Separate abbreviations and pattern
                abreviacoes = ""
                receita = full_text
                
                lower_text = full_text.lower()
                abbrev_pos = lower_text.find("abbreviations")
                pattern_pos = lower_text.find("pattern")

                if abbrev_pos != -1 and pattern_pos != -1 and abbrev_pos < pattern_pos:
                    abreviacoes = full_text[abbrev_pos:pattern_pos]
                    receita = full_text[pattern_pos:]
                elif abbrev_pos != -1:
                    abreviacoes = full_text[abbrev_pos:]
                    receita = ""

                print("   ✓ PDF reading complete.")
                return {
                    "titulo": titulo,
                    "materiais": abreviacoes.strip(),
                    "receita": receita.strip()
                }
        except Exception as e:
            print(f"   ✗ Error reading PDF: {e}")
            return None

    def extract_recipe_details(self, url: str) -> dict:
        """Downloads PDF from a recipe page and extracts its content."""
        print(f"Processing recipe: {url}")
        
        try:
            self.driver.get(url)
            time.sleep(1.5)  # Reduced from 3

            recipe_data = {'url': url, 'titulo': '', 'materiais': '', 'receita': '', 'origem': self.name}

            # Try to close any pop-ups or overlays first
            try:
                close_selectors = [
                    (By.XPATH, '//button[@aria-label="Close"]'),
                    (By.XPATH, '//button[contains(@class, "close")]'),
                    (By.XPATH, '//button[contains(text(), "×")]'),
                ]
                for by, selector in close_selectors:
                    try:
                        close_btn = WebDriverWait(self.driver, 1).until(
                            EC.element_to_be_clickable((by, selector))
                        )
                        close_btn.click()
                        print("   ✓ Closed pop-up/overlay")
                        time.sleep(0.5)
                        break
                    except:
                        continue
            except:
                pass

            # Scroll to ensure button is in view
            self.driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(0.3)

            # Try to find and click download/add to library button
            possible_selectors = [
                (By.XPATH, '//button[contains(translate(., "ADD TO LIBRARY", "add to library"), "add to library")]'),
                (By.XPATH, '//button[contains(translate(., "FREE", "free"), "free")]'),
                (By.XPATH, '//button[contains(translate(., "DOWNLOAD", "download"), "download")]'),
                (By.XPATH, '//a[contains(translate(., "DOWNLOAD", "download"), "download")]'),
            ]
            
            button_clicked = False
            for by, selector in possible_selectors:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    # Scroll to element
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    time.sleep(0.3)
                    
                    # Try JavaScript click if regular click fails
                    try:
                        WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((by, selector)))
                        element.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", element)
                    
                    print(f"   ✓ Button clicked")
                    button_clicked = True
                    break
                except (TimeoutException, NoSuchElementException):
                    continue
                except Exception as e:
                    continue
            
            if not button_clicked:
                print("   ✗ No download button found. Skipping.")
                return recipe_data

            time.sleep(1.5)  # Reduced from 3
            
            # Try to find final download link after adding to library
            try:
                WebDriverWait(self.driver, 2).until(
                    EC.visibility_of_element_located((By.XPATH, '//*[contains(text(), "In your library")]'))
                )
                print("   Recipe added to library. Clicking final download link.")
                try:
                    download_link = self.driver.find_element(
                        By.XPATH, '//a[contains(@href, ".pdf")] | //a[contains(translate(., "DOWNLOAD", "download"), "download")]'
                    )
                    # Use JavaScript click for download link
                    self.driver.execute_script("arguments[0].click();", download_link)
                except NoSuchElementException:
                    print("   ✗ Could not find final download link.")
            except TimeoutException:
                pass

            # Wait for PDF download and parse it
            downloaded_pdf = self._wait_for_download_complete()
            if downloaded_pdf:
                pdf_data = self._parse_pdf(downloaded_pdf)
                if pdf_data:
                    recipe_data.update(pdf_data)
            else:
                print("   ✗ PDF download not completed or not found.")

            return recipe_data
            
        except Exception as e:
            print(f"   ✗ An unexpected error occurred: {str(e)[:200]}")
            return {'url': url, 'titulo': '', 'materiais': '', 'receita': '', 'origem': self.name}

    def run(self, args: dict):
        """Main orchestration method for Lovecrafts scraper."""
        os.makedirs(os.path.join(self.db_dir, "resultados"), exist_ok=True)
        self._setup_download_dir()

        # Get credentials
        lc_email = os.environ.get('LOVECRAFTS_EMAIL')
        lc_password = os.environ.get('LOVECRAFTS_PASSWORD')

        if not lc_email:
            lc_email = input("Enter your Lovecrafts email: ")
        if not lc_password:
            lc_password = getpass.getpass("Enter your Lovecrafts password: ")

        # Perform login
        if not self._perform_login(lc_email, lc_password):
            print("✗ Scraper halted due to login failure.")
            print("   Please verify your credentials in the .env file or when prompted.")
            return

        # Collect URLs
        urls_remotas = self.collect_recipe_urls()
        
        if not urls_remotas:
            print("✗ No recipe URLs found. Halting.")
            return

        # Load existing URLs to compare
        urls_locais = set()
        if os.path.exists(self.url_file_path):
            with open(self.url_file_path, 'r', encoding='utf-8') as f:
                urls_locais = set(line.strip() for line in f if line.strip())

        # Determine mode and URLs to process
        is_force_mode = args.get('force', False)
        
        if is_force_mode:
            urls_to_process = sorted(list(urls_remotas))
        else:
            urls_to_process = sorted(list(urls_remotas - urls_locais))

        # Check if CSV exists - if not, force first run
        if not os.path.exists(self.csv_file_path) and not is_force_mode:
            print(f"Data file '{self.csv_file_path}' not found. Activating forced first run mode.")
            is_force_mode = True
            urls_to_process = sorted(list(urls_remotas))

        # Update URL file after determining what to process
        with open(self.url_file_path, 'w', encoding='utf-8') as f:
            for url in sorted(list(urls_remotas)):
                f.write(f"{url}\n")
        print(f"✓ URLs saved to '{self.url_file_path}'")

        if args.get('update_urls_only'):
            print("Lovecrafts scraper: URLs updated. Halting as requested.")
            return

        if not urls_to_process:
            print("Lovecrafts scraper: No new recipes to process.")
            return

        print(f"\n--- Starting detail extraction for {len(urls_to_process)} recipes ---")
        all_recipes_data = []
        
        for i, url in enumerate(urls_to_process):
            print(f"\n[{i+1}/{len(urls_to_process)}]")
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


