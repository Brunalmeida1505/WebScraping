"""
Script para baixar imagens das receitas do Ravelry
e atualizar o CSV com os caminhos das imagens

Diferente do Scribd (que extrai de PDFs), o Ravelry fornece URLs de imagens
através da API. Este script baixa essas imagens e atualiza o CSV.
"""
import os
import sys
import asyncio
import aiohttp
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import re

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
    print("✓ Pillow disponível!\n")
except ImportError as e:
    print(f"✗ Pillow não disponível: {e}")
    print("  Instale com: pip install Pillow")
    sys.exit(1)

# Configurações
MIN_WIDTH = 150
MIN_HEIGHT = 150
MAX_ASPECT_RATIO = 3.0

class RavelryImageProcessor:
    def __init__(self):
        self.csv_path = 'db/resultados/ravelry_dados.csv'
        self.images_dir = Path('downloads/images/ravelry_images')
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        # Carregar credenciais
        env_path = Path(__file__).parent / '.env'
        load_dotenv(dotenv_path=env_path, override=True)
        
        self.username = os.getenv('RAVELRY_USERNAME')
        self.api_key = os.getenv('RAVELRY_APIKEY')
        self.password = os.getenv('RAVELRY_PASSWORD')
        
        if not self.username or not (self.api_key or self.password):
            raise ValueError("Ravelry credentials not found in .env file")
        
        # Determinar credencial a usar
        if self.api_key:
            self.auth = aiohttp.BasicAuth(self.username, self.api_key)
        else:
            self.auth = aiohttp.BasicAuth(self.username, self.password)
    
    def extract_pattern_id_from_url(self, url: str) -> str:
        """Extrai o ID ou slug do padrão da URL do Ravelry."""
        if not url or pd.isna(url):
            return None
        
        # Padrões de URL do Ravelry:
        # https://www.ravelry.com/patterns/library/pattern-name
        # https://www.ravelry.com/patterns/library/pattern-name-2
        patterns = [
            r'/patterns/library/([a-zA-Z0-9-]+)',
            r'/patterns/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def get_pattern_images_from_api(self, pattern_slug: str, session: aiohttp.ClientSession) -> list:
        """Busca URLs de imagens do padrão via API do Ravelry."""
        try:
            # Tentar buscar por slug
            async with session.get(
                f'https://api.ravelry.com/patterns/{pattern_slug}.json',
                timeout=30
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pattern = data.get('pattern', {})
                    
                    # Coletar todas as URLs de imagens disponíveis
                    image_urls = []
                    
                    # 1. Foto principal
                    photos = pattern.get('photos', [])
                    for photo in photos:
                        # Preferir 'medium' ou 'small' para tamanho razoável
                        if 'medium_url' in photo:
                            image_urls.append(photo['medium_url'])
                        elif 'small_url' in photo:
                            image_urls.append(photo['small_url'])
                        elif 'thumbnail_url' in photo:
                            image_urls.append(photo['thumbnail_url'])
                    
                    # 2. Craft photo (imagem do tipo de artesanato)
                    craft = pattern.get('craft', {})
                    if craft and 'permalink' in craft:
                        # Imagem do craft pode não ser útil, pular
                        pass
                    
                    return image_urls
                
        except Exception as e:
            pass
        
        return []
    
    async def download_image(self, url: str, output_path: Path, session: aiohttp.ClientSession) -> bool:
        """Baixa uma imagem e valida seus critérios."""
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    return False
                
                image_bytes = await resp.read()
                
                # Validar imagem com Pillow
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    width, height = img.size
                    
                    # Aplicar filtros
                    if width < MIN_WIDTH or height < MIN_HEIGHT:
                        return False
                    
                    aspect_ratio = max(width, height) / min(width, height)
                    if aspect_ratio > MAX_ASPECT_RATIO:
                        return False
                    
                    # Salvar imagem
                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    return True
                    
                except Exception as e:
                    return False
                    
        except Exception as e:
            return False
    
    async def process_row(self, idx: int, row: pd.Series, session: aiohttp.ClientSession) -> dict:
        """Processa uma linha do CSV para extrair imagem."""
        url = row.get('url')
        titulo = row.get('titulo', 'unknown')
        
        # Skip se já tem imagem
        current_image = row.get('imagem_local')
        if current_image and not pd.isna(current_image) and str(current_image).strip() not in ('', 'N/A', 'ERROR'):
            return None
        
        # Extrair ID/slug do padrão
        pattern_slug = self.extract_pattern_id_from_url(url)
        if not pattern_slug:
            return {'idx': idx, 'imagem_local': 'ERROR', 'imagem_url': 'ERROR'}
        
        # Buscar URLs de imagens na API
        image_urls = await self.get_pattern_images_from_api(pattern_slug, session)
        
        if not image_urls:
            return {'idx': idx, 'imagem_local': 'N/A', 'imagem_url': 'N/A'}
        
        # Tentar baixar a primeira imagem válida
        for img_url in image_urls[:3]:  # Limitar a 3 tentativas
            # Criar nome de arquivo baseado no slug e índice
            safe_slug = re.sub(r'[^\w\-]', '_', pattern_slug)[:50]
            output_filename = f"{safe_slug}.jpeg"
            output_path = self.images_dir / output_filename
            
            # Se já existe, não baixar novamente
            if output_path.exists():
                return {
                    'idx': idx,
                    'imagem_local': str(output_path),
                    'imagem_url': img_url
                }
            
            # Baixar imagem
            success = await self.download_image(img_url, output_path, session)
            
            if success:
                return {
                    'idx': idx,
                    'imagem_local': str(output_path),
                    'imagem_url': img_url
                }
        
        # Nenhuma imagem válida encontrada
        return {'idx': idx, 'imagem_local': 'N/A', 'imagem_url': 'N/A'}
    
    async def process_all_async(self):
        """Processa todas as receitas de forma assíncrona."""
        print("=" * 80)
        print("PROCESSAMENTO DE IMAGENS DO RAVELRY")
        print("=" * 80)
        
        # Carregar CSV
        print(f"\n📂 Carregando CSV: {self.csv_path}")
        if not os.path.exists(self.csv_path):
            print(f"✗ CSV não encontrado: {self.csv_path}")
            return
        
        df = pd.read_csv(self.csv_path, sep=';', encoding='utf-8-sig')
        print(f"   ✓ {len(df)} registros carregados")
        
        # Garantir colunas existem
        if 'imagem_local' not in df.columns:
            df['imagem_local'] = None
        if 'imagem_url' not in df.columns:
            df['imagem_url'] = None
        
        # Filtrar apenas registros sem imagem
        needs_processing = df[
            df['imagem_local'].isna() | 
            (df['imagem_local'] == '') | 
            (df['imagem_local'] == 'N/A') |
            (df['imagem_local'] == 'ERROR')
        ]
        
        print(f"\n📊 Registros a processar: {len(needs_processing)}")
        if len(needs_processing) == 0:
            print("   ℹ Todos os registros já têm imagens processadas")
            return
        
        # Criar sessão HTTP com autenticação
        headers = {
            'User-Agent': 'AmigurumiScraper/1.0',
            'Accept': 'application/json'
        }
        
        results = []
        success_count = 0
        na_count = 0
        error_count = 0
        
        async with aiohttp.ClientSession(headers=headers, auth=self.auth) as session:
            print(f"\n🔄 Processando registros...")
            print(f"   Filtros: min {MIN_WIDTH}x{MIN_HEIGHT}px, aspect ratio < {MAX_ASPECT_RATIO}")
            print()
            
            # Processar em lotes para não sobrecarregar
            batch_size = 10
            for i in range(0, len(needs_processing), batch_size):
                batch = needs_processing.iloc[i:i+batch_size]
                
                # Processar batch
                tasks = []
                for idx, row in batch.iterrows():
                    tasks.append(self.process_row(idx, row, session))
                
                batch_results = await asyncio.gather(*tasks)
                
                # Atualizar DataFrame e contadores
                for result in batch_results:
                    if result:
                        results.append(result)
                        idx = result['idx']
                        df.at[idx, 'imagem_local'] = result['imagem_local']
                        df.at[idx, 'imagem_url'] = result['imagem_url']
                        
                        if result['imagem_local'] not in ('N/A', 'ERROR'):
                            success_count += 1
                            size_kb = os.path.getsize(result['imagem_local']) / 1024
                            print(f"[{i+len(batch_results)}/{len(needs_processing)}] {Path(result['imagem_local']).name[:50]:<50} ✓ ({size_kb:.1f} KB)")
                        elif result['imagem_local'] == 'N/A':
                            na_count += 1
                        else:
                            error_count += 1
                
                # Rate limiting
                await asyncio.sleep(1.0)
        
        # Salvar CSV atualizado
        print(f"\n💾 Salvando CSV atualizado...")
        df.to_csv(self.csv_path, index=False, sep=';', encoding='utf-8-sig')
        print(f"   ✓ CSV salvo: {self.csv_path}")
        
        # Estatísticas finais
        print("\n" + "=" * 80)
        print("RESUMO")
        print("=" * 80)
        print(f"  Total processado: {len(needs_processing)}")
        print(f"  ✓ Com imagens: {success_count} ({success_count/len(needs_processing)*100:.1f}%)")
        print(f"  ✗ Sem imagens: {na_count} ({na_count/len(needs_processing)*100:.1f}%)")
        print(f"  ⚠ Erros: {error_count}")
        
        # Estatísticas do diretório
        images = list(self.images_dir.glob('*.jpeg')) + list(self.images_dir.glob('*.jpg')) + list(self.images_dir.glob('*.png'))
        if images:
            total_size = sum(img.stat().st_size for img in images)
            avg_size = total_size / len(images)
            print(f"\n  Imagens salvas em: {self.images_dir}")
            print(f"  Total de imagens no diretório: {len(images)}")
            print(f"  Tamanho total: {total_size / (1024*1024):.2f} MB")
            print(f"  Tamanho médio: {avg_size / 1024:.1f} KB")
        
        print("\n" + "=" * 80)
    
    def run(self):
        """Executa o processamento."""
        asyncio.run(self.process_all_async())


if __name__ == '__main__':
    processor = RavelryImageProcessor()
    processor.run()
