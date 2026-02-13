# Processamento de Imagens do Lovecrafts

## Objetivo
Extrair imagens dos PDFs de receitas do Lovecrafts e vinculá-las aos registros do CSV `lovecrafts_dados.csv`.

## Resultados
- **Total de PDFs processados**: 519
- **PDFs com imagens extraídas**: 514 (99.0%)
- **PDFs sem imagens**: 5 (1.0%)
- **Registros CSV vinculados**: 127 de 469 (27.1%)
- **Total de imagens únicas**: 492
- **Tamanho total**: 200.37 MB
- **Tamanho médio por imagem**: 417.0 KB
- **Diretório de imagens**: `downloads/images/lovecrafts_images/`

## Características Especiais

### Desafio: Nomes de Arquivo em Hash
Diferente dos scrapers Scribd e Ravelry, os PDFs do Lovecrafts são nomeados com **hashes criptográficos**:

```
0077464c537bf26d61bdb5edd7fa87b99626daa6.pdf
010f57a7ab60877789ceab96b739a155fe270f78.pdf
8c364ca1987c7539701ab26af5814cdc763ea96c.pdf
```

Isso impede a vinculação direta nome-do-arquivo → URL do CSV.

### Solução: Processamento em Duas Etapas

1. **Extração de todas as imagens**: Processa TODOS os 519 PDFs independentemente
2. **Vinculação via título/slug**: Tenta combinar URLs do CSV com PDFs usando:
   - Normalização de nomes de arquivo
   - Comparação com títulos da receita
   - Matching via slug da URL

## Método Técnico

### Biblioteca Utilizada
**PyMuPDF (fitz)** - Extração nativa de imagens de PDFs

```python
import fitz  # PyMuPDF
```

### Processo de Extração

1. **Leitura do PDF**:
   ```python
   doc = fitz.open(pdf_path)
   ```

2. **Extração das primeiras 3 páginas**:
   ```python
   for page_num in range(min(3, len(doc))):
       page = doc[page_num]
       images = page.get_images()
   ```

3. **Validação de dimensões**:
   - Mínimo: 150x150 pixels
   - Aspect ratio: < 3.0 (evitar banners longos)

4. **Conversão e salvamento**:
   ```python
   img = Image.frombytes("RGB", (width, height), pix.samples)
   img.save(output_path, "JPEG", quality=95)
   ```

### Vinculação PDF-CSV

```python
def find_pdf_for_url(url, title, pdf_dict):
    # 1. Tentar pelo slug da URL
    slug = url.split('/')[-1]
    
    # 2. Normalizar título
    normalized = normalize_filename(title)
    
    # 3. Buscar match no dicionário de PDFs
    for pdf_name in pdf_dict:
        if slug in pdf_name or normalized in pdf_name:
            return pdf_dict[pdf_name]
```

## Filtros Aplicados

### Tamanho Mínimo
- Largura: **150 pixels**
- Altura: **150 pixels**
- Rejeita miniaturas e ícones pequenos

### Aspect Ratio
- Máximo: **3.0** (3:1)
- Evita banners horizontais e elementos gráficos longos

### Formato de Saída
- **JPEG** (qualidade 95)
- Conversão automática de outros formatos

## Comparação com Outros Scrapers

| Aspecto | Lovecrafts | Scribd | Ravelry |
|---------|-----------|--------|---------|
| **Fonte** | PDFs | PDFs | API |
| **Método** | PyMuPDF | PyMuPDF | aiohttp |
| **Nomes de arquivo** | Hash criptográfico | Título legível | Pattern ID |
| **Taxa de sucesso** | 99.0% extração | 95.7% extração | 100% download |
| **Vinculação CSV** | 27.1% | 27.8% | 100% |
| **Tamanho médio** | 417.0 KB | 238.7 KB | 138.3 KB |
| **Desafio principal** | Matching hash→URL | ID numéricos | Rate limiting |

## Como Usar

### Execução Simples
```bash
python process_lovecrafts_images.py
```

### Pré-requisitos
```bash
pip install PyMuPDF Pillow pandas
```

### Estrutura de Diretórios
```
downloads/
  ├── pdfs/
  │   └── lovecrafts/          # 519 PDFs com nomes em hash
  └── images/
      └── lovecrafts_images/   # 492 imagens extraídas
```

## Fluxo de Execução

1. **Carrega CSV**: `db/resultados/lovecrafts_dados.csv` (469 registros)
2. **Lista PDFs**: `downloads/pdfs/lovecrafts/` (519 arquivos)
3. **Extrai imagens**: PyMuPDF em todas as páginas 1-3
4. **Cria mapeamento**: hash_filename → caminho_da_imagem
5. **Vincula ao CSV**: Tenta match via título/slug
6. **Atualiza CSV**: Adiciona colunas `imagem_local` e `imagem_url`

## Resultados por Tipo de Arquivo

### PDFs com Nome Legível
```
✓ 10103756_Birds-Nest-in-DMC-Downloadable-PDF_2.pdf
✓ 10130102_Bobby-the-Bee-Free-Amigurumi-Crochet-Toy-
✓ Alice+in+Wonderland.pdf
✓ Amigurumi+Bear+pattern.pdf
```
**Vantagem**: Matching mais fácil com URLs do CSV

### PDFs com Hash
```
✓ 0077464c537bf26d61bdb5edd7fa87b99626daa6.pdf
✓ 010f57a7ab60877789ceab96b739a155fe270f78.pdf
✓ 8c364ca1987c7539701ab26af5814cdc763ea96c.pdf
```
**Desafio**: Requer matching indireto via título ou slug

## Imagens Extraídas

### Estatísticas
- **99.0% de sucesso**: 514 de 519 PDFs geraram imagens
- **5 PDFs rejeitados**: Imagens muito pequenas ou sem imagens válidas
- **492 imagens únicas**: Alguns PDFs duplicados geraram mesma imagem

### Exemplos de Nomes
```
0077464c537bf26d61bdb5edd7fa87b99626daa6_page1_0.jpeg
Amigurumi+Bear+pattern_page1_0.jpeg
10130102_Bobby-the-Bee-Free-Amigurumi-Crochet-Toy-_page1_0.jpeg
```
**Formato**: `{nome_pdf}_page{N}_{índice}.jpeg`

## Vinculação ao CSV

### Taxa de Vinculação: 27.1%
De 469 registros no CSV:
- **127 vinculados** com sucesso (27.1%)
- **342 sem vinculação** (72.9%)

### Por que apenas 27.1%?
1. **Nomes em hash**: Dificulta matching com títulos
2. **Múltiplos PDFs duplicados**: Mesmo PDF com nomes diferentes
3. **Títulos diferentes**: Título no CSV ≠ nome do PDF
4. **Slugs modificados**: URLs com slugs diferentes do esperado

### Exemplo de Vinculação Bem-Sucedida
```
URL: https://www.lovecrafts.com/en-gb/.../bobby-the-bee
Título: "Bobby the Bee Free Amigurumi Crochet Toy"
PDF: 10130102_Bobby-the-Bee-Free-Amigurumi-Crochet-Toy-...pdf
Imagem: 10130102_Bobby-the-Bee-Free-Amigurumi-Crochet-Toy-_page1_0.jpeg
✓ Match via título normalizado
```

## Melhorias Futuras

### Para Aumentar Taxa de Vinculação
1. **OCR nos PDFs**: Extrair título real do PDF via OCR
2. **Fuzzy matching**: Usar bibliotecas como `fuzzywuzzy` para matching aproximado
3. **Metadata dos PDFs**: Ler propriedades do PDF (autor, título)
4. **Histórico de download**: Salvar URL original ao baixar PDF

### Otimizações de Performance
1. **Processamento paralelo**: Usar `multiprocessing` para PDFs
2. **Cache de imagens**: Não reprocessar PDFs já extraídos
3. **Extração apenas página 1**: Reduzir para 1 página se necessário

## Vantagens do Método Atual

### ✅ Extração Completa
- Processa **todos** os PDFs disponíveis
- Não depende de matching com CSV
- Garante que todas as imagens possíveis sejam extraídas

### ✅ Alta Taxa de Sucesso
- 99.0% dos PDFs geram imagens válidas
- Apenas 5 PDFs rejeitados (sem imagens ou muito pequenas)

### ✅ Qualidade Garantida
- Filtros de tamanho mínimo (150x150)
- Filtro de aspect ratio (< 3.0)
- JPEG com qualidade 95

### ✅ Robustez
- Não falha se vinculação CSV falhar
- Cria todas as imagens independentemente
- Pode ser re-executado para tentar melhor vinculação

## Script Completo

### Arquivo: `process_lovecrafts_images.py`

**Principais Funções**:
- `extract_image_from_pdf()`: Extração via PyMuPDF
- `normalize_filename()`: Normalização para matching
- `find_pdf_for_url()`: Vinculação PDF→CSV
- `main()`: Orquestração completa

### Execução
```bash
# Ativar ambiente virtual
.venv\Scripts\Activate.ps1

# Executar processamento
python process_lovecrafts_images.py
```

### Saída
```
✓ PyMuPDF disponível!

================================================================================
PROCESSAMENTO DE IMAGENS DE PDFs DO LOVECRAFTS
================================================================================

📂 Carregando CSV: db/resultados/lovecrafts_dados.csv
   ✓ 469 registros carregados

📁 PDFs encontrados: 519
   Processando TODOS os 519 PDFs...

🔄 Iniciando processamento...
   Filtros: min 150x150px, aspect ratio < 3.0

[1/519] 0077464c537bf26d61bdb5edd7fa87b99626daa6.pdf       ✓ (40.4 KB)
[2/519] 010f57a7ab60877789ceab96b739a155fe270f78.pdf       ✓ (68.5 KB)
...
[519/519] トマト+Tomato+Amigurumi.pdf                        ✓ (17.2 KB)

   Processados: 519, Sucesso: 514, Pulados: 0

🔗 Vinculando imagens ao CSV...
   ✓ 127 registros vinculados

💾 Salvando CSV atualizado...
   ✓ CSV salvo: db/resultados/lovecrafts_dados.csv

================================================================================
RESUMO
================================================================================
  Total processado: 519
  ✓ Com imagens: 514 (99.0%)
  ✗ Sem imagens: 5 (1.0%)

  Imagens salvas em: downloads\images\lovecrafts_images
  Total de imagens no diretório: 492
  Tamanho total: 200.37 MB
  Tamanho médio: 417.0 KB

  Registros no CSV com imagens: 127 (27.1%)
================================================================================
```

## Conclusão

O processamento de imagens do Lovecrafts apresenta um **desafio único** devido aos nomes de arquivo em hash, mas a **abordagem em duas etapas** (extração completa + vinculação posterior) garante:

1. ✅ **99.0% de sucesso** na extração de imagens
2. ✅ **492 imagens** salvas e disponíveis
3. ✅ **27.1% dos registros CSV** vinculados
4. ✅ **Robustez**: Todas as imagens extraídas, independente de vinculação

A taxa de vinculação pode ser melhorada no futuro com OCR ou fuzzy matching, mas o importante é que **todas as imagens possíveis já foram extraídas e estão disponíveis**.
