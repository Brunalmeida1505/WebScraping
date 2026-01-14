"""Async Ravelry scraper adapted to project structure.

Uses AsyncRavelryScraper for API calls while following the ScraperStrategy pattern.
Maintains async structure with aiohttp and respects rate limiting.
Downloads PDFs and converts to base64.
"""
from __future__ import annotations

import asyncio
import os
import sys
import base64
import re
import pandas as pd
from typing import AsyncIterator, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from dotenv import load_dotenv

from scrapers.base_scraper import ScraperStrategy

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class AsyncRavelryScraper:
    def __init__(self, username: str, api_key: Optional[str] = None, password: Optional[str] = None, *, max_concurrent: int = 3, user_agent: Optional[str] = None):
        self.username = username
        self.api_key = api_key
        self.password = password
        self.max_concurrent = max_concurrent
        self._session: Optional[aiohttp.ClientSession] = None
        if user_agent is None:
            user_agent = os.environ.get('RAVELRY_USER_AGENT', 'AigurumiScraper/1.0 (+https://github.com/wmodanez)')
        self._headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json'
        }

    async def __aenter__(self) -> "AsyncRavelryScraper":
        auth = None
        if self.password is not None:
            auth = aiohttp.BasicAuth(self.username, self.password)
        elif self.api_key is not None:
            # Ravelry uses username:api_key for BasicAuth
            auth = aiohttp.BasicAuth(self.username, self.api_key)

        self._session = aiohttp.ClientSession(headers=self._headers, auth=auth)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._session:
            await self._session.close()

    async def fetch_patterns(self, max_pages: int = 1, per_page: int = 100) -> AsyncIterator[dict]:
        """Async generator yielding pattern dicts from search endpoint."""
        assert self._session is not None, "Use 'async with AsyncRavelryScraper(...) as scraper'"

        page = 1
        while page <= max_pages:
            params = {
                'craft': 'crochet',
                'query': 'amigurumi',
                'availability': 'free',  # Apenas receitas gratuitas
                'page': page,
                'page_size': per_page,
                'sort': 'best'
            }

            try:
                async with self._session.get('https://api.ravelry.com/patterns/search.json', params=params, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        patterns = data.get('patterns', [])
                        
                        if not patterns:
                            print(f"  No more patterns found at page {page}")
                            break
                            
                        for pat in patterns:
                            yield pat
                    else:
                        text = await resp.text()
                        print(f'✗ Error fetching page {page}: {resp.status} - {text[:200]}')
                        break
            except Exception as e:
                print(f'✗ Exception fetching patterns page {page}: {e}')
                break

            page += 1
            await asyncio.sleep(1.0)  # rate limiting

    async def buscar_pdf_em_pagina_externa(self, page_url: str) -> Optional[str]:
        """Busca links de PDF em uma página externa (blog, Dropbox, Google Drive, etc.)."""
        assert self._session is not None, "Use 'async with AsyncRavelryScraper(...) as scraper'"
        
        if not page_url:
            return None
        
        try:
            # Headers para simular navegador
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            async with self._session.get(page_url, headers=headers, timeout=30, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None
                
                # Verificar se já é um PDF direto
                content_type = resp.headers.get('Content-Type', '').lower()
                if 'application/pdf' in content_type:
                    pdf_bytes = await resp.read()
                    if b'%PDF' in pdf_bytes[:20]:
                        return base64.b64encode(pdf_bytes).decode('utf-8')
                    return None
                
                # Se não é PDF direto, procurar links na página HTML
                html_content = await resp.text(errors='ignore')
                
                # Padrões para encontrar links de PDF (mais abrangentes)
                pdf_patterns = [
                    # Links diretos para PDF
                    r'href=["\'](https?://[^"\']*\.pdf(?:\?[^"\']*)?)["\']',
                    # Google Drive
                    r'href=["\'](https?://drive\.google\.com/[^"\']*)["\']',
                    r'href=["\'](https?://docs\.google\.com/[^"\']*)["\']',
                    # Dropbox
                    r'href=["\'](https?://(?:www\.)?dropbox\.com/[^"\']*)["\']',
                    r'href=["\'](https?://dl\.dropboxusercontent\.com/[^"\']*)["\']',
                    # CloudFront e CDNs
                    r'href=["\'](https?://[^"\']*\.cloudfront\.net/[^"\']*\.pdf[^"\']*)["\']',
                    r'href=["\'](https?://[^"\']*cdn[^"\']*\.pdf[^"\']*)["\']',
                    # URLs com 'download' ou 'file'
                    r'href=["\'](https?://[^"\']*(?:download|file)[^"\']*\.pdf[^"\']*)["\']',
                    # Links relativos
                    r'href=["\'](/[^"\']*\.pdf(?:\?[^"\']*)?)["\']',
                    # Patreon
                    r'href=["\'](https?://(?:www\.)?patreon\.com/file[^"\']*)["\']',
                    # Blogger/Blogspot attachments
                    r'href=["\'](https?://[^"\']*\.blogspot\.com/[^"\']*\.pdf[^"\']*)["\']',
                    # WordPress attachments
                    r'href=["\'](https?://[^"\']*wp-content/uploads/[^"\']*\.pdf[^"\']*)["\']',
                ]
                
                pdf_urls = []
                for pattern in pdf_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    pdf_urls.extend(matches)
                
                # Remover duplicatas e converter URLs relativas
                pdf_urls = list(set(pdf_urls))
                absolute_urls = []
                for url in pdf_urls:
                    if url.startswith('/'):
                        absolute_urls.append(urljoin(page_url, url))
                    else:
                        absolute_urls.append(url)
                
                # Tentar baixar cada PDF encontrado (limite de 3 tentativas)
                for pdf_url in absolute_urls[:3]:
                    try:
                        # Tratamento especial para Dropbox
                        if 'dropbox.com' in pdf_url and 'dl=0' in pdf_url:
                            pdf_url = pdf_url.replace('dl=0', 'dl=1')
                        elif 'dropbox.com' in pdf_url and '?dl=' not in pdf_url:
                            pdf_url = pdf_url + ('&' if '?' in pdf_url else '?') + 'dl=1'
                        
                        # Tratamento especial para Google Drive
                        if 'drive.google.com' in pdf_url or 'docs.google.com' in pdf_url:
                            # Extrair ID do arquivo
                            file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', pdf_url)
                            if not file_id_match:
                                file_id_match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', pdf_url)
                            if file_id_match:
                                file_id = file_id_match.group(1)
                                pdf_url = f'https://drive.google.com/uc?export=download&id={file_id}'
                        
                        pdf_base64 = await self.baixar_pdf_base64(pdf_url)
                        if pdf_base64:
                            return pdf_base64
                    except Exception as e:
                        continue
                
                return None
                
        except Exception as e:
            return None

    async def baixar_pdf_base64(self, pdf_url: str) -> Optional[str]:
        """Baixa um PDF e converte para base64."""
        assert self._session is not None, "Use 'async with AsyncRavelryScraper(...) as scraper'"
        
        if not pdf_url:
            return None
        
        try:
            async with self._session.get(pdf_url, timeout=60) as resp:
                if resp.status == 200:
                    pdf_bytes = await resp.read()
                    
                    # Validar se é realmente um PDF verificando o header
                    if len(pdf_bytes) < 4:
                        return None
                    
                    # PDFs começam com "%PDF" (pode ter espaços/quebras antes)
                    # Procurar por %PDF nos primeiros 20 bytes
                    header_check = pdf_bytes[:20]
                    if b'%PDF' not in header_check:
                        # Verificar se é HTML, JSON ou outro formato
                        try:
                            text_header = pdf_bytes[:50].decode('utf-8', errors='ignore')
                            if any(x in text_header.lower() for x in ['<!doctype', '<html', '{"page":', '<?xml', '<head>', '<body>']):
                                return None
                        except:
                            pass
                        
                        return None
                    
                    # É um PDF válido, converter para base64
                    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                    return pdf_base64
                else:
                    return None
        except Exception as e:
            return None

    async def obter_detalhes_receita(self, pattern_id: int) -> Optional[dict]:
        """Fetches detailed information for a specific pattern."""
        assert self._session is not None, "Use 'async with AsyncRavelryScraper(...) as scraper'"
        try:
            async with self._session.get(f'https://api.ravelry.com/patterns/{pattern_id}.json', timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pattern = data.get('pattern', {})
                    
                    # Extrair informações de materiais
                    yarn_weight = pattern.get('yarn_weight', {})
                    yarn_weight_name = yarn_weight.get('name', '') if yarn_weight else ''
                    
                    gauge = pattern.get('gauge_description', '')
                    yardage = pattern.get('yardage_description', '')
                    difficulty = pattern.get('difficulty_average', 0)
                    rating = pattern.get('rating_average', 0)
                    
                    # Construir texto de materiais
                    materiais_parts = []
                    if yarn_weight_name:
                        materiais_parts.append(f"Peso do fio: {yarn_weight_name}")
                    if gauge:
                        materiais_parts.append(f"Gauge: {gauge}")
                    if yardage:
                        materiais_parts.append(f"Metragem: {yardage}")
                    if difficulty:
                        materiais_parts.append(f"Dificuldade: {difficulty:.1f}/5")
                    if rating:
                        materiais_parts.append(f"Avaliação: {rating:.1f}/5")
                    
                    materiais = " | ".join(materiais_parts) if materiais_parts else "Não especificado"
                    
                    # Receita (notes/description)
                    receita = pattern.get('notes', pattern.get('pattern_notes', ''))
                    if not receita:
                        receita = "Ver padrão completo no link"
                    
                    # Verificar se tem PDF disponível
                    pdf_url = None
                    pdf_base64 = None
                    external_url = None  # Guardar URL externa para tentar buscar PDF
                    
                    # 1. Verificar se tem PDF direto na API
                    # A API do Ravelry fornece 'download_location' com informações de download
                    download_location = pattern.get('download_location')
                    if download_location:
                        url = download_location.get('url', '')
                        # Se terminar em .pdf, é um PDF direto
                        if url and url.lower().endswith('.pdf'):
                            pdf_url = url
                        else:
                            # Guardar para buscar PDF na página externa
                            external_url = url
                    
                    # Alternativa: verificar em 'pdf_url' direto
                    if not pdf_url:
                        url = pattern.get('pdf_url', '')
                        if url and url.lower().endswith('.pdf'):
                            pdf_url = url
                    
                    # Alternativa: verificar em 'pattern_sources'
                    if not pdf_url:
                        pattern_sources = pattern.get('pattern_sources', [])
                        for source in pattern_sources:
                            url = source.get('url', '')
                            if url and url.lower().endswith('.pdf'):
                                pdf_url = url
                                break
                            elif url and not external_url:
                                # Guardar primeira URL externa para tentativa
                                external_url = url
                    
                    # 2. Se encontrou PDF direto, baixar
                    if pdf_url:
                        print(f"  → Downloading direct PDF...")
                        pdf_base64 = await self.baixar_pdf_base64(pdf_url)
                        if pdf_base64:
                            pdf_size_kb = len(pdf_base64) * 3 / 4 / 1024
                            print(f"  ✓ PDF downloaded ({pdf_size_kb:.1f} KB)")
                        else:
                            pdf_url = None
                    
                    # 3. Se não encontrou PDF direto, buscar em URLs externas
                    if not pdf_base64 and external_url:
                        print(f"  → Searching for PDF in external page...")
                        print(f"     URL: {external_url[:60]}...")
                        external_pdf = await self.buscar_pdf_em_pagina_externa(external_url)
                        if external_pdf:
                            pdf_base64 = external_pdf
                            pdf_url = external_url
                            pdf_size_kb = len(pdf_base64) * 3 / 4 / 1024
                            print(f"  ✓ PDF found in external page ({pdf_size_kb:.1f} KB)")
                    
                    return {
                        'id': pattern.get('id'),
                        'nome': pattern.get('name', ''),
                        'url': pattern.get('permalink', ''),
                        'materiais': materiais,
                        'receita': receita,
                        'gratuito': pattern.get('free', False),
                        'pdf_url': pdf_url or '',
                        'pdf_base64': pdf_base64 or '',
                    }
                else:
                    text = await resp.text()
                    print(f'✗ Error fetching details for pattern {pattern_id}: {resp.status} - {text[:200]}')
        except Exception as e:
            print(f'✗ Exception fetching details for pattern {pattern_id}: {e}')

        return None


class RavelryScraper(ScraperStrategy):
    """Scraper for free amigurumi patterns from Ravelry API following Strategy Pattern."""

    def __init__(self, driver=None):
        """
        Inicializa o scraper do Ravelry.
        Note: Este scraper usa a API REST assíncrona do Ravelry, não Selenium.
        O parâmetro driver é mantido para compatibilidade com a interface.
        """
        super().__init__(driver)
        self.name = "Ravelry"
        self.base_url = "https://api.ravelry.com"
        self.db_dir = "db"
        self.url_file_path = os.path.join(self.db_dir, "ravelry_urls.txt")
        self.csv_file_path = os.path.join(self.db_dir, "resultados", "ravelry_dados.csv")
        
        # Carregar credenciais do .env
        self._load_credentials()

    def get_name(self) -> str:
        return self.name

    def _load_credentials(self):
        """Carrega credenciais do arquivo .env"""
        # Especificar o caminho absoluto do .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        
        # Força o carregamento do .env
        load_dotenv(dotenv_path=env_path, override=True)
        
        # Ler credenciais
        self.username = os.getenv('RAVELRY_USERNAME')
        api_key = os.getenv('RAVELRY_APIKEY')
        password = os.getenv('RAVELRY_PASSWORD')
        self.user_agent = os.getenv('RAVELRY_USER_AGENT', 'AmigurumiScraper/1.0')
        
        # Priorizar API Key se disponível
        if self.username and api_key:
            self.credential_secret = api_key
            self.credential_type = 'api_key'
            print(f"✓ Using Ravelry API Key (username: {self.username})")
        elif self.username and password:
            self.credential_secret = password
            self.credential_type = 'password'
            print(f"✓ Using Ravelry password credentials (username: {self.username})")
        else:
            raise ValueError(
                "Ravelry credentials not found in .env file.\n"
                "Please add RAVELRY_USERNAME and (RAVELRY_APIKEY or RAVELRY_PASSWORD)\n"
                "Also set RAVELRY_USER_AGENT to identify your application."
            )

    async def _test_authentication_async(self, scraper: AsyncRavelryScraper) -> bool:
        """Testa se as credenciais funcionam usando o endpoint de busca (Read Only compatível)."""
        try:
            # Usar endpoint de busca que funciona com Read Only access
            params = {'craft': 'crochet', 'page_size': 1}
            async with scraper._session.get('https://api.ravelry.com/patterns/search.json', 
                                           params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Authentication successful! Read Only access working.")
                    return True
                elif resp.status == 401:
                    print(f"✗ Authentication failed: 401 Unauthorized")
                    print(f"  → Username or API Key is incorrect")
                    return False
                elif resp.status == 403:
                    print(f"✗ Authentication failed: 403 Forbidden")
                    text = await resp.text()
                    print(f"  → Response: {text[:300]}")
                    return False
                else:
                    text = await resp.text()
                    print(f"✗ Authentication failed: {resp.status} - {text[:200]}")
                    return False
        except Exception as e:
            print(f"✗ Connection error during authentication: {e}")
            return False

    def collect_recipe_urls(self, max_pages=None) -> set:
        """Coleta URLs de padrões usando a API assíncrona."""
        print(f"Starting URL collection from Ravelry API...")
        pattern_data = asyncio.run(self._collect_patterns_async(max_pages))
        print(f"Collected {len(pattern_data)} pattern URLs")
        return pattern_data

    async def _collect_patterns_async(self, max_pages=None) -> dict:
        """Coleta padrões e seus IDs usando a API assíncrona."""
        max_pages = max_pages if max_pages else 10
        pattern_data = {}  # {url: {id, name}}
        
        # Criar scraper assíncrono
        if self.credential_type == 'api_key':
            scraper = AsyncRavelryScraper(username=self.username, api_key=self.credential_secret, user_agent=self.user_agent)
        else:
            scraper = AsyncRavelryScraper(username=self.username, password=self.credential_secret, user_agent=self.user_agent)
        
        async with scraper:
            # Testar autenticação
            print("\nTesting Ravelry API authentication...")
            if not await self._test_authentication_async(scraper):
                print("✗ Authentication failed. Please check your .env credentials.")
                return pattern_data
            
            print(f"\n✓ Starting pattern collection (max {max_pages} pages, 100 per page)...")
            
            count = 0
            async for pattern in scraper.fetch_patterns(max_pages=max_pages, per_page=100):
                pattern_id = pattern.get('id')
                permalink = pattern.get('permalink')
                name = pattern.get('name', 'Unknown')
                
                if pattern_id and permalink:
                    pattern_data[permalink] = {'id': pattern_id, 'name': name}
                    count += 1
                    
                    if count % 50 == 0:
                        print(f"  Collected {count} patterns so far...")
        
        return pattern_data

    def extract_recipe_details(self, url: str) -> dict:
        """Extrai detalhes de uma receita - placeholder para compatibilidade."""
        return {
            'titulo': 'Pattern from Ravelry',
            'url': url,
            'materiais': 'Ver no link',
            'receita': 'Ver padrão completo no Ravelry',
            'origem': self.name
        }

    def run(self, args):
        """Executa o scraper."""
        print(f"Running scraper: {self.name}...")
        
        # Garantir que os diretórios existam
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.csv_file_path), exist_ok=True)
        
        # Coletar padrões com detalhes
        recipes_data = asyncio.run(self._run_async(args))
        
        # Salvar em CSV
        if recipes_data:
            df = pd.DataFrame(recipes_data)
            df.to_csv(self.csv_file_path, index=False, sep=';', encoding='utf-8-sig')
            print(f"✓ Data saved to {self.csv_file_path} ({len(recipes_data)} recipes)")
        else:
            print("✗ No recipe data collected")

    async def _run_async(self, args):
        """Executa a coleta completa de forma assíncrona."""
        recipes_data = []
        
        # Criar scraper assíncrono
        if self.credential_type == 'api_key':
            scraper = AsyncRavelryScraper(username=self.username, api_key=self.credential_secret, user_agent=self.user_agent)
        else:
            scraper = AsyncRavelryScraper(username=self.username, password=self.credential_secret, user_agent=self.user_agent)
        
        async with scraper:
            # Testar autenticação
            print("\nTesting Ravelry API authentication...")
            if not await self._test_authentication_async(scraper):
                return recipes_data
            
            # Suporta tanto dict quanto Namespace
            if isinstance(args, dict):
                max_pages = args.get('max_pages', 10)
            else:
                max_pages = getattr(args, 'max_pages', 10) if hasattr(args, 'max_pages') else 10
            
            print(f"\n✓ Collecting patterns with details (max {max_pages} pages)...")
            
            count = 0
            async for pattern in scraper.fetch_patterns(max_pages=max_pages, per_page=100):
                pattern_id = pattern.get('id')
                pattern_name = pattern.get('name', 'Unknown Pattern')
                
                if pattern_id:
                    # Buscar detalhes completos
                    details = await scraper.obter_detalhes_receita(pattern_id)
                    
                    if details:
                        recipes_data.append({
                            'titulo': details['nome'],
                            'url': details['url'],
                            'materiais': details['materiais'],
                            'receita': details['receita'],
                            'pdf_url': details.get('pdf_url', ''),
                            'pdf_base64': details.get('pdf_base64', ''),
                            'origem': self.name
                        })
                        count += 1
                        
                        if count % 10 == 0:
                            print(f"  Processed {count} patterns...")
                    
                    # Rate limiting
                    await asyncio.sleep(1.0)
        
        return recipes_data