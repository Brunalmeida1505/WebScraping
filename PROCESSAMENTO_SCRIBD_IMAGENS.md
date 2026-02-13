# 📖 Processamento de Imagens Scribd

## 🎯 Objetivo

Extrair imagens de alta qualidade dos PDFs baixados do Scribd usando PyMuPDF (fitz), aplicando filtros para garantir que apenas imagens de receitas válidas sejam salvas.

## ✅ Resultados Típicos

- **Taxa de sucesso:** ~96-97% dos PDFs contêm imagens extraíveis
- **Formatos:** JPEG (~95%), PNG (~5%)
- **Resolução média:** 600x800 pixels
- **Tamanho médio:** 240 KB por imagem

## 🔍 Filtros Aplicados

- **Tamanho mínimo:** 150x150 pixels (rejeita logos e ícones)
- **Aspect ratio:** < 3 (rejeita banners e headers)
- **Estratégia:** Primeira imagem válida de cada PDF (páginas 1-3)

## � Como Usar

### 1. Pré-requisitos

Instale as dependências necessárias:

```bash
pip install PyMuPDF Pillow
```

### 2. Executar Processamento de Imagens

```bash
python process_scribd_images.py
```

O script irá:
- ✅ Escanear o diretório `downloads/pdfs/scribd/`
- ✅ Processar cada PDF encontrado
- ✅ Extrair a primeira imagem válida (páginas 1-3)
- ✅ Salvar imagens em `downloads/images/scribd_images/`
- ✅ Atualizar `db/resultados/scribd_dados.csv` com caminhos das imagens
- ✅ Exibir progresso e estatísticas em tempo real

### 3. Saída Esperada

```
================================================================================
PROCESSAMENTO DE IMAGENS DE PDFs DO SCRIBD
================================================================================

📂 Carregando CSV: db/resultados/scribd_dados.csv
   ✓ 3013 registros carregados

📁 PDFs encontrados: 791
   Processando TODOS os 791 PDFs...

[1/791] 142197526-Kokeshi-Amigurumi.pdf                              ✓ (23.1 KB)
[2/791] 144927758-Amigurumi-Froggie.pdf                              ✓ (29.6 KB)
...

================================================================================
RESUMO
================================================================================
  Total processado: 791
  ✓ Com imagens: 765 (96.7%)
  ✗ Sem imagens: 26 (3.3%)

  Imagens salvas em: downloads/images/scribd_images/
  Total de imagens no diretório: 766
  Tamanho total: 180.89 MB
  Tamanho médio: 241.8 KB
```

## 🛠️ Tecnologia Utilizada

### PyMuPDF (fitz)

Biblioteca Python para manipulação de PDFs que permite extração nativa de imagens embutidas.

**Exemplo de código:**
```python
import fitz

pdf = fitz.open("pattern.pdf")
for page in pdf:
    for img in page.get_images():
        # Extrai imagem nativa (sem renderização)
        xref = img[0]
        base_image = pdf.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        
        # Salva imagem
        with open(f"output.{image_ext}", "wb") as f:
            f.write(image_bytes)
```

### Vantagens:
- ✅ **Imagens nativas:** Extrai diretamente do PDF sem perda de qualidade
- ✅ **Rápido:** < 1 segundo por PDF
- ✅ **Sem dependências externas:** Não precisa de Poppler ou outros binários
- ✅ **Múltiplos formatos:** JPEG, PNG, GIF, TIFF automaticamente
- ✅ **Metadados:** Acesso a dimensões, formato e tamanho original

### Filtros de Qualidade:
```python
from PIL import Image
import io

# Valida dimensões
img_obj = Image.open(io.BytesIO(image_bytes))
width, height = img_obj.size

# Rejeita imagens muito pequenas
if width < 150 or height < 150:
    continue

# Rejeita banners/headers (aspect ratio muito alto)
aspect_ratio = max(width, height) / min(width, height)
if aspect_ratio > 3:
    continue
```

## �️ Estrutura de Diretórios

```
Web Scraping/
├── downloads/
│   ├── pdfs/
│   │   └── scribd/              # PDFs baixados do Scribd
│   │       ├── 142197526-Kokeshi-Amigurumi.pdf
│   │       ├── 144927758-Amigurumi-Froggie.pdf
│   │       └── ...
│   │
│   └── images/
│       └── scribd_images/       # Imagens extraídas dos PDFs
│           ├── 142197526-Kokeshi-Amigurumi_page1_0.jpeg
│           ├── 144927758-Amigurumi-Froggie_page1_0.jpeg
│           └── ...
│
├── db/
│   └── resultados/
│       └── scribd_dados.csv     # Metadados + caminhos das imagens
│
└── process_scribd_images.py     # Script de processamento
```

### Nomenclatura dos Arquivos de Imagem:
```
{pdf_basename}_page{N}_{index}.{ext}
```

**Exemplos:**
- `142197526-Kokeshi-Amigurumi_page1_0.jpeg` — 1ª imagem da página 1
- `scribd_document_1769168282_page2_1.png` — 2ª imagem da página 2

## 📊 Campos Atualizados no CSV

Após o processamento, o CSV `scribd_dados.csv` contém:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `imagem_local` | Caminho local da imagem | `downloads/images/scribd_images/arquivo_page1_0.jpeg` |
| `imagem_url` | Indicador da origem | `PDF_PAGE_1`, `PDF_PAGE_2`, ou `N/A` |

**Status possíveis:**
- ✅ **Caminho válido** — Imagem extraída com sucesso
- ❌ **N/A** — Nenhuma imagem válida encontrada no PDF
- ❌ **ERROR** — Erro durante processamento

## 💡 Dicas de Uso

### Reprocessar PDFs Específicos
Edite o CSV e remova os valores de `imagem_local` para os PDFs que deseja reprocessar. O script detectará linhas sem imagem e tentará extrair novamente.

### Processar Apenas Novos PDFs
O script é idempotente: PDFs que já têm imagem no CSV não serão reprocessados, economizando tempo.

### Ajustar Filtros de Qualidade
Edite `process_scribd_images.py` e modifique as constantes:
```python
MIN_WIDTH = 150   # Largura mínima
MIN_HEIGHT = 150  # Altura mínima
MAX_ASPECT_RATIO = 3  # Rejeita banners
MAX_PAGES = 3     # Páginas a escanear
```
