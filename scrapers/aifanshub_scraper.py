"""
AIFansHub Scraper - Padrões de amigurumi
Site: https://www.aifanshub.com/search/label/AMIGURUMI%20PATTERN

Dados extraídos:
- titulo, url, imagem_url, imagem_local
- materiais, abreviações, receita, origem

IMPORTANTE: Este scraper usa Selenium para lidar com carregamento dinâmico
de posts via JavaScript (scroll infinito).
"""

import requests
from bs4 import BeautifulSoup, Comment
import pandas as pd
from pathlib import Path
import time
import re
from urllib.parse import urljoin
from PIL import Image
from io import BytesIO
import hashlib
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base_scraper import ScraperStrategy


class AIFansHubScraperCore:
    def __init__(self, driver=None, label='AMIGURUMI%20PATTERN'):
        self.base_url = "https://www.aifanshub.com"
        self.label = label
        self.search_url = f"{self.base_url}/search/label/{label}"
        self.driver = driver
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.aifanshub.com/'
        })
        
        # Diretórios
        self.base_dir = Path(__file__).parent.parent
        self.db_dir = self.base_dir / "db" / "resultados"
        self.images_dir = self.base_dir / "downloads" / "images" / "aifanshub_images"
        self.urls_file = self.base_dir / "db" / "aifanshub_urls.txt"
        
        # Criar diretórios
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        self.patterns = []
        
    def extract_post_links(self, html_content):
        """Extrai links de posts da página de listagem"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # Procurar por links de artigos
        # Padrão: <a href="https://www.aifanshub.com/YYYY/MM/post-title.html">
        article_links = soup.find_all('a', href=re.compile(r'/\d{4}/\d{2}/.*\.html'))
        
        for link in article_links:
            href = link.get('href')
            if href and 'aifanshub.com' in href:
                # Filtrar URLs externas (Pinterest, etc)
                if any(skip in href.lower() for skip in ['pinterest.com', 'facebook.com', 'twitter.com', 'instagram.com']):
                    continue
                # Pegar apenas links únicos
                if href not in links:
                    links.append(href)
        
        return links
    
    def get_pagination_token(self, soup):
        """Extrai token de paginação para carregar mais posts"""
        # Blogger usa um sistema de paginação com max-results e continuation token
        # Procurar por scripts que contenham informações de paginação
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'continuation' in script.string.lower():
                # Extrair token se existir
                match = re.search(r'continuation["\']?\s*:\s*["\']([^"\']+)', script.string)
                if match:
                    return match.group(1)
        return None
    
    def scroll_and_load_posts(self, max_scrolls=100):
        """Realiza scroll na página para carregar posts dinamicamente"""
        if not self.driver:
            print("⚠️  WebDriver não disponível, usando método alternativo...")
            return self.scrape_listing_page_requests()
        
        print(f"\n{'='*80}")
        print("SCRAPING DE LISTAGEM - AIFANSHUB (com scroll dinâmico)")
        print(f"{'='*80}\n")
        
        print(f"🌐 Acessando: {self.search_url}")
        self.driver.get(self.search_url)
        time.sleep(3)  # Aguardar carregamento inicial
        
        all_links = set()
        last_height = 0
        scrolls_without_new_content = 0
        
        for scroll_num in range(1, max_scrolls + 1):
            print(f"\n🔄 Scroll {scroll_num}/{max_scrolls}...")
            
            # Extrair links atuais
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            current_links = self.extract_post_links(str(soup))
            
            new_links = [link for link in current_links if link not in all_links]
            all_links.update(new_links)
            
            print(f"   ✓ Links novos: {len(new_links)} | Total: {len(all_links)}")
            
            # Verificar se há novos posts
            if len(new_links) == 0:
                scrolls_without_new_content += 1
                print(f"   ⚠️  Sem novos posts ({scrolls_without_new_content}/3)")
                
                if scrolls_without_new_content >= 3:
                    print(f"\n✓ Sem mais conteúdo após {scrolls_without_new_content} tentativas")
                    break
            else:
                scrolls_without_new_content = 0
            
            # Realizar scroll
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Aguardar carregamento
            
            # Verificar se altura mudou
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"   ℹ️  Altura da página não mudou")
            else:
                print(f"   ↕️  Altura: {last_height} → {new_height}")
            last_height = new_height
        
        # Salvar URLs
        print(f"\n💾 Salvando {len(all_links)} URLs...")
        with open(self.urls_file, 'w', encoding='utf-8') as f:
            for link in sorted(all_links):
                f.write(f"{link}\n")
        
        print(f"   ✓ URLs salvas em: {self.urls_file}")
        return list(all_links)
    
    def scrape_listing_page_requests(self, max_pages=5):
        """Método alternativo usando requests (sem Selenium)"""
        print(f"\n{'='*80}")
        print("SCRAPING DE LISTAGEM - AIFANSHUB (requests)")
        print(f"{'='*80}\n")
        
        all_links = set()
        current_url = self.search_url
        
        for page in range(1, max_pages + 1):
            print(f"📄 Página {page}/{max_pages}...")
            
            try:
                response = self.session.get(current_url, timeout=30)
                response.raise_for_status()
                
                links = self.extract_post_links(response.text)
                new_links = [link for link in links if link not in all_links]
                all_links.update(new_links)
                
                print(f"   ✓ Encontrados {len(new_links)} novos links (Total: {len(all_links)})")
                
                # Tentar obter próxima página
                if page < max_pages:
                    time.sleep(2)
                    start_param = page * 20
                    current_url = f"{self.search_url}?max-results=20&start={start_param}"
                
            except Exception as e:
                print(f"   ✗ Erro na página {page}: {e}")
                break
        
        # Salvar URLs
        print(f"\n💾 Salvando {len(all_links)} URLs...")
        with open(self.urls_file, 'w', encoding='utf-8') as f:
            for link in sorted(all_links):
                f.write(f"{link}\n")
        
        print(f"   ✓ URLs salvas em: {self.urls_file}")
        return list(all_links)
    
    def clean_soup_from_footer(self, soup):
        """Remove todo conteúdo após o comentário INTERNAL LINKS FOOTER"""
        # Método 1: Remover via comentário INTERNAL LINKS FOOTER
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if 'INTERNAL LINKS FOOTER' in comment.upper():
                # Remover todos os elementos após este comentário
                next_elem = comment.next_sibling
                while next_elem:
                    next_to_remove = next_elem.next_sibling
                    if hasattr(next_elem, 'extract'):
                        next_elem.extract()
                    next_elem = next_to_remove
                # Remover o próprio comentário
                comment.extract()
                break
        
        # Método 2: Remover elementos com class="site-footer"
        site_footers = soup.find_all(class_='site-footer')
        for footer in site_footers:
            footer.extract()
        
        # Método 3: Remover seções específicas indesejadas
        # Remover "What Our Community Says" (reviews/depoimentos)
        community_sections = soup.find_all(['section', 'div'], 
                                          string=re.compile(r'What Our Community Says', re.I))
        for section in community_sections:
            # Se o texto está em um título, remover a section pai
            if section.name in ['h2', 'h3', 'h4', 'h5']:
                parent = section.find_parent(['section', 'div', 'article'])
                if parent:
                    parent.extract()
            else:
                section.extract()
        
        # Remover por título dentro de sections
        sections_with_community = soup.find_all('section')
        for section in sections_with_community:
            title = section.find(['h2', 'h3', 'h4', 'h5'])
            if title and 'COMMUNITY SAYS' in title.get_text().upper():
                section.extract()
        
        # Remover outras seções comuns de footer
        unwanted_patterns = [
            r'More Patterns',
            r'Related Posts',
            r'You Might Also Like',
            r'Popular Posts'
        ]
        for pattern in unwanted_patterns:
            unwanted_sections = soup.find_all('section', string=re.compile(pattern, re.I))
            for section in unwanted_sections:
                section.extract()
        
        # Remover copyright e outros textos de rodapé
        copyright_texts = soup.find_all(string=re.compile(r'©.*AIFansHub|All rights reserved|Privacy Policy', re.I))
        for text in copyright_texts:
            if hasattr(text, 'parent') and text.parent:
                text.parent.extract()
        
        return soup
    
    def extract_pattern_data(self, url):
        """Extrai dados de um post de padrão"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # IMPORTANTE: Limpar conteúdo após INTERNAL LINKS FOOTER
            soup = self.clean_soup_from_footer(soup)
            
            # Título
            title = None
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # Materiais
            materiais = self.extract_materials(soup)
            
            # Abreviações
            abreviacoes = self.extract_abbreviations(soup)
            
            # Receita (padrão completo)
            receita = self.extract_pattern_instructions(soup)
            
            # Origem
            origem = "AIFansHub"
            
            # Imagem principal
            imagem_url = self.extract_main_image(soup, url)
            
            pattern_data = {
                'titulo': title,
                'url': url,
                'imagem_url': imagem_url,
                'imagem_local': None,  # Será preenchido após download
                'materiais': materiais,
                'abreviacoes': abreviacoes,
                'receita': receita,
                'origem': origem
            }
            
            return pattern_data
            
        except Exception as e:
            print(f"   ✗ Erro ao extrair dados de {url}: {e}")
            return None
    
    def extract_materials(self, soup):
        """Extrai lista de materiais"""
        materials = []
        
        # Procurar por seção de materiais
        materials_section = soup.find(string=re.compile(r'Materials?:', re.I))
        if materials_section:
            # Tentar encontrar lista após "Materials:"
            parent = materials_section.parent
            if parent:
                # Procurar próximos elementos que sejam listas ou texto
                for sibling in parent.next_siblings:
                    if sibling.name in ['ul', 'ol']:
                        for li in sibling.find_all('li'):
                            text = li.get_text(strip=True)
                            if text:
                                materials.append(text)
                        break
                    elif sibling.string and ':' not in sibling.string and len(sibling.string.strip()) > 10:
                        materials.append(sibling.string.strip())
        
        # Alternativa: procurar em PROJECT INFO
        if not materials:
            project_info = soup.find(string=re.compile(r'PROJECT INFO', re.I))
            if project_info:
                parent = project_info.find_parent()
                if parent:
                    text = parent.get_text()
                    # Procurar linha de Materials
                    match = re.search(r'Materials?:\s*(.+?)(?:Hook Size:|Difficulty:|$)', text, re.I | re.DOTALL)
                    if match:
                        materials_text = match.group(1).strip()
                        materials = [m.strip() for m in materials_text.split(',') if m.strip()]
        
        return ' | '.join(materials) if materials else None
    
    def extract_abbreviations(self, soup):
        """Extrai abreviações de crochê"""
        abbreviations = {}
        
        # Método 1: Procurar pelo comentário HTML <!--ABBREVIATIONS -->
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if 'ABBREVIATIONS' in comment.upper():
                # Pegar o próximo elemento <section> após o comentário
                next_elem = comment.next_sibling
                while next_elem:
                    if hasattr(next_elem, 'name') and next_elem.name == 'section':
                        # Encontrou a section de abreviações
                        text = next_elem.get_text()
                        # Padrão: MR: Magic Ring (adjustable loop)
                        # Buscar linhas no formato "SIGLA: Descrição"
                        lines = text.split('\n')
                        for line in lines:
                            line = line.strip()
                            # Match: 1-4 letras maiúsculas seguidas de : e descrição
                            match = re.match(r'^([A-Z]{1,4}):\s*(.+?)$', line)
                            if match:
                                abbr = match.group(1).strip()
                                meaning = match.group(2).strip()
                                # Remover texto entre parênteses se houver
                                meaning = re.sub(r'\s*\([^)]*\)\s*$', '', meaning)
                                abbreviations[abbr] = meaning
                        break
                    next_elem = next_elem.next_sibling
                
                # Se encontrou abreviações, não precisa procurar mais
                if abbreviations:
                    break
        
        # Método 2 (fallback): Procurar por seção KEY ABBREVIATIONS via texto
        if not abbreviations:
            abbr_section = soup.find(string=re.compile(r'KEY ABBREVIATIONS', re.I))
            if abbr_section:
                parent = abbr_section.find_parent()
                if parent:
                    # Procurar lista de abreviações
                    text = parent.get_text()
                    # Padrão: MR: Magic Ring, sc: Single Crochet, etc
                    matches = re.findall(r'([A-Z]{1,4}):\s*([^\n]+?)(?=\n|$)', text)
                    for abbr, meaning in matches:
                        abbr = abbr.strip()
                        meaning = meaning.strip()
                        # Pular a linha do título
                        if abbr in ['KEY']:
                            continue
                        # Remover texto entre parênteses
                        meaning = re.sub(r'\s*\([^)]*\)\s*$', '', meaning)
                        abbreviations[abbr] = meaning
        
        if abbreviations:
            # Formato: "MR: Magic Ring | sc: Single Crochet | ..."
            return ' | '.join([f"{k}: {v}" for k, v in abbreviations.items()])
        return None
    
    def extract_pattern_instructions(self, soup):
        """Extrai instruções completas do padrão"""
        instructions = []
        
        # Procurar por seção "THE PATTERN" ou seções numeradas
        pattern_section = soup.find(string=re.compile(r'THE PATTERN|✨ THE PATTERN', re.I))
        
        if pattern_section:
            parent = pattern_section.find_parent()
            if parent:
                # Encontrar todos os cabeçalhos de seção (SECTION 1, SECTION 2, etc)
                sections = parent.find_all(['h3', 'h4'], string=re.compile(r'SECTION \d+|Part [A-Z]', re.I))
                
                for section in sections:
                    section_title = section.get_text(strip=True)
                    section_content = []
                    
                    # Pegar conteúdo após o cabeçalho até próximo cabeçalho
                    for sibling in section.next_siblings:
                        if sibling.name in ['h3', 'h4'] and re.search(r'SECTION \d+', sibling.get_text(), re.I):
                            break
                        
                        if sibling.name in ['p', 'div']:
                            text = sibling.get_text(strip=True)
                            # Filtrar linhas de receita (começam com R1:, R2:, etc)
                            if re.match(r'R\d+:', text):
                                section_content.append(text)
                    
                    if section_content:
                        instructions.append(f"[{section_title}]\n" + "\n".join(section_content))
        
        # Se não encontrou padrão estruturado, tentar busca genérica
        if not instructions:
            # Procurar todos os parágrafos com padrão R1:, R2:, etc
            all_text = soup.get_text()
            pattern_lines = re.findall(r'R\d+:.*?(?=R\d+:|$)', all_text, re.DOTALL)
            if pattern_lines:
                # Limpar e filtrar
                instructions = [line.strip() for line in pattern_lines if len(line.strip()) > 10]
        
        return '\n\n'.join(instructions) if instructions else None
    
    def extract_main_image(self, soup, post_url):
        """Extrai URL da imagem principal (primeira de alta qualidade)"""
        # Procurar por imagens no conteúdo
        img_tags = soup.find_all('img')
        
        for img in img_tags:
            src = img.get('src') or img.get('data-src')
            
            if not src:
                continue
            
            # Pular imagens pequenas/ícones
            if any(skip in src.lower() for skip in ['icon', 'logo', 'avatar', 'profile', 'favicon']):
                continue
            
            # URLs do Blogger - forçar alta qualidade
            if 'blogger.googleusercontent.com' in src:
                src = re.sub(r'/s\d+(-rw)?/', '/s1600/', src)
                return urljoin(post_url, src)
        
        return None
    
    def download_image(self, img_url, pattern_title):
        """Download e validação de imagem"""
        try:
            response = self.session.get(img_url, timeout=30)
            response.raise_for_status()
            
            # Abrir imagem
            img = Image.open(BytesIO(response.content))
            
            # Validar dimensões mínimas
            width, height = img.size
            if width < 150 or height < 150:
                return None
            
            # Validar aspect ratio
            aspect_ratio = max(width, height) / min(width, height)
            if aspect_ratio > 3.0:
                return None
            
            # Converter para RGB se necessário
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Nome do arquivo baseado no título
            safe_title = re.sub(r'[^\w\s-]', '', pattern_title)
            safe_title = re.sub(r'[-\s]+', '_', safe_title)[:50]
            
            # Hash da URL para garantir unicidade
            url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
            
            filename = f"{safe_title}_{url_hash}.jpeg"
            filepath = self.images_dir / filename
            
            # Salvar como JPEG
            img.save(filepath, 'JPEG', quality=95, optimize=True)
            
            return str(filepath)
            
        except Exception as e:
            print(f"      ✗ Erro ao baixar imagem: {e}")
            return None
    
    def process_pattern(self, url):
        """Processa um padrão: extrai dados e baixa imagem"""
        print(f"\n🔄 Processando: {url}")
        
        # Extrair dados
        pattern_data = self.extract_pattern_data(url)
        
        if not pattern_data:
            return None
        
        print(f"   ✓ Título: {pattern_data['titulo']}")
        
        # Download de imagem
        if pattern_data['imagem_url']:
            print(f"   📥 Baixando imagem...")
            imagem_local = self.download_image(pattern_data['imagem_url'], pattern_data['titulo'] or 'pattern')
            if imagem_local:
                pattern_data['imagem_local'] = imagem_local
                print(f"      ✓ Imagem salva")
            else:
                print(f"      ✗ Falha no download")
        
        return pattern_data
    
    def scrape_all(self, max_scrolls=100, max_patterns=None):
        """Processo completo de scraping"""
        print(f"\n{'='*80}")
        print("SCRAPER AIFANSHUB - PADRÕES DE AMIGURUMI")
        print(f"{'='*80}\n")
        
        # 1. Coletar URLs
        print("📋 ETAPA 1: Coletando URLs dos posts...")
        urls = self.scroll_and_load_posts(max_scrolls=max_scrolls)
        
        if not urls:
            print("❌ Nenhuma URL encontrada!")
            return
        
        print(f"\n✓ Total de URLs coletadas: {len(urls)}")
        
        # Limitar quantidade se especificado
        if max_patterns and max_patterns < len(urls):
            urls = urls[:max_patterns]
            print(f"   Limitando a {max_patterns} padrões")
        
        # 2. Processar cada padrão
        print(f"\n📋 ETAPA 2: Processando {len(urls)} padrões...")
        
        for idx, url in enumerate(urls, 1):
            print(f"\n[{idx}/{len(urls)}]", end=" ")
            pattern_data = self.process_pattern(url)
            
            if pattern_data:
                self.patterns.append(pattern_data)
            
            # Rate limiting
            time.sleep(2)
        
        # 3. Salvar resultados
        print(f"\n{'='*80}")
        print("📊 SALVANDO RESULTADOS")
        print(f"{'='*80}\n")
        
        if not self.patterns:
            print("❌ Nenhum padrão processado com sucesso!")
            return
        
        df = pd.DataFrame(self.patterns)
        
        # Reordenar colunas na ordem especificada
        columns_order = ['titulo', 'url', 'imagem_url', 'imagem_local', 'materiais', 'abreviacoes', 'receita', 'origem']
        # Garantir que todas as colunas existem
        for col in columns_order:
            if col not in df.columns:
                df[col] = None
        df = df[columns_order]
        
        # Salvar CSV
        csv_path = self.db_dir / "aifanshub_dados.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        print(f"✓ CSV salvo: {csv_path}")
        
        # Estatísticas
        self.print_statistics(df)
    
    def print_statistics(self, df):
        """Imprime estatísticas do scraping"""
        print(f"\n{'='*80}")
        print("📊 ESTATÍSTICAS FINAIS")
        print(f"{'='*80}\n")
        
        print(f"Total de padrões: {len(df)}")
        print(f"Padrões com imagens: {df['imagem_local'].notna().sum()} ({df['imagem_local'].notna().sum()/len(df)*100:.1f}%)")
        print(f"Padrões com materiais: {df['materiais'].notna().sum()}")
        print(f"Padrões com abreviações: {df['abreviacoes'].notna().sum()}")
        print(f"Padrões com receita: {df['receita'].notna().sum()}")
        
        # Contar imagens no diretório
        image_files = list(self.images_dir.glob('*.jpeg'))
        if image_files:
            total_size = sum(f.stat().st_size for f in image_files)
            print(f"\nTotal de imagens salvas: {len(image_files)}")
            print(f"Tamanho total: {total_size / (1024*1024):.2f} MB")
            print(f"Tamanho médio: {total_size / len(image_files) / 1024:.1f} KB")
        
        print(f"\n📁 Diretório de imagens: {self.images_dir}")
        print(f"📄 Arquivo CSV: {self.db_dir / 'aifanshub_dados.csv'}")
        
        print(f"\n{'='*80}")


class AIFansHubScraper(ScraperStrategy):
    """
    Wrapper class to integrate AIFansHubScraperCore with the main.py ScraperStrategy pattern.
    """
    
    AVAILABLE_LABELS = {
        'amigurumi': 'AMIGURUMI%20PATTERN',
        'bags': 'BAGS%20PATTERN',
        'style': 'Style',
        'all': 'All%20%20BLOGS'
    }
    
    def __init__(self, driver):
        super().__init__(driver)
        self.driver = driver
        self.core_scraper = AIFansHubScraperCore(driver=driver)
    
    def get_name(self) -> str:
        return "AIFansHub"
    
    def collect_recipe_urls(self) -> set:
        """Coleta URLs usando scroll dinâmico (Selenium) ou requests"""
        urls = self.core_scraper.scroll_and_load_posts(max_scrolls=100)
        return set(urls)
    
    def extract_recipe_details(self, url: str) -> dict:
        """Extrai detalhes de um padrão"""
        return self.core_scraper.extract_pattern_data(url)
    
    def run(self, args: dict):
        """
        Executa o scraper completo.
        
        Args aceitos:
        - max_pages: Número de scrolls para carregar posts (padrão: 100)
        - limit: Número máximo de padrões (padrão: None = todos)
        - label: Categoria (amigurumi|bags|style|all, padrão: amigurumi)
        """
        # Configurar label
        label_key = args.get('label', 'amigurumi')
        if label_key in self.AVAILABLE_LABELS:
            label_encoded = self.AVAILABLE_LABELS[label_key]
            self.core_scraper = AIFansHubScraperCore(driver=self.driver, label=label_encoded)
        
        # Se max_pages for None, usar valor padrão 100 (scrolls)
        max_scrolls = args.get('max_pages')
        if max_scrolls is None:
            max_scrolls = 100
        
        max_patterns = args.get('limit', None)
        
        print(f"\n{'='*80}")
        print(f"SCRAPER: {self.get_name()}")
        print(f"CATEGORIA: {label_key.upper()}")
        print(f"MODO: {'Selenium (scroll dinâmico)' if self.driver else 'Requests (estático)'}")
        print(f"{'='*80}")
        print(f"Configurações:")
        print(f"  • Scrolls para carregar posts: {max_scrolls}")
        print(f"  • Limite de padrões: {max_patterns or 'Todos'}")
        print(f"{'='*80}\n")
        
        
        # Executar scraping completo
        self.core_scraper.scrape_all(max_scrolls=max_scrolls, max_patterns=max_patterns)


def main():
    """Execução principal (standalone)"""
    print("⚠️  ATENÇÃO: Para usar scroll dinâmico, execute via main.py")
    print("   Exemplo: python main.py aifanshub --max-pages 100\n")
    
    scraper = AIFansHubScraperCore(driver=None)
    
    # Configurações
    MAX_SCROLLS = 100     # Número de scrolls para carregar posts
    MAX_PATTERNS = None   # None = todos, ou especificar número (ex: 50)
    
    # Executar scraping completo (sem Selenium, usará requests)
    scraper.scrape_all(max_scrolls=MAX_SCROLLS, max_patterns=MAX_PATTERNS)


if __name__ == "__main__":
    main()
