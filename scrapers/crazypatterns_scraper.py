"""
CrazyPatterns scraper — https://www.crazypatterns.net
Coleta padrões gratuitos de crochê das primeiras N páginas de
https://www.crazypatterns.net/en/search?keyword=free&a_c=1

Fluxo:
  1. Login via AJAX (requests): authenticate_email → authenticate_login
  2. Coleta links de itens via Selenium (conteúdo renderizado por JS)
  3. Para cada item: GET /en/items/free_download/{id} com cookies da sessão
     → redireciona para /en/items/download/{id}/{slug}
     → página tem link ZIP: /en/users/downloads/{id}/{hash}/{slug}
  4. Baixa o ZIP, extrai o primeiro PDF, salva localmente
  5. Salva imagem principal do item
  6. Registra em CSV
"""
import os
import re
import time
import zipfile
import io

import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from scrapers.base_scraper import ScraperStrategy

load_dotenv()

BASE_URL = "https://www.crazypatterns.net"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class CrazyPatternsScraper(ScraperStrategy):
    """Scraper para padrões gratuitos do CrazyPatterns."""

    def __init__(self, driver):
        super().__init__(driver)
        self.name = "CrazyPatterns"
        self.base_url = BASE_URL
        self.db_dir = "db"
        self.csv_path = os.path.join(self.db_dir, "resultados", "crazypatterns_dados.csv")
        self.pdfs_dir = os.path.join("downloads", "pdfs", "crazypatterns_pdfs")
        self.images_dir = os.path.join("downloads", "images", "crazypatterns_images")
        os.makedirs(self.pdfs_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(os.path.join(self.db_dir, "resultados"), exist_ok=True)

        # Session requests (autenticada)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.is_logged_in = False

        if driver:
            self.wait = WebDriverWait(driver, 20)

    # ------------------------------------------------------------------
    # Interface ScraperStrategy
    # ------------------------------------------------------------------

    def get_name(self) -> str:
        return self.name

    def collect_recipe_urls(self) -> set:
        """Coleta URLs de itens (não usado diretamente — ver run())."""
        return set()

    def extract_recipe_details(self, url: str) -> dict:
        """Extrai detalhes de um item (não usado diretamente — ver run())."""
        return {}

    def run(self, args: dict):
        """Execução principal do scraper."""
        max_pages = args.get("max_pages") or 3
        force = args.get("force", False)

        print(f"\n{'='*60}")
        print(f"  {self.name} Scraper")
        print(f"  Páginas: 1–{max_pages} | Force: {force}")
        print(f"{'='*60}\n")

        # 1. Login
        email = os.environ.get("CRAZYPATTERNS_EMAIL", "")
        password = os.environ.get("CRAZYPATTERNS_PASSWORD", "")
        if not self._login(email, password):
            print("✗ Login falhou. Abortando.")
            return

        # 2. Carregar CSV existente
        df_existing = self._load_existing_csv()
        processed_urls = set(df_existing["url"].tolist()) if not df_existing.empty else set()
        print(f"✓ {len(processed_urls)} itens já processados no CSV.\n")

        results = []

        # 3. Iterar páginas
        for page_num in range(1, max_pages + 1):
            print(f"\n--- Página {page_num}/{max_pages} ---")
            item_links = self._collect_page_items(page_num)
            print(f"  {len(item_links)} itens encontrados.")

            for idx, item_url in enumerate(item_links, 1):
                full_url = f"{BASE_URL}{item_url}" if item_url.startswith("/") else item_url
                print(f"  [{idx}/{len(item_links)}] {full_url}")

                if full_url in processed_urls and not force:
                    print("    ↷ Já processado, pulando.")
                    continue

                try:
                    data = self._process_item(full_url)
                    if data:
                        results.append(data)
                        processed_urls.add(full_url)
                        print(f"    ✓ {data.get('titulo', '?')[:60]}")
                    else:
                        print("    ✗ Sem dados retornados.")
                except Exception as e:
                    print(f"    ✗ Erro: {e}")

                time.sleep(1.0)

        # 4. Salvar CSV
        if results:
            df_new = pd.DataFrame(results)
            if not df_existing.empty:
                df_final = pd.concat([df_existing, df_new], ignore_index=True)
                df_final.drop_duplicates(subset=["url"], keep="last", inplace=True)
            else:
                df_final = df_new

            df_final.to_csv(self.csv_path, index=False, encoding="utf-8-sig")
            print(f"\n✓ CSV salvo: {self.csv_path} ({len(df_final)} registros total)")
        else:
            print("\nNenhum novo item para salvar.")

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def _login(self, email: str, password: str) -> bool:
        """Faz login via AJAX no CrazyPatterns (requests puro, sem Selenium)."""
        if self.is_logged_in:
            return True

        if not email or not password:
            print("✗ Credenciais não definidas. Configure CRAZYPATTERNS_EMAIL e CRAZYPATTERNS_PASSWORD no .env")
            return False

        print(f"  Fazendo login como {email}...")

        ajax_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/en/",
            "Origin": BASE_URL,
        }

        # Obter cookie de sessão inicial
        self.session.get(f"{BASE_URL}/en/", timeout=20)

        # Step 1: verificar e-mail
        r1 = self.session.post(
            f"{BASE_URL}/en/users/authenticate_email",
            data={"email": email},
            headers=ajax_headers,
            timeout=20,
        )
        d1 = r1.json()
        if not d1.get("emailExists"):
            print(f"  ✗ E-mail não encontrado: {email}")
            return False

        # Step 2: autenticar com senha
        r2 = self.session.post(
            f"{BASE_URL}/en/users/authenticate_login",
            data={"email": email, "password": password, "permalogin": "1"},
            headers=ajax_headers,
            timeout=20,
        )
        d2 = r2.json()
        if not d2.get("pwdValid") and not d2.get("alreadyAuthed"):
            print(f"  ✗ Senha incorreta: {d2.get('pwdMessage','')[:80]}")
            return False

        self.is_logged_in = True
        print("  ✓ Login bem-sucedido!")
        return True

    # ------------------------------------------------------------------
    # Coleta de URLs por página (Selenium — conteúdo JS)
    # ------------------------------------------------------------------

    def _collect_page_items(self, page_num: int) -> list:
        """Retorna lista de hrefs de itens da página de listagem."""
        if page_num == 1:
            url = f"{BASE_URL}/en/search?keyword=free&a_c=1"
        else:
            url = f"{BASE_URL}/en/search/{page_num}?keyword=free&a_c=1"

        print(f"  Carregando: {url}")
        self.driver.get(url)

        # Fechar modal de cookies se aparecer
        self._dismiss_cookie_modal()

        # Aguardar product-cards
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card"))
            )
        except TimeoutException:
            print("  ⚠ Timeout aguardando product-cards.")
            return []

        time.sleep(2)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        links = []
        seen = set()
        for card in soup.find_all("div", class_="product-card"):
            a_tag = card.find("a", href=re.compile(r"^/en/items/\d+/"))
            if a_tag and a_tag["href"] not in seen:
                seen.add(a_tag["href"])
                links.append(a_tag["href"])

        return links

    # ------------------------------------------------------------------
    # Processamento de cada item
    # ------------------------------------------------------------------

    def _process_item(self, item_url: str) -> dict | None:
        """
        Processa um item: baixa o PDF via requests autenticado,
        salva imagem e retorna dict com os dados.
        """
        # Extrair ID do item da URL: /en/items/{id}/{slug}
        m = re.search(r"/en/items/(\d+)/", item_url)
        if not m:
            return None
        item_id = m.group(1)

        # Usar Selenium para extrair título e imagem da página do item
        title, image_url = self._extract_item_meta(item_url, item_id)

        # Download via requests autenticado
        pdf_path = self._download_item_file(item_id, title)

        # Baixar imagem
        img_local = self._download_image(image_url, item_id) if image_url else ""

        return {
            "titulo": title,
            "url": item_url,
            "imagem_url": image_url or "",
            "imagem_local": img_local,
            "pdf_local": pdf_path or "",
            "pdf_downloaded": bool(pdf_path),
            "origem": "CrazyPatterns",
        }

    # ------------------------------------------------------------------
    # Extração de metadados do item (título + imagem) via Selenium
    # ------------------------------------------------------------------

    def _extract_item_meta(self, item_url: str, item_id: str) -> tuple:
        """Extrai título e URL da imagem principal de uma página de item."""
        full_url = f"{BASE_URL}{item_url}" if item_url.startswith("/") else item_url
        self.driver.get(full_url)
        self._dismiss_cookie_modal()

        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .product-title"))
            )
        except TimeoutException:
            pass

        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        # Título
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title:
            title = og_title.get("content", "").strip()
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
        if not title:
            title = soup.title.get_text(strip=True) if soup.title else f"Item_{item_id}"

        # Imagem principal (swiper-slide ativo)
        image_url = ""
        og_img = soup.find("meta", property="og:image")
        if og_img:
            image_url = og_img.get("content", "").strip()

        if not image_url:
            img = soup.select_one(
                "div.swiper-slide-active img, #main-product-img_0, .product-main-swiper img"
            )
            if img:
                src = img.get("src") or img.get("data-src", "")
                if src:
                    image_url = f"{BASE_URL}{src}" if src.startswith("/") else src

        return title, image_url

    # ------------------------------------------------------------------
    # Download do arquivo via requests autenticado
    # ------------------------------------------------------------------

    def _download_item_file(self, item_id: str, title: str) -> str:
        """
        Navega para /en/items/free_download/{id} com a sessão autenticada,
        pega o link de ZIP da página de download, baixa e extrai o primeiro PDF.
        Retorna o caminho local do PDF ou "" em caso de falha.
        """
        dl_url = f"{BASE_URL}/en/items/free_download/{item_id}"
        resp = self.session.get(
            dl_url,
            headers={"Referer": f"{BASE_URL}/en/items/{item_id}/"},
            timeout=30,
            allow_redirects=True,
        )

        if resp.status_code != 200:
            print(f"    ✗ Erro {resp.status_code} ao acessar página de download.")
            return ""

        # Verificar se é PDF direto
        ct = resp.headers.get("Content-Type", "")
        if "pdf" in ct.lower():
            return self._save_pdf_bytes(resp.content, item_id, title)

        # Verificar se é ZIP direto
        if "zip" in ct.lower():
            return self._extract_pdf_from_zip(resp.content, item_id, title)

        # Página HTML — procurar link de download
        soup = BeautifulSoup(resp.text, "html.parser")
        zip_href = self._find_download_link(soup, item_id)

        if not zip_href:
            # Verificar se é item pago (não free)
            if "You have to buy" in resp.text or "authentication" in resp.url.lower():
                print(f"    ⚠ Item {item_id}: requer compra (não é free).")
            else:
                print(f"    ✗ Link de download não encontrado para item {item_id}.")
            return ""

        full_dl = f"{BASE_URL}{zip_href}" if zip_href.startswith("/") else zip_href
        print(f"    ↓ Baixando: {full_dl[:90]}")

        file_resp = self.session.get(
            full_dl,
            headers={"Referer": resp.url},
            timeout=60,
            allow_redirects=True,
            stream=True,
        )

        if file_resp.status_code != 200:
            print(f"    ✗ Erro {file_resp.status_code} ao baixar arquivo.")
            return ""

        content_type = file_resp.headers.get("Content-Type", "")
        content = file_resp.content

        if "pdf" in content_type.lower() or full_dl.lower().endswith(".pdf"):
            return self._save_pdf_bytes(content, item_id, title)

        # ZIP → extrair PDF
        if "zip" in content_type.lower() or full_dl.lower().endswith(".zip") or content[:2] == b"PK":
            return self._extract_pdf_from_zip(content, item_id, title)

        print(f"    ⚠ Tipo desconhecido: {content_type}")
        return ""

    def _find_download_link(self, soup: BeautifulSoup, item_id: str) -> str:
        """
        Procura o link de download ZIP/PDF na página de download.
        Prioridade:
          1. /en/users/downloads/{item_id}/... (link direto na página)
          2. Qualquer link com .zip ou .pdf
          3. /en/zip/... (API de ZIP)
        """
        # 1. Link direto de downloads
        for a in soup.find_all("a", href=re.compile(rf"/en/users/downloads/{item_id}/")):
            return a["href"]

        # 2. Qualquer link com zip ou pdf
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"\.(zip|pdf)($|\?)", href, re.I):
                return href

        # 3. Link de zip genérico
        for a in soup.find_all("a", href=re.compile(r"/en/zip/")):
            return a["href"]

        # 4. Tentar AJAX browsefiles para obter lista de arquivos
        return self._fetch_browsefiles(item_id)

    def _fetch_browsefiles(self, item_id: str) -> str:
        """
        Chama POST /en/zip/browsefiles/{item_id} para obter lista de arquivos.
        Retorna a URL do primeiro arquivo ou "".
        """
        try:
            r = self.session.post(
                f"{BASE_URL}/en/zip/browsefiles/{item_id}",
                headers={
                    "Referer": f"{BASE_URL}/en/items/download/{item_id}/",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json",
                },
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json()
                # Resposta pode ser dict {"files": [...]} ou lista direta
                if isinstance(data, dict):
                    files = data.get("files", [])
                    if data.get("redirect"):
                        return data["redirect"]
                elif isinstance(data, list):
                    files = data
                else:
                    return ""

                if files:
                    # Mensagens de erro vêm como lista de strings
                    first = files[0]
                    if isinstance(first, str) and len(first) > 200:
                        # É mensagem de erro, não URL
                        return ""
                    if isinstance(first, dict):
                        return (
                            first.get("url")
                            or first.get("href")
                            or first.get("path")
                            or first.get("download_url")
                            or ""
                        )
                    elif isinstance(first, str):
                        return first
        except Exception as e:
            print(f"    ⚠ browsefiles falhou: {e}")
        return ""

    # ------------------------------------------------------------------
    # Utilitários de arquivo
    # ------------------------------------------------------------------

    def _save_pdf_bytes(self, content: bytes, item_id: str, title: str) -> str:
        """Salva bytes como PDF e retorna o caminho."""
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title)[:60].strip()
        filename = f"{item_id}_{safe_title}.pdf"
        path = os.path.join(self.pdfs_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
        print(f"    ✓ PDF salvo: {filename}")
        return path

    def _extract_pdf_from_zip(self, content: bytes, item_id: str, title: str) -> str:
        """Extrai o primeiro PDF de um ZIP em memória e salva."""
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                pdf_files = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
                if not pdf_files:
                    print(f"    ⚠ ZIP sem PDFs. Arquivos: {zf.namelist()[:5]}")
                    return ""
                pdf_name = pdf_files[0]
                pdf_bytes = zf.read(pdf_name)
                return self._save_pdf_bytes(pdf_bytes, item_id, title)
        except zipfile.BadZipFile:
            print("    ✗ Arquivo inválido (não é ZIP nem PDF).")
            return ""

    def _download_image(self, image_url: str, item_id: str) -> str:
        """Baixa a imagem e salva localmente. Retorna o caminho ou ''."""
        try:
            ext = "jpg"
            m = re.search(r"\.(jpg|jpeg|png|webp)($|\?)", image_url, re.I)
            if m:
                ext = m.group(1).lower()

            filename = f"{item_id}.{ext}"
            path = os.path.join(self.images_dir, filename)

            if os.path.exists(path):
                return path

            r = self.session.get(image_url, timeout=20)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
                return path
        except Exception as e:
            print(f"    ⚠ Erro ao baixar imagem: {e}")
        return ""

    # ------------------------------------------------------------------
    # CSV helpers
    # ------------------------------------------------------------------

    def _load_existing_csv(self) -> pd.DataFrame:
        """Carrega CSV existente ou retorna DataFrame vazio."""
        if os.path.exists(self.csv_path):
            try:
                return pd.read_csv(self.csv_path, encoding="utf-8-sig")
            except Exception:
                pass
        return pd.DataFrame(
            columns=["titulo", "url", "imagem_url", "imagem_local",
                     "pdf_local", "pdf_downloaded", "origem"]
        )

    # ------------------------------------------------------------------
    # Utilitários Selenium
    # ------------------------------------------------------------------

    def _dismiss_cookie_modal(self):
        """Remove modal de cookies se presente (via JavaScript)."""
        try:
            self.driver.execute_script("""
                var cm = document.getElementById('cookie-consent-modal');
                if (cm) cm.remove();
                var bd = document.querySelector('.modal-backdrop');
                if (bd) bd.remove();
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
            """)
        except Exception:
            pass
