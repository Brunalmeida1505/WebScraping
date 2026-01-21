"""
Extrator de Texto dos PDFs do Scribd
Extrai texto dos PDFs salvos em base64 e adiciona colunas materiais/receita ao CSV
"""

import pandas as pd
import base64
import io
import re
from PyPDF2 import PdfReader

print("=" * 80)
print(" " * 15 + "EXTRATOR DE TEXTO - PDFs SCRIBD")
print("=" * 80)

# ============================================================================
# CARREGAR DADOS
# ============================================================================
print("\n📂 Carregando dados...")

# Carregar CSV com metadados
csv_path = 'db/resultados/scribd_dados.csv'
df_csv = pd.read_csv(csv_path)
print(f"✓ CSV carregado: {len(df_csv)} receitas")

# Carregar Parquet com PDFs base64
parquet_path = 'db/resultados/scribd_base64.parquet'
df_parquet = pd.read_parquet(parquet_path)
print(f"✓ Parquet carregado: {len(df_parquet)} PDFs")

# ============================================================================
# EXTRAIR TEXTO DOS PDFs
# ============================================================================
print("\n🔍 Extraindo texto dos PDFs...")
print("(Isso pode demorar alguns minutos...)\n")

resultados = []
erros = 0
sucesso = 0

for idx, row in df_parquet.iterrows():
    url = row['url']
    base64_content = row['base64_content']
    
    # Pular se não tem base64
    if pd.isna(base64_content) or base64_content == '':
        resultados.append({
            'url': url,
            'materiais': '',
            'receita': '',
            'sucesso': False
        })
        erros += 1
        continue
    
    try:
        # Decodificar base64 para bytes
        pdf_bytes = base64.b64decode(base64_content)
        
        # Criar objeto PDF em memória
        pdf_file = io.BytesIO(pdf_bytes)
        
        # Ler PDF
        pdf_reader = PdfReader(pdf_file)
        
        # Extrair texto de todas as páginas
        texto_completo = ""
        for page in pdf_reader.pages:
            texto_completo += page.extract_text() + "\n"
        
        # Tentar separar materiais e receita
        materiais = ""
        receita = texto_completo
        
        # Procurar seção de materiais
        patterns_materiais = [
            r'(?i)(materials?|supplies|you will need)(.*?)(?=pattern|instructions|abbreviations|\n\n)',
            r'(?i)(yarn|hook|needle|stuffing)(.*?)(?=pattern|instructions|\n\n)',
        ]
        
        for pattern in patterns_materiais:
            match = re.search(pattern, texto_completo, re.DOTALL)
            if match:
                materiais = match.group(0).strip()
                # Remover materiais da receita
                receita = texto_completo.replace(match.group(0), '').strip()
                break
        
        # Se não encontrou materiais, deixa tudo como receita
        if not materiais:
            materiais = ""
            receita = texto_completo
        
        resultados.append({
            'url': url,
            'materiais': materiais[:10000] if materiais else '',  # Limitar tamanho
            'receita': receita[:50000] if receita else '',  # Limitar tamanho
            'sucesso': True
        })
        sucesso += 1
        
        if (idx + 1) % 100 == 0:
            print(f"  Processados: {idx + 1}/{len(df_parquet)} ({(idx+1)/len(df_parquet)*100:.1f}%)")
        
    except Exception as e:
        resultados.append({
            'url': url,
            'materiais': '',
            'receita': '',
            'sucesso': False
        })
        erros += 1
        
        if idx < 5:  # Mostrar primeiros erros
            print(f"  ⚠️ Erro na URL {idx+1}: {str(e)[:100]}")

print(f"\n✓ Extração concluída!")
print(f"  • Sucesso: {sucesso} PDFs ({sucesso/len(df_parquet)*100:.1f}%)")
print(f"  • Erros: {erros} PDFs ({erros/len(df_parquet)*100:.1f}%)")

# ============================================================================
# MESCLAR DADOS
# ============================================================================
print("\n🔗 Mesclando dados...")

# Criar DataFrame com textos extraídos
df_textos = pd.DataFrame(resultados)

# Mesclar com CSV original
df_final = df_csv.merge(df_textos[['url', 'materiais', 'receita']], on='url', how='left')

# Adicionar coluna origem
df_final['origem'] = 'Scribd'

# Preencher vazios
df_final['materiais'] = df_final['materiais'].fillna('')
df_final['receita'] = df_final['receita'].fillna('')

print(f"✓ Dados mesclados: {len(df_final)} receitas")

# ============================================================================
# SALVAR RESULTADO
# ============================================================================
print("\n💾 Salvando resultados...")

# Salvar CSV atualizado
output_path = 'db/resultados/scribd_dados.csv'
df_final.to_csv(output_path, index=False, encoding='utf-8-sig')
print(f"✓ CSV atualizado: {output_path}")

# Estatísticas finais
print("\n" + "=" * 80)
print("📊 ESTATÍSTICAS FINAIS")
print("=" * 80)
print(f"\nTotal de receitas: {len(df_final)}")
print(f"Com materiais: {(df_final['materiais'] != '').sum()} ({(df_final['materiais'] != '').sum()/len(df_final)*100:.1f}%)")
print(f"Com receita: {(df_final['receita'] != '').sum()} ({(df_final['receita'] != '').sum()/len(df_final)*100:.1f}%)")
print(f"Completas (titulo+materiais+receita): {((df_final['title'] != '') & (df_final['materiais'] != '') & (df_final['receita'] != '')).sum()}")

print("\n✅ Extração concluída com sucesso!")
print("=" * 80)
