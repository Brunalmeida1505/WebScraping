"""
Script para codificar PDFs do LoveCrafts em base64 e adicionar ao CSV.
Estratégia: Extrai o título de cada PDF e associa com as receitas do CSV.
"""
import os
import base64
import pandas as pd
import pdfplumber
from pathlib import Path
import sys
import re

# Configurar encoding UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def normalizar_texto(texto):
    """Normaliza texto para comparação (remove acentos, lowercase, espaços extras)."""
    if not texto:
        return ""
    # Converter para lowercase
    texto = texto.lower()
    # Remover caracteres especiais, manter apenas alfanuméricos e espaços
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    # Remover espaços extras
    texto = ' '.join(texto.split())
    return texto

def extrair_titulo_pdf(pdf_path):
    """Extrai o título de um PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > 0:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                if text:
                    # Pegar primeira linha não vazia
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    if lines:
                        return lines[0]
    except Exception as e:
        pass
    return None

def codificar_pdf_base64(pdf_path):
    """Lê um PDF e retorna sua codificação em base64."""
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_bytes = pdf_file.read()
            
            # Validar se é um PDF
            if b'%PDF' not in pdf_bytes[:20]:
                return None
            
            # Codificar em base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            return pdf_base64
    except Exception as e:
        return None

def main():
    print("=" * 80)
    print("  CODIFICAÇÃO DE PDFs DO LOVECRAFTS PARA BASE64")
    print("=" * 80)
    
    # Caminhos
    csv_path = "db/resultados/lovecrafts_dados.csv"
    downloads_dir = "downloads"
    
    # Verificar se CSV existe
    if not os.path.exists(csv_path):
        print(f"✗ CSV não encontrado: {csv_path}")
        return
    
    # Verificar se pasta downloads existe
    if not os.path.exists(downloads_dir):
        print(f"✗ Pasta downloads não encontrada: {downloads_dir}")
        return
    
    # Carregar CSV
    print(f"\n1. Carregando CSV...")
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')
    print(f"   ✓ {len(df)} receitas carregadas")
    
    # Listar todos os PDFs na pasta downloads
    print(f"\n2. Listando e analisando PDFs...")
    pdf_files = list(Path(downloads_dir).glob("*.pdf"))
    print(f"   ✓ {len(pdf_files)} PDFs encontrados")
    
    # Criar mapeamento: título normalizado -> caminho do PDF
    print(f"\n3. Extraindo títulos dos PDFs (pode demorar)...")
    pdf_map = {}
    pdf_titulos_originais = {}
    
    for i, pdf_path in enumerate(pdf_files):
        if (i + 1) % 50 == 0:
            print(f"   ... Processados {i+1}/{len(pdf_files)} PDFs...")
        
        titulo_pdf = extrair_titulo_pdf(pdf_path)
        if titulo_pdf:
            titulo_normalizado = normalizar_texto(titulo_pdf)
            if titulo_normalizado:
                pdf_map[titulo_normalizado] = str(pdf_path)
                pdf_titulos_originais[titulo_normalizado] = titulo_pdf
    
    print(f"   ✓ {len(pdf_map)} PDFs com títulos extraídos")
    
    # Adicionar colunas se não existirem
    if 'pdf_url' not in df.columns:
        df['pdf_url'] = ''
    if 'pdf_base64' not in df.columns:
        df['pdf_base64'] = ''
    
    print(f"\n4. Associando receitas com PDFs e codificando...")
    
    pdfs_codificados = 0
    pdfs_nao_encontrados = 0
    associacoes_parciais = 0
    
    for idx, row in df.iterrows():
        titulo_receita = row['titulo']
        url = row['url']
        
        # Normalizar título da receita
        titulo_normalizado = normalizar_texto(titulo_receita)
        
        # Busca exata
        pdf_encontrado = None
        if titulo_normalizado in pdf_map:
            pdf_encontrado = pdf_map[titulo_normalizado]
        else:
            # Busca parcial (se o título da receita está contido no PDF ou vice-versa)
            for titulo_pdf_norm, pdf_path in pdf_map.items():
                # Se o título da receita está no PDF OU se o título do PDF está na receita
                if (titulo_normalizado in titulo_pdf_norm) or (titulo_pdf_norm in titulo_normalizado):
                    # Verificar se tem pelo menos 50% de correspondência
                    palavras_receita = set(titulo_normalizado.split())
                    palavras_pdf = set(titulo_pdf_norm.split())
                    if palavras_receita and palavras_pdf:
                        intersecao = palavras_receita & palavras_pdf
                        if len(intersecao) >= max(2, min(len(palavras_receita), len(palavras_pdf)) * 0.5):
                            pdf_encontrado = pdf_path
                            associacoes_parciais += 1
                            break
        
        if pdf_encontrado:
            # Codificar PDF
            pdf_base64 = codificar_pdf_base64(pdf_encontrado)
            
            if pdf_base64:
                df.at[idx, 'pdf_url'] = url
                df.at[idx, 'pdf_base64'] = pdf_base64
                
                pdf_size_kb = len(pdf_base64) * 3 / 4 / 1024
                print(f"   ✓ [{idx+1}/{len(df)}] {titulo_receita[:40]}... ({pdf_size_kb:.1f} KB)")
                pdfs_codificados += 1
            else:
                pdfs_nao_encontrados += 1
        else:
            pdfs_nao_encontrados += 1
        
        # Mostrar progresso a cada 50 receitas
        if (idx + 1) % 50 == 0:
            print(f"   ... Processadas {idx+1}/{len(df)} receitas...")
    
    print(f"\n5. Salvando CSV atualizado...")
    
    # Salvar CSV atualizado
    df.to_csv(csv_path, index=False, sep=';', encoding='utf-8-sig')
    print(f"   ✓ CSV salvo: {csv_path}")
    
    # Estatísticas
    print(f"\n{'=' * 80}")
    print(f"  ESTATÍSTICAS FINAIS")
    print(f"{'=' * 80}")
    print(f"  Total de receitas: {len(df)}")
    print(f"  PDFs codificados: {pdfs_codificados} ({pdfs_codificados/len(df)*100:.1f}%)")
    print(f"  Associações exatas: {pdfs_codificados - associacoes_parciais}")
    print(f"  Associações parciais: {associacoes_parciais}")
    print(f"  Sem PDF: {pdfs_nao_encontrados} ({pdfs_nao_encontrados/len(df)*100:.1f}%)")
    print(f"  PDFs disponíveis: {len(pdf_files)}")
    print(f"  PDFs com títulos legíveis: {len(pdf_map)}")
    print(f"{'=' * 80}")
    
    print(f"\n✅ Processo concluído com sucesso!")

if __name__ == "__main__":
    main()
