import os
import time
import base64
import getpass
import pandas as pd
import requests
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

from scrapers.base_scraper import ScraperStrategy

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path, override=True)
except ImportError:
    pass

class ScribdScraper(ScraperStrategy):
    """Scraper for amigurumi patterns from scribd.com (requires login and PDF download)."""

    def __init__(self, driver):
        super().__init__(driver)
        self.wait = WebDriverWait(driver, 15)
        self.name = "Scribd"
        self.login_url = "https://www.scribd.com/login"
        self.search_base_url = 'https://pt.scribd.com/search?query=amigurumi&suggestion_id=long-b70e2f6da9dd040250cd00c57ef10d28&verbatim=true'
        self.db_dir = 'db'
        self.url_file_path = os.path.join(self.db_dir, 'scribd_urls.txt')
        self.csv_file_path = os.path.join(self.db_dir, 'resultados', 'scribd_dados.csv')
        self.parquet_file_path = os.path.join(self.db_dir, 'resultados', 'scribd_base64.parquet')
        self.download_dir = os.path.join(os.getcwd(), "downloads", "scribd")
        self.is_logged_in = False

    def get_name(self) -> str:
        return self.name

    def _setup_download_dir(self):
        """Creates the download directory if it doesn't exist."""
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            print(f"✓ Download directory created: {self.download_dir}")

    def _handle_cookie_banner(self):
        """Attempts to close cookie consent banner quickly."""
        # Reduced selectors to most common ones only
        accept_selectors = [
            (By.ID, "onetrust-accept-btn-handler"),
            (By.XPATH, '//button[contains(@class, "osano")]'),
            (By.XPATH, '//button[contains(text(), "Accept")]'),
        ]
        
        for by, selector in accept_selectors:
            try:
                element = WebDriverWait(self.driver, 1.5).until(  # Reduced from 3s
                    EC.element_to_be_clickable((by, selector))
                )
                # Use JavaScript click to avoid inspector errors
                self.driver.execute_script("arguments[0].click();", element)
                print("✓ Cookie banner closed.")
                time.sleep(0.5)  # Reduced from 1s
                return True
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                # Silently ignore other errors (like inspector errors)
                continue
        
        return False

    def _check_if_logged_in(self) -> bool:
        """Check if already logged in by looking for user account indicators."""
        print("Checking if already logged in...")
        try:
            # Try to access a page that requires login
            self.driver.get("https://www.scribd.com/account")
            time.sleep(1.5)  # Reduced from 2s
            
            current_url = self.driver.current_url
            
            # If we're redirected to login page, we're not logged in
            if "login" in current_url.lower():
                print("   Not logged in yet.")
                return False
            
            # Check for account/user elements
            user_indicators = [
                (By.XPATH, '//a[contains(@href, "/account")]'),
                (By.XPATH, '//a[contains(@href, "/user/")]'),
                (By.XPATH, '//*[contains(@class, "user_menu")]'),
                (By.XPATH, '//*[contains(@class, "account")]'),
            ]
            
            for by, selector in user_indicators:
                try:
                    self.driver.find_element(by, selector)
                    print("   ✓ Already logged in!")
                    self.is_logged_in = True
                    return True
                except:
                    continue
            
            print("   Could not confirm login status.")
            return False
            
        except Exception as e:
            print(f"   Error checking login status: {e}")
            return False

    def _perform_login(self, email: str, password: str) -> bool:
        """Performs login to Scribd (manual login recommended)."""
        print(f"\n--- Starting login process ---")
        
        # First check if already logged in
        if self._check_if_logged_in():
            return True
        
        # Go directly to account page for manual login (faster than login page)
        print(f"\n{'='*60}")
        print(f"⚠️  OPENING BROWSER - Please wait...")
        print(f"{'='*60}\n")
        print(f"Opening Scribd homepage...")
        
        self.driver.get("https://www.scribd.com")
        
        # Maximize and bring window to front (multiple approaches)
        try:
            self.driver.maximize_window()
            self.driver.switch_to.window(self.driver.current_window_handle)
            
            # Try to bring window to front using Windows API (if on Windows)
            try:
                import win32gui
                import win32con
                # Find Chrome window and bring to front
                def callback(hwnd, windows):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if "Chrome" in title or "Scribd" in title:
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                windows = []
                win32gui.EnumWindows(callback, windows)
            except ImportError:
                pass  # pywin32 not installed, skip
        except Exception as e:
            print(f"   Warning: Could not maximize window: {e}")
        
        time.sleep(2)  # Increased wait time for page load
        
        current_url = self.driver.current_url
        print(f"✓ Page loaded: {current_url}")
        
        self._handle_cookie_banner()
        
        print("\n" + "="*60)
        print("🌐 BROWSER WINDOW SHOULD BE VISIBLE NOW!")
        print("="*60)
        
        print("\n" + "="*60)
        print("⚠️  MANUAL LOGIN REQUIRED")
        print("="*60)
        print("STEPS:")
        print("1. Look for the Chrome browser window (it should be maximized)")
        print("2. Click 'Log In' button in the top right corner")
        print("3. Enter your Scribd credentials:")
        print(f"   Email: paraspamsomente@gmail.com")
        print(f"   Password: (your password)")
        print("4. Complete the login")
        print("5. After successful login, come back here and press ENTER")
        print("="*60 + "\n")
        
        print("⏳ Waiting for you to complete login in the browser...")
        input("👉 Press ENTER after you have logged in: ")
        
        # Check if manual login was successful
        if self._check_if_logged_in():
            print("✓ Login detected successfully!")
            return True
        else:
            print("✗ Login not detected. Please try again.")
            return False

    def collect_recipe_urls(self) -> set:
        """Collects all document URLs from search results with pagination."""
        if not self.is_logged_in:
            print("✗ Cannot collect URLs: Not logged in.")
            return set()

        print(f"\n--- Starting URL collection ---")
        all_urls = set()
        page = 1
        max_pages = 100  # Increased limit - will stop when no more results
        consecutive_empty_pages = 0
        max_consecutive_empty = 3  # Stop after 3 consecutive pages with no new URLs
        
        while page <= max_pages:
            search_url = f"{self.search_base_url}&page={page}"
            print(f"\nPage {page}: {search_url}")
            self.driver.get(search_url)
            time.sleep(1.5)  # Reduced from 2s
            
            try:
                # Find document links
                link_selectors = [
                    (By.XPATH, '//a[contains(@href, "/document/")]'),
                    (By.XPATH, '//div[contains(@class, "search_result")]//a'),
                    (By.CSS_SELECTOR, 'a[href*="/document/"]'),
                ]
                
                links = []
                for by, selector in link_selectors:
                    try:
                        links = self.driver.find_elements(by, selector)
                        if links:
                            break
                    except:
                        continue
                
                if not links:
                    consecutive_empty_pages += 1
                    print(f"   No results found on page {page}.")
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"   ⚠ {max_consecutive_empty} consecutive empty pages. Stopping.")
                        break
                    page += 1
                    continue
                
                page_urls = set()
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        if href and '/document/' in href:
                            # Clean URL (remove query parameters for deduplication)
                            clean_url = href.split('?')[0]
                            if clean_url not in all_urls:
                                page_urls.add(clean_url)
                    except:
                        continue
                
                if not page_urls:
                    consecutive_empty_pages += 1
                    print(f"   No new URLs found on page {page} (all duplicates).")
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"   ⚠ {max_consecutive_empty} consecutive pages with no new URLs. Stopping.")
                        break
                else:
                    consecutive_empty_pages = 0  # Reset counter
                
                all_urls.update(page_urls)
                print(f"   Found {len(page_urls)} new URLs on this page (Total: {len(all_urls)})")
                
                # Check if we're on the last page by looking for disabled next button or no pagination
                try:
                    # Look for next page indicators
                    next_indicators = [
                        (By.XPATH, '//a[contains(@class, "next") and contains(@class, "disabled")]'),
                        (By.XPATH, '//button[contains(@class, "next") and @disabled]'),
                        (By.XPATH, '//li[contains(@class, "next") and contains(@class, "disabled")]'),
                    ]
                    
                    for by, selector in next_indicators:
                        try:
                            disabled_next = self.driver.find_element(by, selector)
                            if disabled_next:
                                print("   ✓ Reached last page (next button disabled).")
                                page = max_pages + 1  # Force exit
                                break
                        except:
                            continue
                except:
                    pass
                
                page += 1
                time.sleep(0.8)  # Reduced delay between pages
                
            except Exception as e:
                print(f"   Error on page {page}: {e}")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    break
                page += 1
        
        print(f"\n✓ Total URLs collected: {len(all_urls)} from {page-1} pages")
        return all_urls

    def _download_pdf_with_requests(self, download_url: str, title: str) -> str:
        """Downloads PDF using requests library to avoid antivirus blocking Selenium downloads."""
        try:
            # Get cookies from Selenium session
            selenium_cookies = self.driver.get_cookies()
            
            # Convert Selenium cookies to requests format
            session = requests.Session()
            for cookie in selenium_cookies:
                session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
            
            # Set headers to mimic browser
            headers = {
                'User-Agent': self.driver.execute_script("return navigator.userAgent;"),
                'Referer': self.driver.current_url,
                'Accept': 'application/pdf,*/*',
            }
            
            print(f"      📥 Downloading via requests (bypassing antivirus)...")
            
            # Download PDF
            response = session.get(download_url, headers=headers, stream=True, timeout=45)
            
            if response.status_code == 200:
                # Save to file
                filename = f"{title}.pdf"
                filepath = os.path.join(self.download_dir, filename)
                
                # Write in chunks
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                print(f"      ✓ Downloaded via requests: {filename} ({file_size:.2f} MB)")
                return filepath
            else:
                print(f"      ✗ HTTP {response.status_code}: {response.reason}")
                return None
                
        except Exception as e:
            print(f"      ✗ Error downloading with requests: {e}")
            return None

    def _download_pdf(self, url: str) -> str:
        """Attempts to download PDF from a Scribd document URL with two-step process."""
        print(f"\n   Accessing: {url}")
        self.driver.get(url)
        time.sleep(3)  # Garantir carregamento completo
        
        # Ativar captura de logs de rede para interceptar download de PDF
        try:
            # Enable network logging
            self.driver.execute_cdp_cmd('Network.enable', {})
        except:
            pass
        
        try:
            # Check for subscription/paywall messages early
            paywall_indicators = [
                '//div[contains(text(), "Start your free trial")]',
                '//div[contains(text(), "Subscribe to read")]',
                '//div[contains(text(), "Upload to unlock")]',
                '//button[contains(text(), "Start Free Trial")]',
            ]
            
            for selector in paywall_indicators:
                try:
                    paywall = self.driver.find_element(By.XPATH, selector)
                    if paywall:
                        print(f"      ⚠️  Paywall detected - document requires subscription")
                        return None
                except:
                    continue
            
            # Get document title for filename BEFORE clicking download
            try:
                title_element = self.driver.find_element(By.XPATH, '//h1 | //title')
                title = title_element.text.strip()
                # Clean filename
                title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                title = title[:100]  # Limit length
                if not title or title == "Scribd":
                    title = f"scribd_document_{int(time.time())}"
            except:
                title = f"scribd_document_{int(time.time())}"
            
            print(f"      Document title: {title}")
            
            # STEP 1: Look for initial download button
            print(f"      Step 1: Looking for download button...")
            
            download_selectors = [
                # Scribd-specific button classes (mais específicos primeiro)
                (By.XPATH, '//button[@aria-label="Download"]'),
                (By.XPATH, '//button[@data-e2e="download-button"]'),
                (By.CLASS_NAME, '_1hU3TU'),
                (By.XPATH, '//button[contains(@class, "_1hU3TU")]'),
                # Seletores mais genéricos
                (By.XPATH, '//button[contains(translate(., "DOWNLOAD", "download"), "download")]'),
                (By.XPATH, '//a[contains(translate(., "DOWNLOAD", "download"), "download")]'),
                (By.XPATH, '//button[contains(@class, "download")]'),
                (By.XPATH, '//a[contains(@class, "download")]'),
                (By.XPATH, '//button[contains(@aria-label, "Download")]'),
                (By.XPATH, '//button[contains(@aria-label, "download")]'),
                (By.XPATH, '//div[contains(@class, "download")]//button'),
                (By.CSS_SELECTOR, 'button[class*="download"]'),
                (By.CSS_SELECTOR, 'a[class*="download"]'),
            ]
            
            download_button = None
            for by, selector in download_selectors:
                try:
                    download_button = WebDriverWait(self.driver, 5).until(  # Aumentado de 3 para 5
                        EC.element_to_be_clickable((by, selector))
                    )
                    print(f"      ✓ Found download button: {selector}")
                    break
                except:
                    continue
            
            if not download_button:
                print("      ⚠️  Download button not found.")
                # Debug: Save page source for analysis
                try:
                    page_text = self.driver.find_element(By.TAG_NAME, 'body').text[:500]
                    if 'premium' in page_text.lower() or 'subscribe' in page_text.lower() or 'trial' in page_text.lower():
                        print("      ⚠️  Document appears to require subscription")
                    else:
                        print(f"      ℹ️  Page preview: {page_text[:200]}...")
                except:
                    pass
                return None
            
            # Try to close any overlaying cookie banners before clicking
            self._handle_cookie_banner()
            time.sleep(0.2)  # Reduced from 0.3s
            
            print(f"      Step 1: Clicking initial download button...")
            try:
                # Use JavaScript click directly (faster and more reliable)
                self.driver.execute_script("arguments[0].scrollIntoView(true);", download_button)
                time.sleep(0.2)
                
                # Try to intercept the download URL before clicking
                download_url = None
                try:
                    # Check if button is a link with href
                    download_url = download_button.get_attribute('href')
                    if not download_url:
                        # Check for data attributes
                        download_url = download_button.get_attribute('data-url') or download_button.get_attribute('data-href')
                except:
                    pass
                
                # If we found a direct download URL, use requests instead of Selenium
                if download_url and ('.pdf' in download_url.lower() or 'download' in download_url.lower()):
                    print(f"      ✓ Found direct PDF URL, using requests method...")
                    return self._download_pdf_with_requests(download_url, title)
                
                # Otherwise, click normally
                self.driver.execute_script("arguments[0].click();", download_button)
                print(f"      ✓ First button clicked!")
            except Exception as e:
                print(f"      ✗ Error clicking button: {e}")
                return None
            
            time.sleep(1)  # Reduced from 1.5s
            
            # STEP 2: Look for second/confirmation download button or format selection
            print(f"      Step 2: Looking for confirmation or format selection...")
            second_step_selectors = [
                # Scribd-specific second button classes (most specific first)
                # Try exact class match first
                (By.XPATH, '//button[contains(@class, "ButtonCore-module_content_8zyAJv") and contains(@class, "ButtonCore-module_fullWidth_WRcye1")]'),
                (By.XPATH, '//button[@class="ButtonCore-module_content_8zyAJv ButtonCore-module_fullWidth_WRcye1"]'),
                # Alternative Scribd buttons
                (By.XPATH, '//button[contains(@class, "AccentButton-module_wrapper_W6vQ8z")]'),
                (By.XPATH, '//button[contains(@class, "ButtonShared-module_fullWidth_zlpvyi")]'),
                (By.XPATH, '//button[contains(@class, "ButtonCore-module_wrapper_MkTb9s") and contains(@class, "AccentButton")]'),
                (By.XPATH, '//button[contains(@class, "ButtonCore-module_fullWidth")]'),
                (By.XPATH, '//button[contains(@class, "ButtonCore-module_content")]'),
                # Look for modal buttons
                (By.XPATH, '//div[contains(@class, "modal")]//button[@type="submit"]'),
                (By.XPATH, '//div[contains(@class, "dialog")]//button[@type="submit"]'),
                (By.XPATH, '//div[@role="dialog"]//button[@type="submit"]'),
                # Generic selectors
                (By.XPATH, '//button[contains(text(), "PDF")]'),
                (By.XPATH, '//a[contains(text(), "PDF")]'),
                (By.XPATH, '//button[contains(text(), "Confirm")]'),
                (By.XPATH, '//button[contains(text(), "Download PDF")]'),
                (By.XPATH, '//a[contains(text(), "Download PDF")]'),
                (By.XPATH, '//button[contains(@class, "confirm")]'),
                (By.XPATH, '//button[@type="submit"]'),
                (By.XPATH, '//div[contains(@class, "modal")]//button[contains(., "Download")]'),
                (By.XPATH, '//div[contains(@class, "dialog")]//button[contains(., "Download")]'),
                (By.XPATH, '//div[contains(@class, "modal")]//button'),
                (By.XPATH, '//div[contains(@class, "dialog")]//button'),
            ]
            
            second_button = None
            for by, selector in second_step_selectors:
                try:
                    second_button = WebDriverWait(self.driver, 3).until(  # Reduced from 5s
                        EC.element_to_be_clickable((by, selector))
                    )
                    print(f"      Found second step button: {selector}")
                    break
                except:
                    continue
            
            if second_button:
                print(f"      Step 2: Clicking confirmation/format button...")
                # Use JavaScript click directly (faster and more reliable)
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", second_button)
                time.sleep(0.2)
                
                # Try to intercept download URL from second button too
                download_url = None
                try:
                    download_url = second_button.get_attribute('href') or second_button.get_attribute('data-url')
                except:
                    pass
                
                # Click the button
                self.driver.execute_script("arguments[0].click();", second_button)
                print(f"      ✓ Second button clicked!")
                
                # Wait a bit and try to capture any PDF download request from network logs
                time.sleep(2)
                
                # Try to get download URL from network logs
                if not download_url:
                    try:
                        logs = self.driver.get_log('performance')
                        for entry in logs:
                            import json
                            log = json.loads(entry['message'])['message']
                            if log.get('method') == 'Network.responseReceived':
                                response = log.get('params', {}).get('response', {})
                                response_url = response.get('url', '')
                                content_type = response.get('mimeType', '')
                                
                                # Check if it's a PDF download
                                if 'application/pdf' in content_type or '.pdf' in response_url.lower():
                                    download_url = response_url
                                    print(f"      ✓ Captured PDF URL from network: {response_url[:100]}...")
                                    break
                    except Exception as e:
                        print(f"      ℹ️  Could not capture network logs: {e}")
                
                # If we captured a download URL, use requests
                if download_url and '.pdf' in download_url.lower():
                    print(f"      ✓ Using requests method to bypass antivirus...")
                    pdf_path = self._download_pdf_with_requests(download_url, title)
                    if pdf_path:
                        return pdf_path
                    # If requests failed, continue with normal Selenium download
                
                time.sleep(2)  # Wait for possible popup to appear
                
                # Check for paywall popup after clicking confirmation button
                try:
                    # Wait up to 3 seconds for popup to appear
                    popup = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((
                            By.XPATH, 
                            '//div[@role="dialog" and contains(@class, "modal")]'
                        ))
                    )
                    print(f"      ⚠️  Paywall popup detected! Attempting to bypass...")
                    
                    # Try multiple strategies to close/bypass the popup
                    popup_closed = False
                    
                    # Strategy 1: Look for "Continue" or "Download" button in the popup
                    continue_selectors = [
                        '//button[contains(text(), "Fazer o download do documento")]',  # Portuguese
                        '//button[contains(text(), "Download")]',
                        '//a[contains(text(), "Fazer o download do documento")]',  # Link version
                        '//a[@data-e2e="modal-download-button"]',  # Data attribute
                    ]
                    
                    for selector in continue_selectors:
                        try:
                            continue_button = WebDriverWait(self.driver, 2).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            self.driver.execute_script("arguments[0].click();", continue_button)
                            print(f"      ✓ Clicked continue button in popup")
                            popup_closed = True
                            break
                        except:
                            continue
                    
                    # Strategy 2: If no continue button, try to close popup with X button
                    if not popup_closed:
                        close_selectors = [
                            '//button[@data-e2e="modal-close"]',
                            '//button[contains(@class, "close")]',
                            '//button[@aria-label="Close" or @aria-label="Fechar"]',
                        ]
                        
                        for selector in close_selectors:
                            try:
                                close_button = WebDriverWait(self.driver, 2).until(
                                    EC.element_to_be_clickable((By.XPATH, selector))
                                )
                                self.driver.execute_script("arguments[0].click();", close_button)
                                print(f"      ✓ Closed popup with X button")
                                popup_closed = True
                                break
                            except:
                                continue
                    
                    if popup_closed:
                        print(f"      ✓ Popup handled successfully")
                        time.sleep(1)  # Wait after closing popup
                    else:
                        print(f"      ⚠️  Could not find button to close popup")
                        
                except TimeoutException:
                    print(f"      ✓ No popup detected, proceeding with download")
                except Exception as e:
                    print(f"      ⚠️  Error handling popup: {str(e)}")
                    
            else:
                print(f"      No second step button found, download may have started already.")
            
            # Wait for download to complete by checking for file in download folder
            print(f"      Waiting for download to complete...")
            max_wait = 40  # Aumentado de 25 para 40 segundos
            waited = 0
            check_interval = 0.5  # Check every 0.5 seconds
            
            # COUNT EXISTING PDFs BEFORE download to detect NEW files
            initial_files = set(os.listdir(self.download_dir))
            initial_pdf_count = len([f for f in initial_files if f.endswith('.pdf')])
            print(f"      Initial PDF count: {initial_pdf_count}")
            
            # Check for any NEW PDF file downloaded
            while waited < max_wait:
                try:
                    # List all files in download directory
                    files = os.listdir(self.download_dir)
                    pdf_files = [f for f in files if f.endswith('.pdf')]
                    
                    # Check if file is still being downloaded (ends with .crdownload or .tmp)
                    temp_files = [f for f in files if f.endswith('.crdownload') or f.endswith('.tmp')]
                    if temp_files:
                        if waited % 5 == 0:  # Print every 5 seconds
                            print(f"      ⏳ Download in progress... ({waited}s)")
                        time.sleep(check_interval)
                        waited += check_interval
                        continue
                    
                    # Check if a NEW PDF appeared (count increased)
                    current_pdf_count = len(pdf_files)
                    if current_pdf_count > initial_pdf_count:
                        # Find the NEW file (not in initial set)
                        new_files = set(files) - initial_files
                        new_pdfs = [f for f in new_files if f.endswith('.pdf')]
                        
                        if new_pdfs:
                            newest_pdf = new_pdfs[0]  # Get the new PDF
                            newest_path = os.path.join(self.download_dir, newest_pdf)
                            print(f"      ✓ NEW PDF downloaded: {newest_pdf}")
                            
                            # Optionally rename to clean title
                            if newest_pdf != f"{title}.pdf":
                                try:
                                    new_path = os.path.join(self.download_dir, f"{title}.pdf")
                                    if not os.path.exists(new_path):
                                        os.rename(newest_path, new_path)
                                        print(f"      ✓ Renamed to: {title}.pdf")
                                        return new_path
                                except:
                                    pass
                            
                            return newest_path
                        
                except Exception as e:
                    print(f"      Error checking downloads: {e}")
                
                time.sleep(check_interval)
                waited += check_interval
            
            print(f"      ⚠ Download timeout after {max_wait}s. File may still be downloading.")
            return None
            
        except Exception as e:
            print(f"      ✗ Error downloading PDF: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _convert_pdf_to_base64(self, pdf_path: str) -> str:
        """Converts a PDF file to base64 encoding."""
        try:
            with open(pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
                base64_encoded = base64.b64encode(pdf_content).decode('utf-8')
                print(f"      ✓ PDF converted to base64 ({len(base64_encoded)} chars)")
                return base64_encoded
        except Exception as e:
            print(f"      ✗ Error converting to base64: {e}")
            return None

    def extract_recipe_details(self, url: str) -> dict:
        """Extracts details from a Scribd document URL and downloads PDF."""
        print(f"\nProcessing: {url}")
        
        try:
            self.driver.get(url)
            time.sleep(4)
            
            # Extract metadata
            title = "N/A"
            author = "N/A"
            description = "N/A"
            
            try:
                title_element = self.driver.find_element(By.XPATH, '//h1[contains(@class, "title")] | //h1')
                title = title_element.text.strip()
            except:
                pass
            
            try:
                author_element = self.driver.find_element(By.XPATH, '//a[contains(@class, "author")] | //span[contains(@class, "author")]')
                author = author_element.text.strip()
            except:
                pass
            
            try:
                desc_element = self.driver.find_element(By.XPATH, '//meta[@name="description"]')
                description = desc_element.get_attribute('content').strip()
            except:
                pass
            
            # Download PDF
            pdf_path = self._download_pdf(url)
            
            # Convert to base64
            base64_content = None
            if pdf_path and os.path.exists(pdf_path):
                base64_content = self._convert_pdf_to_base64(pdf_path)
            
            return {
                'url': url,
                'title': title,
                'author': author,
                'description': description,
                'pdf_downloaded': pdf_path is not None,
                'pdf_path': pdf_path if pdf_path else "N/A",
                'base64_content': base64_content if base64_content else None
            }
            
        except Exception as e:
            print(f"   ✗ Error extracting details: {e}")
            return {
                'url': url,
                'title': "ERROR",
                'author': "ERROR",
                'description': str(e),
                'pdf_downloaded': False,
                'pdf_path': "N/A",
                'base64_content': None
            }

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

    def _save_results_to_csv(self, results: list):
        """Saves scraping results to CSV (without base64) and Parquet (with base64)."""
        results_dir = os.path.join(self.db_dir, 'resultados')
        os.makedirs(results_dir, exist_ok=True)
        
        # Create DataFrame with all data
        df_full = pd.DataFrame(results)
        
        # Save full data (including base64) to Parquet (merge with existing if present)
        if 'base64_content' in df_full.columns:
            df_parquet = df_full[['url', 'title', 'pdf_path', 'base64_content']].copy()
            df_parquet = df_parquet[df_parquet['base64_content'].notna()]  # Only rows with base64
            
            if not df_parquet.empty:
                # If parquet exists, merge to avoid losing previous data
                try:
                    if os.path.exists(self.parquet_file_path):
                        existing = pd.read_parquet(self.parquet_file_path)
                        combined = pd.concat([existing, df_parquet], ignore_index=True)
                        combined = combined.drop_duplicates(subset=['url'], keep='first')
                        combined.to_parquet(self.parquet_file_path, index=False, compression='snappy')
                    else:
                        df_parquet.to_parquet(self.parquet_file_path, index=False, compression='snappy')
                    print(f"✓ Base64 data saved to Parquet: {self.parquet_file_path}")
                    print(f"  Parquet file size: {os.path.getsize(self.parquet_file_path) / (1024*1024):.2f} MB")
                except Exception as e:
                    print(f"   ⚠ Could not merge Parquet file: {e}")
        
        # Save metadata (without base64) to CSV (merge with existing CSV to keep history)
        df_csv = df_full.drop(columns=['base64_content'], errors='ignore')
        try:
            if os.path.exists(self.csv_file_path):
                existing_csv = pd.read_csv(self.csv_file_path, encoding='utf-8-sig')
                combined_csv = pd.concat([existing_csv, df_csv], ignore_index=True)
                combined_csv = combined_csv.drop_duplicates(subset=['url'], keep='first')
                combined_csv.to_csv(self.csv_file_path, index=False, encoding='utf-8-sig')
            else:
                df_csv.to_csv(self.csv_file_path, index=False, encoding='utf-8-sig')
            print(f"✓ Metadata saved to CSV: {self.csv_file_path}")
        except Exception as e:
            print(f"   ⚠ Could not save/merge CSV metadata: {e}")

    def run(self, args: dict):
        """
        Main orchestration method for the Scribd scraper.
        
        Args:
            args: Dictionary with options like:
                - 'force': bool, force re-scraping even if URLs exist
                - 'limit': int, limit number of recipes to process
                - 'email': str, Scribd email (optional, will prompt if not provided)
                - 'password': str, Scribd password (optional, will prompt if not provided)
        """
        print(f"\n{'='*60}")
        print(f"Starting {self.name} Scraper")
        print(f"{'='*60}")
        
        # Debug: verificar se driver existe
        if not self.driver:
            print("❌ ERRO: Driver não foi inicializado!")
            return
        
        print(f"✓ Driver inicializado: {type(self.driver)}")
        print(f"✓ Args recebidos: {args}")
        
        self._setup_download_dir()
        
        # Get credentials
        email = args.get('email') or os.getenv('SCRIBD_EMAIL')
        password = args.get('password') or os.getenv('SCRIBD_PASSWORD')
        
        if not email:
            email = input("Enter your Scribd email: ")
        if not password:
            password = getpass.getpass("Enter your Scribd password: ")
        
        # Login
        if not self._perform_login(email, password):
            print("\n✗ Cannot proceed without successful login.")
            return
        
        # Collect URLs
        force = args.get('force', False)
        if force:
            print(f"\n🔄 Force mode: Collecting fresh URLs...")
            urls = self.collect_recipe_urls()
            if urls:
                self._save_urls_to_file(urls)
        elif not os.path.exists(self.url_file_path):
            print(f"\n📥 No URL file found. Collecting URLs...")
            urls = self.collect_recipe_urls()
            if urls:
                self._save_urls_to_file(urls)
        else:
            print(f"\n📂 Loading existing URLs from: {self.url_file_path}")
            urls = self._load_urls_from_file()
            print(f"✓ Loaded {len(urls)} URLs")

        # If resume flag is provided, filter out URLs already present in the CSV results
        if args.get('resume'):
            print("\n→ Resume mode: computing remaining URLs (filtering already processed)...")
            processed = set()
            try:
                if os.path.exists(self.csv_file_path):
                    df = pd.read_csv(self.csv_file_path, encoding='utf-8-sig')
                    if 'url' in df.columns:
                        processed = set(df['url'].astype(str).tolist())
            except Exception as e:
                print(f"   ⚠ Could not read existing CSV to determine processed URLs: {e}")

            # Read original URLs in original order and filter
            remaining = []
            try:
                with open(self.url_file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        u = line.strip()
                        if not u:
                            continue
                        if u not in processed:
                            remaining.append(u)
            except Exception as e:
                print(f"   ⚠ Could not read URL file for resume: {e}")

            print(f"   ✓ Already processed: {len(processed)} | Remaining: {len(remaining)}")
            urls = set(remaining)
        
        if not urls:
            print("\n✗ No URLs to process.")
            return
        
        # Process recipes
        limit = args.get('limit', len(urls))
        urls_to_process = list(urls)[:limit]
        
        print(f"\n{'='*60}")
        print(f"Processing {len(urls_to_process)} documents...")
        print(f"{'='*60}")
        
        results = []
        batch_size = 50  # Save every 50 documents to avoid losing progress
        for i, url in enumerate(urls_to_process, 1):
            print(f"\n[{i}/{len(urls_to_process)}]")
            details = self.extract_recipe_details(url)
            results.append(details)
            
            # Save intermediate results every batch_size documents
            if i % batch_size == 0:
                print(f"\n💾 Saving intermediate results ({i} documents)...")
                self._save_results_to_csv(results)
                print(f"✓ Progress saved!")
            
            time.sleep(0.3)  # Reduced from 0.5s - minimal delay between docs
        
        # Save final results
        if results:
            self._save_results_to_csv(results)
        
        print(f"\n{'='*60}")
        print(f"✓ Scraping completed!")
        print(f"   Total documents processed: {len(results)}")
        print(f"   PDFs downloaded: {sum(1 for r in results if r['pdf_downloaded'])}")
        print(f"   Base64 saved to Parquet: {sum(1 for r in results if r.get('base64_content'))}")
        print(f"{'='*60}\n")
