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
import sys
from collections import Counter
from processar_scribd import processar_scribd

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

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
        # Prefer Parquet for Scribd: skip Scribd CSV if present
        if 'scribd' in nome.lower():
            print(f"  ⏭️ {nome:30} → CSV do Scribd será ignorado (usar Parquet)")
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
    
    # If this is the Scribd base64 parquet, load it and build compatible columns
    if 'scribd' in nome and 'base64' in nome:
        try:
            dfp = pd.read_parquet(f)
            # Normalize columns and keep relevant fields
            # Expected columns: url, title, pdf_path, base64_content (may vary)
            cols = set(dfp.columns)
            # prefer base64_content or base64
            if 'base64_content' in cols or 'base64' in cols:
                df_s = pd.DataFrame()
                df_s['url'] = dfp.get('url')
                df_s['title'] = dfp.get('title')
                df_s['pdf_path'] = dfp.get('pdf_path')
                # keep base64 if present
                if 'base64_content' in cols:
                    df_s['base64_content'] = dfp['base64_content']
                elif 'base64' in cols:
                    df_s['base64_content'] = dfp['base64']
                else:
                    df_s['base64_content'] = None

                # Mark origem and standardize title->titulo
                df_s['origem'] = 'Scribd'
                if 'title' in df_s.columns and 'titulo' not in df_s.columns:
                    df_s['titulo'] = df_s['title']

                # Try to populate imagem_local by scanning images folder
                imagens_dir = os.path.join('downloads', 'images', 'scribd_images')
                image_map = {}
                if os.path.exists(imagens_dir):
                    for img in os.listdir(imagens_dir):
                        key = os.path.splitext(img)[0]
                        image_map[key] = os.path.join(imagens_dir, img)

                def _find_image(row):
                    # candidates: pdf filename without ext, slug from url, title token
                    try:
                        pdf_path = row.get('pdf_path') or ''
                        pdf_fn = os.path.splitext(os.path.basename(pdf_path))[0]
                        if pdf_fn and pdf_fn in image_map:
                            return image_map[pdf_fn]

                        url = str(row.get('url') or '')
                        slug = url.rstrip('/').split('/')[-1]
                        if slug and slug in image_map:
                            return image_map[slug]

                        title = str(row.get('title') or '')
                        if title and title in image_map:
                            return image_map[title]

                        # fallback: try prefix match
                        for k, v in image_map.items():
                            if slug and k.startswith(slug):
                                return v
                            if pdf_fn and k.startswith(pdf_fn):
                                return v
                            if title and k.startswith(title):
                                return v
                    except:
                        return None
                    return None

                if image_map:
                    df_s['imagem_local'] = df_s.apply(_find_image, axis=1)
                else:
                    df_s['imagem_local'] = None

                # imagem_url mirror or N/A
                df_s['imagem_url'] = df_s['imagem_local'].apply(lambda x: x if pd.notna(x) and x else 'N/A')
                df_s['pdf_downloaded'] = df_s['pdf_path'].notna() & (df_s['pdf_path'] != 'N/A')

                print(f"  ✓ {os.path.basename(f):30} → {len(df_s):4} receitas (Scribd parquet)")
                dfs.append(df_s)
                continue
            else:
                print(f"  ⚠️ {os.path.basename(f):30} → Parquet não contém base64, carregando normalmente")
        except Exception as e:
            print(f"  ⚠️ Erro ao ler {nome}: {e}")
            continue
    
    try:
        df = pd.read_parquet(f)
        if 'pdf_base64' in df.columns:
            df = df.drop(columns=['pdf_base64'])
        print(f"  ✓ {os.path.basename(f):30} → {len(df):4} receitas")
        dfs.append(df)
    except Exception as e:
        print(f"  ⚠️ Erro ao ler {nome}: {e}")

# Concatenar todos os DataFrames
df = pd.concat(dfs, ignore_index=True)

# Padronizar nomes de colunas
if 'title' in df.columns and 'titulo' not in df.columns:
    df['titulo'] = df['title']

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
# 4. ANÁLISE DE IMAGENS COLETADAS
# ============================================================================
print("\n" + "=" * 80)
print("🖼️ 4. ANÁLISE DE IMAGENS COLETADAS")
print("=" * 80)

# Verificar quais scrapers têm coluna de imagem
tem_imagem = 'imagem_url' in df.columns or 'imagem_local' in df.columns

if tem_imagem:
    # Análise por scraper
    print("\n📊 ESTATÍSTICAS DE IMAGENS POR SCRAPER:\n")
    print(f"{'Scraper':20} {'Total':>10} {'Com Imagem':>12} {'Taxa':>10} {'Tamanho Médio':>15}")
    print("-" * 80)
    
    total_receitas = 0
    total_com_imagem = 0
    total_tamanho = 0
    
    for origem in df['origem'].dropna().unique():
        if not origem or str(origem).strip() == '' or pd.isna(origem):
            continue
            
        df_origem = df[df['origem'] == origem]
        qtd_total = len(df_origem)
        
        # Contar imagens válidas (não N/A e não ERROR)
        tamanhos = []  # Inicializar aqui
        if 'imagem_local' in df_origem.columns:
            imagens_validas = df_origem['imagem_local'].notna() & \
                             (df_origem['imagem_local'] != 'N/A') & \
                             (df_origem['imagem_local'] != 'ERROR') & \
                             (df_origem['imagem_local'] != '')
            qtd_com_imagem = imagens_validas.sum()
            
            # Calcular tamanho médio das imagens
            tamanho_medio = 0
            if qtd_com_imagem > 0:
                caminhos_validos = df_origem[imagens_validas]['imagem_local']
                for caminho in caminhos_validos:
                    try:
                        if os.path.exists(str(caminho)):
                            tamanhos.append(os.path.getsize(str(caminho)))
                    except:
                        pass
                if tamanhos:
                    tamanho_medio = sum(tamanhos) / len(tamanhos)
        else:
            qtd_com_imagem = 0
            tamanho_medio = 0
        
        taxa = (qtd_com_imagem / qtd_total * 100) if qtd_total > 0 else 0
        
        # Formatar tamanho
        if tamanho_medio > 1024 * 1024:
            tam_str = f"{tamanho_medio / (1024*1024):.1f} MB"
        elif tamanho_medio > 1024:
            tam_str = f"{tamanho_medio / 1024:.1f} KB"
        else:
            tam_str = f"{tamanho_medio:.0f} B" if tamanho_medio > 0 else "N/A"
        
        print(f"{origem:20} {qtd_total:>10} {qtd_com_imagem:>12} {taxa:>9.1f}% {tam_str:>15}")
        
        total_receitas += qtd_total
        total_com_imagem += qtd_com_imagem
        if tamanhos:
            total_tamanho += sum(tamanhos)
    
    print("-" * 80)
    taxa_geral = (total_com_imagem / total_receitas * 100) if total_receitas > 0 else 0
    tam_geral_str = f"{total_tamanho / (1024*1024):.1f} MB" if total_tamanho > 0 else "N/A"
    print(f"{'TOTAL':20} {total_receitas:>10} {total_com_imagem:>12} {taxa_geral:>9.1f}% {tam_geral_str:>15}")
    
    # Estatísticas detalhadas
    print("\n\n📈 ESTATÍSTICAS DETALHADAS DE IMAGENS:\n")
    
    if 'imagem_local' in df.columns:
        imagens_validas_df = df[df['imagem_local'].notna() & 
                                (df['imagem_local'] != 'N/A') & 
                                (df['imagem_local'] != 'ERROR') & 
                                (df['imagem_local'] != '')]
        
        if len(imagens_validas_df) > 0:
            # Coletar informações de todas as imagens
            tamanhos_imagens = []
            formatos = []
            
            for caminho in imagens_validas_df['imagem_local']:
                try:
                    caminho_str = str(caminho)
                    if os.path.exists(caminho_str):
                        tamanho = os.path.getsize(caminho_str)
                        tamanhos_imagens.append(tamanho)
                        
                        # Extrair formato
                        ext = os.path.splitext(caminho_str)[1].lower()
                        formatos.append(ext if ext else 'sem extensão')
                except:
                    pass
            
            if tamanhos_imagens:
                print(f"  • Total de imagens coletadas: {len(tamanhos_imagens)}")
                print(f"  • Tamanho total: {sum(tamanhos_imagens) / (1024*1024):.2f} MB")
                print(f"  • Tamanho médio: {sum(tamanhos_imagens) / len(tamanhos_imagens) / 1024:.1f} KB")
                print(f"  • Maior imagem: {max(tamanhos_imagens) / 1024:.1f} KB")
                print(f"  • Menor imagem: {min(tamanhos_imagens) / 1024:.1f} KB")
                
                # Distribuição de formatos
                print("\n  📁 FORMATOS DE IMAGEM:\n")
                formato_count = Counter(formatos)
                for formato, qtd in sorted(formato_count.items(), key=lambda x: x[1], reverse=True):
                    pct = (qtd / len(formatos)) * 100
                    barra = "█" * int(pct / 2)
                    print(f"    {formato:15} → {qtd:4} ({pct:5.1f}%) {barra}")
                
                # Distribuição de tamanhos
                print("\n  📊 DISTRIBUIÇÃO DE TAMANHO DAS IMAGENS:\n")
                bins_kb = [0, 10, 50, 100, 200, 500, float('inf')]
                labels_kb = ['Muito pequena (<10KB)', 'Pequena (10-50KB)', 'Média (50-100KB)', 
                            'Grande (100-200KB)', 'Muito grande (200-500KB)', 'Enorme (>500KB)']
                
                tamanhos_kb = [t / 1024 for t in tamanhos_imagens]
                for i in range(len(bins_kb)-1):
                    count = sum(1 for t in tamanhos_kb if bins_kb[i] <= t < bins_kb[i+1])
                    pct = (count / len(tamanhos_kb)) * 100
                    barra = "█" * int(pct / 2)
                    print(f"    {labels_kb[i]:30} → {count:4} ({pct:5.1f}%) {barra}")
            else:
                print("  ⚠️ Nenhuma imagem encontrada nos caminhos especificados")
        else:
            print("  ⚠️ Nenhuma receita com imagem válida encontrada")
    
    # Top scrapers com melhor taxa de imagens
    print("\n\n🏆 TOP SCRAPERS COM MELHOR TAXA DE IMAGENS:\n")
    
    taxas_scrapers = []
    for origem in df['origem'].dropna().unique():
        if not origem or str(origem).strip() == '' or pd.isna(origem):
            continue
            
        df_origem = df[df['origem'] == origem]
        qtd_total = len(df_origem)
        
        if 'imagem_local' in df_origem.columns and qtd_total >= 5:  # Apenas scrapers com pelo menos 5 receitas
            imagens_validas = df_origem['imagem_local'].notna() & \
                             (df_origem['imagem_local'] != 'N/A') & \
                             (df_origem['imagem_local'] != 'ERROR') & \
                             (df_origem['imagem_local'] != '')
            qtd_com_imagem = imagens_validas.sum()
            taxa = (qtd_com_imagem / qtd_total * 100) if qtd_total > 0 else 0
            
            taxas_scrapers.append({
                'origem': origem,
                'taxa': taxa,
                'com_imagem': qtd_com_imagem,
                'total': qtd_total
            })
    
    for i, item in enumerate(sorted(taxas_scrapers, key=lambda x: x['taxa'], reverse=True), 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"  {emoji} {i}º {item['origem']:20} → {item['taxa']:5.1f}% ({item['com_imagem']}/{item['total']})")
    
else:
    print("\n⚠️ Nenhuma coluna de imagem encontrada nos dados.")
    print("   Execute os scrapers com a funcionalidade de imagens implementada.")

# ============================================================================
# 5. COMPARAÇÃO DE COMPLEXIDADE ENTRE SCRAPERS
# ============================================================================
print("\n" + "=" * 80)
print("⚙️ 5. COMPARAÇÃO DE COMPLEXIDADE ENTRE SCRAPERS")
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
    
    # Scribd usa 'texto', outros scrapers usam 'receita'
    # Verificar qual coluna tem dados para esta origem específica
    tem_texto = 'texto' in df_origem.columns and df_origem['texto'].notna().any()
    tem_receita = 'receita' in df_origem.columns and df_origem['receita'].notna().any()
    
    if tem_texto:
        coluna_texto = 'texto'
    elif tem_receita:
        coluna_texto = 'receita'
    else:
        # Sem dados de texto para esta origem
        continue
    
    # Tamanho médio do texto/receita
    receitas_validas = df_origem[coluna_texto].dropna()
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
