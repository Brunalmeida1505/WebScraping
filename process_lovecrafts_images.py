"""
Script para extrair imagens de PDFs já baixados do Lovecrafts
e atualizar o CSV com os caminhos das imagens

Similar ao process_scribd_images.py, mas para Lovecrafts.
"""
import os
import sys
import pandas as pd
from pathlib import Path
import re

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    PYMUPDF_AVAILABLE = True
    print("✓ PyMuPDF disponível!\n")
except ImportError as e:
    print(f"✗ PyMuPDF não disponível: {e}")
    print("  Instale com: pip install PyMuPDF Pillow")
    sys.exit(1)

# Configurações
MIN_WIDTH = 150
MIN_HEIGHT = 150
MAX_ASPECT_RATIO = 3.0

def extract_image_from_pdf(pdf_path: str, pdf_basename: str, images_dir: str) -> tuple:
    """
    Extracts the first valid image from a PDF file.
    Returns: (image_url, image_local_path)
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return ("N/A", "N/A")
    
    try:
        pdf = fitz.open(pdf_path)
        max_pages = min(3, len(pdf))
        
        for page_num in range(max_pages):
            page = pdf[page_num]
            image_list = page.get_images()
            
            if not image_list:
                continue
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = pdf.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Validate image with Pillow
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    width, height = pil_img.size
                    
                    # Apply filters
                    if width < MIN_WIDTH or height < MIN_HEIGHT:
                        continue
                    
                    aspect_ratio = max(width, height) / min(width, height)
                    if aspect_ratio > MAX_ASPECT_RATIO:
                        continue
                    
                    # Save image
                    output_filename = f"{pdf_basename}_page{page_num+1}_{img_index}.{image_ext}"
                    output_path = os.path.join(images_dir, output_filename)
                    
                    with open(output_path, "wb") as img_file:
                        img_file.write(image_bytes)
                    
                    pdf.close()
                    return (output_filename, output_path)
                    
                except Exception as e:
                    continue
        
        pdf.close()
        return ("N/A", "N/A")
        
    except Exception as e:
        return ("ERROR", "ERROR")


def normalize_filename(filename: str) -> str:
    """Normaliza nome de arquivo para matching."""
    if not filename or pd.isna(filename):
        return ''
    # Remove extensão e normaliza
    name = str(filename).lower().replace('.pdf', '')
    return name


def find_pdf_for_url(url: str, pdf_files: list, csv_df: pd.DataFrame) -> str:
    """Tenta encontrar o PDF correspondente a uma URL."""
    if not url or pd.isna(url):
        return None
    
    # Extrair possíveis identificadores da URL
    url_parts = url.rstrip('/').split('/')
    url_slug = url_parts[-1] if url_parts else ''
    
    # Tentar match por título primeiro (do CSV)
    matching_rows = csv_df[csv_df['url'] == url]
    if not matching_rows.empty:
        titulo = matching_rows.iloc[0].get('titulo', '')
        if titulo and not pd.isna(titulo):
            titulo_norm = normalize_filename(titulo)
            # Procurar PDF com nome similar
            for pdf_path in pdf_files:
                pdf_name = normalize_filename(Path(pdf_path).stem)
                if titulo_norm in pdf_name or pdf_name in titulo_norm:
                    return pdf_path
    
    # Se não encontrou por título, tentar por slug da URL
    url_norm = normalize_filename(url_slug)
    for pdf_path in pdf_files:
        pdf_name = normalize_filename(Path(pdf_path).stem)
        if url_norm in pdf_name or pdf_name in url_norm:
            return pdf_path
    
    return None


def main():
    print("=" * 80)
    print("PROCESSAMENTO DE IMAGENS DE PDFs DO LOVECRAFTS")
    print("=" * 80)
    
    # Paths
    csv_path = 'db/resultados/lovecrafts_dados.csv'
    pdf_dir = Path('downloads/pdfs/lovecrafts')
    images_dir = Path('downloads/images/lovecrafts_images')
    
    # Create images directory
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Load CSV
    print(f"\n📂 Carregando CSV: {csv_path}")
    if not os.path.exists(csv_path):
        print(f"✗ CSV não encontrado: {csv_path}")
        return
    
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')
    print(f"   ✓ {len(df)} registros carregados")
    
    # Ensure columns exist
    if 'imagem_local' not in df.columns:
        df['imagem_local'] = None
    if 'imagem_url' not in df.columns:
        df['imagem_url'] = None
    
    # Get all PDFs
    if not pdf_dir.exists():
        print(f"✗ Diretório de PDFs não encontrado: {pdf_dir}")
        return
    
    pdf_files = list(pdf_dir.glob('*.pdf'))
    print(f"\n📁 PDFs encontrados: {len(pdf_files)}")
    
    if not pdf_files:
        print("✗ Nenhum PDF encontrado para processar")
        return
    
    # Since Lovecrafts PDFs have hash names, we'll process all PDFs
    # and try to match them to URLs
    print(f"   Processando TODOS os {len(pdf_files)} PDFs...")
    
    # Create a map of already processed images
    existing_images = {normalize_filename(Path(img).stem): img 
                      for img in images_dir.glob('*') if img.suffix.lower() in ['.jpg', '.jpeg', '.png']}
    
    print(f"\n🔄 Iniciando processamento...")
    print(f"   Filtros: min {MIN_WIDTH}x{MIN_HEIGHT}px, aspect ratio < {MAX_ASPECT_RATIO}")
    print()
    
    # Process PDFs
    processed = 0
    success = 0
    skipped = 0
    
    # Create a mapping: PDF basename -> image path
    pdf_to_image = {}
    
    for i, pdf_path in enumerate(pdf_files, 1):
        pdf_basename = pdf_path.stem
        pdf_basename_norm = normalize_filename(pdf_basename)
        
        # Skip if already processed
        if pdf_basename_norm in existing_images:
            pdf_to_image[pdf_basename] = existing_images[pdf_basename_norm]
            skipped += 1
            continue
        
        # Extract image
        img_url, img_local = extract_image_from_pdf(
            str(pdf_path),
            pdf_basename,
            str(images_dir)
        )
        
        processed += 1
        
        if img_local not in ("N/A", "ERROR"):
            success += 1
            pdf_to_image[pdf_basename] = img_local
            size_kb = os.path.getsize(img_local) / 1024
            status = "✓"
            print(f"[{i}/{len(pdf_files)}] {pdf_path.name[:50]:<50} {status} ({size_kb:.1f} KB)")
        else:
            # Still add to map with N/A
            pdf_to_image[pdf_basename] = img_local
    
    print(f"\n   Processados: {processed}, Sucesso: {success}, Pulados: {skipped}")
    
    # Now update CSV by trying to match URLs to PDFs
    print(f"\n🔗 Vinculando imagens ao CSV...")
    updated = 0
    
    for idx, row in df.iterrows():
        # Skip if already has image
        current_img = row.get('imagem_local')
        if current_img and not pd.isna(current_img) and str(current_img).strip() not in ('', 'N/A', 'ERROR'):
            continue
        
        url = row.get('url')
        if not url or pd.isna(url):
            continue
        
        # Try to find PDF for this URL
        pdf_path = find_pdf_for_url(url, [str(p) for p in pdf_files], df)
        
        if pdf_path:
            pdf_basename = Path(pdf_path).stem
            if pdf_basename in pdf_to_image:
                img_path = pdf_to_image[pdf_basename]
                df.at[idx, 'imagem_local'] = img_path
                df.at[idx, 'imagem_url'] = img_path
                updated += 1
    
    print(f"   ✓ {updated} registros vinculados")
    
    # Save updated CSV
    print(f"\n💾 Salvando CSV atualizado...")
    df.to_csv(csv_path, index=False, sep=';', encoding='utf-8-sig')
    print(f"   ✓ CSV salvo: {csv_path}")
    
    # Statistics
    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"  Total processado: {len(pdf_files)}")
    print(f"  ✓ Com imagens: {success} ({success/len(pdf_files)*100:.1f}%)")
    print(f"  ✗ Sem imagens: {len(pdf_files) - success} ({(len(pdf_files) - success)/len(pdf_files)*100:.1f}%)")
    
    # Directory statistics
    all_images = list(images_dir.glob('*.jpeg')) + list(images_dir.glob('*.jpg')) + list(images_dir.glob('*.png'))
    if all_images:
        total_size = sum(img.stat().st_size for img in all_images)
        avg_size = total_size / len(all_images)
        print(f"\n  Imagens salvas em: {images_dir}")
        print(f"  Total de imagens no diretório: {len(all_images)}")
        print(f"  Tamanho total: {total_size / (1024*1024):.2f} MB")
        print(f"  Tamanho médio: {avg_size / 1024:.1f} KB")
    
    # CSV statistics
    csv_imgs = df['imagem_local'].notna().sum()
    print(f"\n  Registros no CSV com imagens: {csv_imgs} ({csv_imgs/len(df)*100:.1f}%)")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
