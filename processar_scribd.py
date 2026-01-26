"""
Processador de dados Scribd - Converte base64 em dados estruturados
"""

import pandas as pd
import base64
from PyPDF2 import PdfReader
from io import BytesIO
import re

def processar_scribd():
    """
    Processa dados do Scribd (base64 → texto) e retorna DataFrame estruturado
    
    Returns:
        DataFrame: Dados do Scribd prontos para análise
    """
    try:
        # Carregar base64
        df_base64 = pd.read_parquet('db/resultados/scribd_base64.parquet')
        
        resultados = []
        
        for idx, row in df_base64.iterrows():
            try:
                # Decodificar base64
                pdf_bytes = base64.b64decode(row['base64_content'])
                
                # Criar objeto PDF em memória
                pdf_file = BytesIO(pdf_bytes)
                pdf = PdfReader(pdf_file)
                
                # Extrair texto de todas as páginas
                texto_completo = ""
                for page in pdf.pages:
                    texto_completo += page.extract_text() + "\n"
                
                palavras = len(texto_completo.split())
                
                # Detectar idioma
                texto_lower = texto_completo.lower()
                if any(word in texto_lower for word in ['amigurumi', 'punto', 'vuelta', 'hilo', 'patron']):
                    idioma = "Espanhol"
                elif any(word in texto_lower for word in ['row', 'stitch', 'yarn', 'pattern', 'round']):
                    idioma = "Inglês"
                elif any(word in texto_lower for word in ['ponto', 'volta', 'fio', 'carreira', 'receita']):
                    idioma = "Português"
                else:
                    idioma = "Desconhecido"
                
                # Extrair título
                titulo = row.get('title', '')
                if not titulo or titulo == 'N/A':
                    # Tentar extrair do texto
                    first_lines = texto_completo[:200].strip()
                    if first_lines:
                        titulo = first_lines.split('\n')[0][:100]
                    else:
                        titulo = f"Documento {idx+1}"
                
                # Criar registro estruturado
                resultado = {
                    'titulo': titulo,
                    'url': row['url'],
                    'texto': texto_completo if palavras > 50 else '',  # Ignora PDFs sem texto
                    'idioma': idioma if palavras > 50 else 'PDF com imagens',
                    'tamanho_pdf_mb': len(pdf_bytes) / (1024 * 1024),
                    'num_paginas': len(pdf.pages),
                    'num_palavras': palavras,
                    'origem': 'Scribd'
                }
                
                resultados.append(resultado)
                
            except Exception as e:
                # Em caso de erro, adiciona registro vazio
                resultado = {
                    'titulo': row.get('title', f'Documento {idx+1}'),
                    'url': row['url'],
                    'texto': '',
                    'idioma': 'ERRO',
                    'tamanho_pdf_mb': 0,
                    'num_paginas': 0,
                    'num_palavras': 0,
                    'origem': 'Scribd'
                }
                resultados.append(resultado)
        
        df_processado = pd.DataFrame(resultados)
        
        return df_processado
        
    except FileNotFoundError:
        print("  ⚠️  Dados do Scribd não encontrados (executar scraper primeiro)")
        return pd.DataFrame()
    except Exception as e:
        print(f"  ⚠️  Erro ao processar Scribd: {str(e)}")
        return pd.DataFrame()

if __name__ == "__main__":
    print("Testando processador Scribd...")
    df = processar_scribd()
    print(f"\n✓ Processados {len(df)} documentos")
    print(f"  Com texto: {len(df[df['num_palavras'] > 50])}")
    print(f"  Total palavras: {df['num_palavras'].sum():,}")
    print("\nPrimeiros registros:")
    print(df[['titulo', 'num_paginas', 'num_palavras', 'idioma']].head())
