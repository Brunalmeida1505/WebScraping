"""
Script para extrair imagens de PDFs já baixados do Scribd
e atualizar o CSV com os caminhos das imagens
"""
import os
import sys
import pandas as pd

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

def extract_image_from_pdf(pdf_path: str, document_slug: str, images_dir: str) -> tuple:
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
                    
                    img_obj = Image.open(io.BytesIO(image_bytes))
                    width, height = img_obj.size
                    
                    # Filter: minimum 150x150
                    if width < 150 or height < 150:
                        continue
                    
                    # Filter: skip banners
                    aspect_ratio = max(width, height) / min(width, height)
                    if aspect_ratio > 3:
                        continue
                    
                    # Save the image
                    filename = f"{document_slug}_page{page_num+1}_{img_index}.{image_ext}"
                    filepath = os.path.join(images_dir, filename)
                    
                    # Check if already exists
                    if os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        if file_size > 1000:
                            pdf.close()
                            return (f"PDF_PAGE_{page_num+1}", filepath)
                    
                    # Save image
                    with open(filepath, 'wb') as img_file:
                        img_file.write(image_bytes)
                    
                    pdf.close()
                    return (f"PDF_PAGE_{page_num+1}", filepath)
                    
                except Exception:
                    continue
        
        pdf.close()
        return ("N/A", "N/A")
        
    except Exception:
        return ("N/A", "N/A")

if __name__ == "__main__":
    print("="*80)
    print("PROCESSAMENTO DE IMAGENS DE PDFs DO SCRIBD")
    print("="*80)
    
    # Diretórios
    pdf_dir = "downloads/pdfs/scribd"
    images_dir = "downloads/images/scribd_images"
    csv_path = "db/resultados/scribd_dados.csv"
    
    os.makedirs(images_dir, exist_ok=True)
    
    # Carregar CSV
    print(f"\n📂 Carregando CSV: {csv_path}")
    df = pd.read_csv(csv_path, encoding='utf-8')
    print(f"   ✓ {len(df)} registros carregados")
    
    # Pegar PDFs que existem
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    print(f"\n📁 PDFs encontrados: {len(pdf_files)}")
    
    # Processar TODOS os PDFs
    limit = len(pdf_files)
    print(f"   Processando TODOS os {limit} PDFs...\n")
    
    results = []
    success = 0
    failed = 0
    
    for idx, pdf_file in enumerate(pdf_files[:limit], 1):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        document_slug = pdf_file.replace('.pdf', '')
        
        print(f"[{idx}/{limit}] {pdf_file[:60]:<60}", end=" ")
        
        imagem_url, imagem_local = extract_image_from_pdf(pdf_path, document_slug, images_dir)
        
        if imagem_local != "N/A":
            size_kb = os.path.getsize(imagem_local) / 1024
            print(f"✓ ({size_kb:.1f} KB)")
            success += 1
        else:
            print("✗ Sem imagens")
            failed += 1
        
        results.append({
            'pdf_file': pdf_file,
            'imagem_url': imagem_url,
            'imagem_local': imagem_local
        })
    
    # Resumo
    print(f"\n{'='*80}")
    print("RESUMO")
    print(f"{'='*80}")
    print(f"  Total processado: {len(results)}")
    print(f"  ✓ Com imagens: {success} ({success/len(results)*100:.1f}%)")
    print(f"  ✗ Sem imagens: {failed} ({failed/len(results)*100:.1f}%)")
    print(f"\n  Imagens salvas em: {images_dir}/")
    
    total_images = len([f for f in os.listdir(images_dir) if os.path.isfile(os.path.join(images_dir, f))])
    print(f"  Total de imagens no diretório: {total_images}")
    
    # Calcular tamanho total
    total_size = sum(os.path.getsize(os.path.join(images_dir, f)) 
                     for f in os.listdir(images_dir) 
                     if os.path.isfile(os.path.join(images_dir, f)))
    print(f"  Tamanho total: {total_size / (1024*1024):.2f} MB")
    print(f"  Tamanho médio: {total_size / total_images / 1024:.1f} KB")
    
    # Criar DataFrame com mapeamento PDF -> imagem
    print(f"\n{'='*80}")
    print("ATUALIZANDO CSV COM IMAGENS")
    print(f"{'='*80}")
    
    df_results = pd.DataFrame(results)
    
    # Criar dicionário de mapeamento: nome_arquivo -> (imagem_url, imagem_local)
    filename_to_image = {}
    for _, row in df_results.iterrows():
        if row['imagem_local'] != "N/A":
            filename_to_image[row['pdf_file']] = (row['imagem_url'], row['imagem_local'])
    
    print(f"\n  Mapeamento criado: {len(filename_to_image)} PDFs com imagens")
    
    # Atualizar DataFrame principal
    updated_count = 0
    for idx, row in df.iterrows():
        if pd.notna(row.get('pdf_path')) and row['pdf_path'] not in ['N/A', '', None]:
            # Extrair apenas o nome do arquivo do caminho completo
            pdf_path = str(row['pdf_path'])
            pdf_filename = os.path.basename(pdf_path)
            
            if pdf_filename in filename_to_image:
                imagem_url, imagem_local = filename_to_image[pdf_filename]
                df.at[idx, 'imagem_url'] = imagem_url
                df.at[idx, 'imagem_local'] = imagem_local
                updated_count += 1
    
    print(f"  ✓ Atualizados {updated_count} registros no CSV")
    
    # Salvar CSV atualizado
    df.to_csv(csv_path, index=False, encoding='utf-8')
    print(f"  ✓ CSV salvo: {csv_path}")
    
    print()
