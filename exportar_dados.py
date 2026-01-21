"""
Exportador de Dados - Web Scraping Amigurumi
Exporta dataset consolidado em CSV
"""

import pandas as pd
import glob
import os

print("=" * 80)
print(" " * 20 + "EXPORTADOR DE DADOS - AMIGURUMI")
print("=" * 80)

# ============================================================================
# CARREGAR TODOS OS DADOS
# ============================================================================
print("\n📂 Carregando dados...")

pasta = 'db/resultados'
arquivos_csv = glob.glob(os.path.join(pasta, "*.csv"))
dfs = []

for f in arquivos_csv:
    try:
        nome = os.path.basename(f)
        
        # Detectar separador automaticamente
        try:
            df_csv = pd.read_csv(f, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
            if len(df_csv.columns) == 1:
                df_csv = pd.read_csv(f, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
        except:
            df_csv = pd.read_csv(f, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
        
        # Adicionar coluna origem se não existir
        if 'origem' not in df_csv.columns:
            # Extrair origem do nome do arquivo
            origem = nome.replace('_dados.csv', '').replace('_data.csv', '').replace('.csv', '')
            origem = origem.replace('_', ' ').title()
            df_csv['origem'] = origem
        
        print(f"  ✓ {nome:30} → {len(df_csv):4} receitas")
        dfs.append(df_csv)
        
    except Exception as e:
        print(f"  ⚠️ Erro ao ler {nome}: {e}")

# Carregar Parquets (exceto base64 puro)
arquivos_parquet = glob.glob(os.path.join(pasta, "*.parquet"))
for f in arquivos_parquet:
    nome = os.path.basename(f).lower()
    if 'base64' in nome and 'scribd' in nome:
        print(f"  ⊘ {os.path.basename(f):30} → ignorado (base64 puro)")
        continue
    
    try:
        df = pd.read_parquet(f)
        if 'pdf_base64' in df.columns:
            df = df.drop(columns=['pdf_base64'])
        print(f"  ✓ {os.path.basename(f):30} → {len(df):4} receitas")
        dfs.append(df)
    except Exception as e:
        print(f"  ⚠️ Erro ao ler {nome}: {e}")

df_completo = pd.concat(dfs, ignore_index=True)
print(f"✅ Total: {len(df_completo)} receitas carregadas\n")

# ============================================================================
# CRIAR DIRETÓRIO DE EXPORTAÇÃO
# ============================================================================
export_dir = 'db/exports'
os.makedirs(export_dir, exist_ok=True)

# ============================================================================
# 1. DATASET COMPLETO
# ============================================================================
print("=" * 80)
print("📦 EXPORTANDO DATASETS")
print("=" * 80)

# Tratar valores vazios
df_export = df_completo.copy()
df_export = df_export.fillna('')

# 1.1 CSV Completo
caminho_csv = os.path.join(export_dir, 'amigurumi_completo.csv')
df_export.to_csv(caminho_csv, index=False, encoding='utf-8-sig')
print(f"\n✅ 1. Dataset Completo: {caminho_csv}")
print(f"   • {len(df_export)} receitas")
print(f"   • {len(df_export.columns)} colunas")
print(f"   • Tamanho: {os.path.getsize(caminho_csv) / 1024 / 1024:.2f} MB")

# ============================================================================
# 2. RECEITAS COMPLETAS (todos os campos preenchidos)
# ============================================================================
df_completas = df_completo[
    (df_completo['titulo'].notna()) & 
    (df_completo['titulo'] != '') &
    (df_completo['materiais'].notna()) & 
    (df_completo['materiais'] != '') &
    (df_completo['receita'].notna()) & 
    (df_completo['receita'] != '')
].copy()

df_completas = df_completas.fillna('')

caminho_completas = os.path.join(export_dir, 'amigurumi_receitas_completas.csv')
df_completas.to_csv(caminho_completas, index=False, encoding='utf-8-sig')
print(f"\n✅ 2. Receitas Completas: {caminho_completas}")
print(f"   • {len(df_completas)} receitas ({len(df_completas)/len(df_completo)*100:.1f}%)")
print(f"   • Apenas receitas com título + materiais + receita")
print(f"   • Tamanho: {os.path.getsize(caminho_completas) / 1024 / 1024:.2f} MB")

# ============================================================================
# 3. METADADOS - RESUMO ESTATÍSTICO
# ============================================================================
metadados = {
    'total_receitas': len(df_completo),
    'receitas_completas': len(df_completas),
    'taxa_completude': f"{len(df_completas)/len(df_completo)*100:.1f}%",
    'scrapers': df_completo['origem'].nunique(),
    'urls_unicas': df_completo['url'].nunique(),
    'duplicatas': len(df_completo) - df_completo['url'].nunique(),
    'com_pdf': df_completo['pdf_url'].notna().sum() if 'pdf_url' in df_completo.columns else 0,
}

# Distribuição por scraper
distribuicao = df_completo['origem'].value_counts().to_dict()

# Salvar metadados
caminho_meta = os.path.join(export_dir, 'metadados.txt')
with open(caminho_meta, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write(" " * 20 + "METADADOS - WEB SCRAPING AMIGURUMI\n")
    f.write("=" * 80 + "\n\n")
    
    f.write("📊 ESTATÍSTICAS GERAIS:\n")
    f.write(f"  • Total de receitas: {metadados['total_receitas']}\n")
    f.write(f"  • Receitas completas: {metadados['receitas_completas']} ({metadados['taxa_completude']})\n")
    f.write(f"  • Número de scrapers: {metadados['scrapers']}\n")
    f.write(f"  • URLs únicas: {metadados['urls_unicas']}\n")
    f.write(f"  • Duplicatas: {metadados['duplicatas']}\n")
    f.write(f"  • Com PDF: {metadados['com_pdf']}\n\n")
    
    f.write("📈 DISTRIBUIÇÃO POR SCRAPER:\n")
    for origem, qtd in sorted(distribuicao.items(), key=lambda x: x[1], reverse=True):
        pct = (qtd / len(df_completo)) * 100
        f.write(f"  • {origem:25} → {qtd:4} receitas ({pct:5.1f}%)\n")
    
    f.write("\n" + "=" * 80 + "\n")
    f.write("Data da exportação: 2026-01-21\n")
    f.write("=" * 80 + "\n")

print(f"\n✅ 3. Metadados: {caminho_meta}")

# ============================================================================
# RESUMO FINAL
# ============================================================================
print("\n" + "=" * 80)
print("✅ EXPORTAÇÃO CONCLUÍDA!")
print("=" * 80)
print(f"\n📁 Arquivos salvos em: {export_dir}")
print("\n📋 Arquivos exportados:")
print("  1. amigurumi_completo.csv - Dataset completo")
print("  2. amigurumi_receitas_completas.csv - Apenas receitas completas")
print("  3. metadados.txt - Estatísticas do dataset")

print("\n💡 Como usar:")
print("  • Abra os CSVs no Excel, Google Sheets ou Pandas")
print("  • Use 'receitas_completas' para análises de qualidade")
print("  • Use 'amigurumi_completo' para análises gerais")

print("\n" + "=" * 80)
