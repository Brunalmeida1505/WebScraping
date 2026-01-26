"""
Análises Avançadas - Web Scraping Amigurumi
- Word Cloud dos títulos
- Clusterização por tipo de amigurumi
- Análise de materiais mais usados
- Comparação de complexidade entre scrapers
"""

import pandas as pd
import numpy as np
import glob
import os
import re
from collections import Counter
from processar_scribd import processar_scribd

print("=" * 80)
print(" " * 20 + "ANÁLISES AVANÇADAS - AMIGURUMI")
print("=" * 80)

# ============================================================================
# CARREGAMENTO DOS DADOS
# ============================================================================
print("\n📂 Carregando dados...")

pasta = 'db/resultados'
arquivos_csv = glob.glob(os.path.join(pasta, "*.csv"))
dfs = []

for f in arquivos_csv:
    try:
        nome = os.path.basename(f)
        
        # 🚫 SKIP SCRIBD CSVs - processaremos o Parquet com base64
        if 'scribd' in nome.lower():
            print(f"  ⏭️ {nome:30} → Será processado do Parquet")
            continue
        
        # Detectar separador automaticamente
        try:
            df_csv = pd.read_csv(f, sep=';', encoding='utf-8-sig', on_bad_lines='skip')
            if len(df_csv.columns) == 1:
                df_csv = pd.read_csv(f, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
        except:
            df_csv = pd.read_csv(f, sep=',', encoding='utf-8-sig', on_bad_lines='skip')
        
        print(f"  ✓ {nome:30} → {len(df_csv):4} receitas")
        dfs.append(df_csv)
        
    except Exception as e:
        print(f"  ⚠️ Erro ao ler {nome}: {e}")

# Carregar Parquets (exceto base64 puro)
arquivos_parquet = glob.glob(os.path.join(pasta, "*.parquet"))
for f in arquivos_parquet:
    nome = os.path.basename(f).lower()
    
    # 🚫 SKIP Scribd Parquet - será processado separadamente
    if 'scribd' in nome:
        print(f"  ⏭️ {os.path.basename(f):30} → Será processado do base64")
        continue
    
    try:
        df = pd.read_parquet(f)
        if 'pdf_base64' in df.columns:
            df = df.drop(columns=['pdf_base64'])
        print(f"  ✓ {os.path.basename(f):30} → {len(df):4} receitas")
        dfs.append(df)
    except Exception as e:
        print(f"  ⚠️ Erro ao ler {nome}: {e}")

# ============================================================================
# PROCESSAR SCRIBD (Base64 → Texto)
# ============================================================================
print("\n🔄 Processando dados do Scribd...")
try:
    df_scribd = processar_scribd()
    if not df_scribd.empty:
        com_texto = len(df_scribd[df_scribd['num_palavras'] > 50])
        total_palavras = df_scribd['num_palavras'].sum()
        
        print(f"  ✓ scribd_base64.parquet → {len(df_scribd):4} documentos processados")
        print(f"    • Com texto extraível: {com_texto}/{len(df_scribd)}")
        print(f"    • Total de palavras: {total_palavras:,}")
        
        dfs.append(df_scribd)
    else:
        print(f"  ⚠️  Nenhum dado Scribd encontrado")
except Exception as e:
    print(f"  ⚠️  Erro ao processar Scribd: {e}")

df = pd.concat(dfs, ignore_index=True)
print(f"✅ Total: {len(df)} receitas carregadas\n")

# ============================================================================
# 1. WORD CLOUD DOS TÍTULOS
# ============================================================================
print("=" * 80)
print("📝 1. WORD CLOUD DOS TÍTULOS")
print("=" * 80)

# Extrair todas as palavras dos títulos
palavras = []
for titulo in df['titulo'].dropna():
    # Remover caracteres especiais e números
    palavras_titulo = re.findall(r'\b[a-zA-Z]{3,}\b', titulo.lower())
    palavras.extend(palavras_titulo)

# Contar frequência
contador = Counter(palavras)

# Remover stopwords comuns
stopwords = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'are', 'was', 'were', 
             'been', 'have', 'has', 'had', 'will', 'can', 'you', 'your', 'not', 'but'}
palavras_filtradas = {palavra: freq for palavra, freq in contador.items() 
                      if palavra not in stopwords}

# Top 30 palavras
print("\n🏆 TOP 30 PALAVRAS MAIS FREQUENTES:\n")
for i, (palavra, freq) in enumerate(sorted(palavras_filtradas.items(), 
                                          key=lambda x: x[1], reverse=True)[:30], 1):
    barra = "█" * int(freq / 20)
    print(f"  {i:2}. {palavra:20} → {freq:4} vezes {barra}")

# Estatísticas
print(f"\n📊 ESTATÍSTICAS:")
print(f"  • Total de palavras únicas: {len(palavras_filtradas)}")
print(f"  • Total de palavras: {sum(palavras_filtradas.values())}")
print(f"  • Média por título: {sum(palavras_filtradas.values()) / len(df):.1f} palavras")

# ============================================================================
# 2. CLUSTERIZAÇÃO POR TIPO DE AMIGURUMI
# ============================================================================
print("\n" + "=" * 80)
print("🎯 2. CLUSTERIZAÇÃO POR TIPO DE AMIGURUMI")
print("=" * 80)

# Categorias de amigurumi
categorias = {
    '🐰 Animais': ['bunny', 'rabbit', 'bear', 'cat', 'dog', 'mouse', 'fox', 'lion', 
                   'elephant', 'giraffe', 'monkey', 'panda', 'tiger', 'wolf', 'deer',
                   'frog', 'turtle', 'penguin', 'owl', 'bird', 'duck', 'chicken',
                   'pig', 'cow', 'sheep', 'horse', 'unicorn', 'dragon'],
    
    '🦖 Dinossauros e Répteis': ['dinosaur', 'dino', 'dragon', 'lizard', 'snake', 
                                  'crocodile', 'alligator', 'trex', 'stegosaurus'],
    
    '🌊 Animais Aquáticos': ['fish', 'whale', 'dolphin', 'octopus', 'crab', 'starfish',
                             'seahorse', 'shark', 'jellyfish', 'turtle', 'seal'],
    
    '🦋 Insetos': ['bee', 'butterfly', 'ladybug', 'spider', 'snail', 'caterpillar',
                   'dragonfly', 'ant'],
    
    '👤 Personagens': ['doll', 'gnome', 'elf', 'fairy', 'witch', 'wizard', 'angel',
                       'mermaid', 'princess', 'prince', 'santa', 'snowman'],
    
    '🍓 Comida': ['food', 'fruit', 'vegetable', 'strawberry', 'apple', 'banana',
                  'carrot', 'mushroom', 'cupcake', 'cake', 'cookie'],
    
    '🌸 Plantas': ['flower', 'rose', 'cactus', 'plant', 'tree', 'leaf'],
    
    '🎃 Sazonal': ['christmas', 'halloween', 'easter', 'valentine', 'spring',
                   'winter', 'summer', 'autumn', 'pumpkin'],
    
    '🎮 Outros': ['toy', 'bag', 'keychain', 'bookmark', 'pillow', 'blanket']
}

# Classificar receitas
resultados = {cat: [] for cat in categorias.keys()}
nao_classificadas = []

for idx, row in df.iterrows():
    titulo = str(row['titulo']).lower()
    classificada = False
    
    for categoria, palavras_chave in categorias.items():
        if any(palavra in titulo for palavra in palavras_chave):
            resultados[categoria].append(titulo)
            classificada = True
            break
    
    if not classificada:
        nao_classificadas.append(titulo)

# Resultados
print("\n📊 DISTRIBUIÇÃO POR CATEGORIA:\n")
total_classificadas = 0
for categoria, receitas in sorted(resultados.items(), key=lambda x: len(x[1]), reverse=True):
    qtd = len(receitas)
    total_classificadas += qtd
    pct = (qtd / len(df)) * 100
    barra = "█" * int(pct / 2)
    print(f"  {categoria:30} → {qtd:4} receitas ({pct:5.1f}%) {barra}")

print(f"\n  {'⚪ Não Classificadas':30} → {len(nao_classificadas):4} receitas ({(len(nao_classificadas)/len(df)*100):5.1f}%)")
print(f"\n  {'TOTAL':30} → {len(df):4} receitas (100.0%)")

# Top 5 de cada categoria
print("\n\n🏆 TOP 3 RECEITAS POR CATEGORIA:\n")
for categoria, receitas in sorted(resultados.items(), key=lambda x: len(x[1]), reverse=True):
    if len(receitas) > 0:
        print(f"\n{categoria}:")
        for i, receita in enumerate(receitas[:3], 1):
            print(f"  {i}. {receita[:60]}...")

# ============================================================================
# 3. ANÁLISE DE MATERIAIS MAIS USADOS
# ============================================================================
print("\n" + "=" * 80)
print("🧶 3. ANÁLISE DE MATERIAIS MAIS USADOS")
print("=" * 80)

# Extrair materiais
todos_materiais = []
for materiais in df['materiais'].dropna():
    texto = str(materiais).lower()
    todos_materiais.append(texto)

texto_materiais = ' '.join(todos_materiais)

# Padrões de linha/fio
print("\n📏 TIPOS DE LINHA/FIO MAIS MENCIONADOS:\n")
tipos_linha = {
    'yarn': texto_materiais.count('yarn'),
    'cotton': texto_materiais.count('cotton'),
    'acrylic': texto_materiais.count('acrylic'),
    'wool': texto_materiais.count('wool'),
    'dk': texto_materiais.count(' dk '),
    'worsted': texto_materiais.count('worsted'),
    'sport': texto_materiais.count('sport'),
    'fingering': texto_materiais.count('fingering'),
    'bulky': texto_materiais.count('bulky')
}

for tipo, freq in sorted(tipos_linha.items(), key=lambda x: x[1], reverse=True):
    if freq > 0:
        barra = "█" * int(freq / 50)
        print(f"  {tipo:15} → {freq:4} vezes {barra}")

# Agulhas
print("\n🪡 TAMANHOS DE AGULHA MAIS USADOS:\n")
agulhas = {}
for match in re.finditer(r'(\d+\.?\d*)\s*mm', texto_materiais):
    tamanho = match.group(1)
    agulhas[tamanho] = agulhas.get(tamanho, 0) + 1

for tamanho, freq in sorted(agulhas.items(), key=lambda x: x[1], reverse=True)[:10]:
    barra = "█" * int(freq / 20)
    print(f"  {tamanho:5} mm → {freq:4} vezes {barra}")

# Cores
print("\n🎨 CORES MAIS MENCIONADAS:\n")
cores = {
    'white': texto_materiais.count('white'),
    'black': texto_materiais.count('black'),
    'brown': texto_materiais.count('brown'),
    'pink': texto_materiais.count('pink'),
    'blue': texto_materiais.count('blue'),
    'green': texto_materiais.count('green'),
    'yellow': texto_materiais.count('yellow'),
    'red': texto_materiais.count('red'),
    'gray': texto_materiais.count('gray') + texto_materiais.count('grey'),
    'beige': texto_materiais.count('beige')
}

for cor, freq in sorted(cores.items(), key=lambda x: x[1], reverse=True):
    if freq > 0:
        barra = "█" * int(freq / 50)
        print(f"  {cor:15} → {freq:4} vezes {barra}")

# Acessórios
print("\n✨ ACESSÓRIOS/MATERIAIS EXTRAS:\n")
acessorios = {
    'safety eyes': texto_materiais.count('safety eyes'),
    'stuffing': texto_materiais.count('stuffing') + texto_materiais.count('fiberfill'),
    'needle': texto_materiais.count('needle'),
    'scissors': texto_materiais.count('scissors'),
    'stitch marker': texto_materiais.count('stitch marker'),
    'button': texto_materiais.count('button')
}

for item, freq in sorted(acessorios.items(), key=lambda x: x[1], reverse=True):
    if freq > 0:
        barra = "█" * int(freq / 50)
        print(f"  {item:20} → {freq:4} vezes {barra}")

# ============================================================================
# 4. COMPARAÇÃO DE COMPLEXIDADE ENTRE SCRAPERS
# ============================================================================
print("\n" + "=" * 80)
print("⚙️ 4. COMPARAÇÃO DE COMPLEXIDADE ENTRE SCRAPERS")
print("=" * 80)

# Análise por origem
print("\n📊 ANÁLISE DE COMPLEXIDADE POR SCRAPER:\n")

complexidade = []

# Filtrar apenas origens válidas (não vazias e não NaN)
for origem in df['origem'].dropna().unique():
    if not origem or str(origem).strip() == '' or pd.isna(origem):
        continue
        
    df_origem = df[df['origem'] == origem]
    
    # Calcular métricas
    qtd = len(df_origem)
    
    # Verificar se tem coluna receita (Scribd não tem)
    if 'receita' not in df_origem.columns:
        continue
    
    # Tamanho médio da receita
    receitas_validas = df_origem['receita'].dropna()
    receitas_validas = receitas_validas[receitas_validas != '']
    if len(receitas_validas) == 0:
        continue  # Pular scrapers sem receitas válidas
    
    tam_medio = receitas_validas.str.len().mean()
    
    # Tamanho médio dos materiais
    materiais_validos = df_origem['materiais'].dropna() if 'materiais' in df_origem.columns else pd.Series([])
    materiais_validos = materiais_validos[materiais_validos != '']
    tam_materiais = materiais_validos.str.len().mean() if len(materiais_validos) > 0 else 0
    
    # Contagem de palavras de complexidade
    texto_completo = ' '.join(receitas_validas.astype(str).tolist()).lower()
    
    indicadores_complexidade = {
        'rounds': texto_completo.count('round'),
        'rows': texto_completo.count('row'),
        'stitch': texto_completo.count('stitch'),
        'increase': texto_completo.count('inc'),
        'decrease': texto_completo.count('dec'),
        'chain': texto_completo.count('ch')
    }
    
    score_complexidade = sum(indicadores_complexidade.values()) / max(len(receitas_validas), 1)
    
    complexidade.append({
        'origem': origem,
        'receitas': qtd,
        'tam_receita': tam_medio,
        'tam_materiais': tam_materiais,
        'score': score_complexidade
    })

# Ordenar por score de complexidade
complexidade = sorted(complexidade, key=lambda x: x['score'], reverse=True)

print(f"{'Scraper':20} {'Receitas':>10} {'Tam.Receita':>15} {'Tam.Materiais':>15} {'Score':>10}")
print("-" * 80)

for item in complexidade:
    print(f"{item['origem']:20} {item['receitas']:>10} "
          f"{item['tam_receita']:>12.0f} char {item['tam_materiais']:>12.0f} char "
          f"{item['score']:>10.1f}")

# Classificação de complexidade
print("\n\n🎖️ CLASSIFICAÇÃO POR COMPLEXIDADE:\n")
for i, item in enumerate(complexidade, 1):
    nivel = "🔴 Alta" if item['score'] > 30 else "🟡 Média" if item['score'] > 15 else "🟢 Baixa"
    print(f"  {i}º {item['origem']:20} → {nivel} (score: {item['score']:.1f})")

# Estatísticas gerais (apenas receitas válidas)
print("\n\n📈 ESTATÍSTICAS GERAIS DE COMPLEXIDADE:\n")
receitas_com_texto = df['receita'].dropna() if 'receita' in df.columns else pd.Series([])
receitas_com_texto = receitas_com_texto[receitas_com_texto != '']

if len(receitas_com_texto) > 0:
    print(f"  • Receita mais longa: {receitas_com_texto.str.len().max():.0f} caracteres")
    print(f"  • Receita mais curta: {receitas_com_texto.str.len().min():.0f} caracteres")
    print(f"  • Média geral: {receitas_com_texto.str.len().mean():.0f} caracteres")
    print(f"  • Mediana: {receitas_com_texto.str.len().median():.0f} caracteres")
    print(f"  • Total de receitas analisadas: {len(receitas_com_texto)}")
    
    # Distribuição de tamanho
    print("\n📊 DISTRIBUIÇÃO DE TAMANHO DAS RECEITAS:\n")
    tamanhos = receitas_com_texto.str.len()
    bins = [0, 500, 1000, 2000, 5000, 10000, float('inf')]
    labels = ['Muito curta (<500)', 'Curta (500-1K)', 'Média (1-2K)', 
              'Longa (2-5K)', 'Muito longa (5-10K)', 'Extremamente longa (>10K)']
    
    for i in range(len(bins)-1):
        count = ((tamanhos >= bins[i]) & (tamanhos < bins[i+1])).sum()
        pct = (count / len(tamanhos)) * 100
        barra = "█" * int(pct / 2)
        print(f"  {labels[i]:30} → {count:4} ({pct:5.1f}%) {barra}")
else:
    print("  ⚠️ Nenhuma receita com texto encontrada")

print("\n" + "=" * 80)
print("✅ ANÁLISE CONCLUÍDA!")
print("=" * 80)
