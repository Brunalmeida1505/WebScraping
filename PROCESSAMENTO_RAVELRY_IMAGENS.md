# 📖 Processamento de Imagens Ravelry

## 🎯 Objetivo

Baixar imagens dos padrões do Ravelry diretamente da API, aplicando filtros para garantir qualidade e atualizar o CSV com os caminhos das imagens locais.

## ✅ Resultados Típicos

- **Taxa de sucesso:** ~100% dos padrões têm imagens disponíveis via API
- **Formato:** JPEG (imagens otimizadas do Ravelry)
- **Resolução média:** Variável (medium quality da API)
- **Tamanho médio:** 140 KB por imagem

## 🔍 Filtros Aplicados

- **Tamanho mínimo:** 150x150 pixels (rejeita thumbnails muito pequenos)
- **Aspect ratio:** < 3 (rejeita banners e headers)
- **Qualidade:** Preferência por `medium_url` da API (balanço entre qualidade e tamanho)

## 🛠️ Como Usar

### 1. Pré-requisitos

Certifique-se de que as credenciais do Ravelry estão configuradas no `.env`:

```bash
RAVELRY_USERNAME=seu_username
RAVELRY_APIKEY=sua_api_key
# ou
RAVELRY_PASSWORD=sua_senha
```

Instale as dependências necessárias:

```bash
pip install Pillow aiohttp python-dotenv
```

### 2. Executar Processamento de Imagens

```bash
python process_ravelry_images.py
```

O script irá:
- ✅ Carregar `db/resultados/ravelry_dados.csv`
- ✅ Para cada padrão sem imagem, buscar na API do Ravelry
- ✅ Baixar a melhor imagem disponível (`medium_url` > `small_url` > `thumbnail_url`)
- ✅ Aplicar filtros de qualidade (tamanho e aspect ratio)
- ✅ Salvar imagens em `downloads/images/ravelry_images/`
- ✅ Atualizar CSV com `imagem_local` e `imagem_url`

### 3. Saída Esperada

```
================================================================================
PROCESSAMENTO DE IMAGENS DO RAVELRY
================================================================================

📂 Carregando CSV: db/resultados/ravelry_dados.csv
   ✓ 94 registros carregados

📊 Registros a processar: 94

🔄 Processando registros...
   Filtros: min 150x150px, aspect ratio < 3.0

[10/94] kitty-bee-amigurumi.jpeg                           ✓ (351.1 KB)
[20/94] amigurumi-spider-13.jpeg                           ✓ (142.0 KB)
...

================================================================================
RESUMO
================================================================================
  Total processado: 94
  ✓ Com imagens: 94 (100.0%)
  ✗ Sem imagens: 0 (0.0%)
  
  Imagens salvas em: downloads/images/ravelry_images
  Total de imagens no diretório: 94
  Tamanho total: 12.70 MB
  Tamanho médio: 138.3 KB
```

## 🔗 Tecnologia Utilizada

### API do Ravelry

O Ravelry fornece uma API REST robusta que inclui URLs de imagens em múltiplas resoluções:

**Exemplo de resposta da API:**
```json
{
  "pattern": {
    "id": 12345,
    "name": "Kitty Bee",
    "photos": [
      {
        "medium_url": "https://images4-b.ravelrycache.com/uploads/photo_medium.jpg",
        "small_url": "https://images4-b.ravelrycache.com/uploads/photo_small.jpg",
        "thumbnail_url": "https://images4-b.ravelrycache.com/uploads/photo_thumb.jpg"
      }
    ]
  }
}
```

### Código de exemplo:

```python
async def get_pattern_images_from_api(pattern_slug: str):
    async with aiohttp.ClientSession(auth=BasicAuth(username, api_key)) as session:
        async with session.get(f'https://api.ravelry.com/patterns/{pattern_slug}.json') as resp:
            data = await resp.json()
            photos = data['pattern']['photos']
            # Preferir medium_url para melhor qualidade
            return [photo['medium_url'] for photo in photos]
```

### Vantagens:
- ✅ **API oficial:** Acesso direto às imagens hospedadas pelo Ravelry
- ✅ **Múltiplas resoluções:** Escolha entre thumbnail, small, medium
- ✅ **Rápido:** Download direto de CDN (~1s por imagem)
- ✅ **Confiável:** 100% dos padrões têm imagens

## 📁 Estrutura de Diretórios

```
Web Scraping/
├── downloads/
│   └── images/
│       └── ravelry_images/         # Imagens baixadas
│           ├── kitty-bee-amigurumi.jpeg
│           ├── amigurumi-spider-13.jpeg
│           └── ...
├── db/
│   └── resultados/
│       └── ravelry_dados.csv       # CSV atualizado com caminhos
└── process_ravelry_images.py       # Script de processamento
```

## 📊 Campos do CSV

O script atualiza/adiciona as seguintes colunas no CSV:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `imagem_local` | Caminho local da imagem | `downloads/images/ravelry_images/kitty-bee-amigurumi.jpeg` |
| `imagem_url` | URL original da API | `https://images4-b.ravelrycache.com/.../photo_medium.jpg` |

## 💡 Dicas de Uso

### Reprocessar Imagens

Para reprocessar imagens (por exemplo, com filtros diferentes):

1. Delete as imagens antigas: `Remove-Item downloads/images/ravelry_images/* -Force`
2. Limpe as colunas no CSV ou delete o CSV
3. Execute novamente: `python process_ravelry_images.py`

### Ajustar Filtros

Edite `process_ravelry_images.py` e modifique as constantes:

```python
MIN_WIDTH = 150        # Largura mínima em pixels
MIN_HEIGHT = 150       # Altura mínima em pixels
MAX_ASPECT_RATIO = 3.0 # Aspect ratio máximo
```

### Processar Novos Padrões

O script processa automaticamente apenas registros sem imagem (`imagem_local` vazio ou `N/A`). Basta executar novamente após adicionar novos padrões ao CSV.

## 🔄 Diferenças vs Scribd

| Aspecto | Scribd | Ravelry |
|---------|--------|---------|
| **Fonte** | Extrai de PDFs locais | Baixa da API REST |
| **Método** | PyMuPDF (extração nativa) | aiohttp (HTTP requests) |
| **Taxa de sucesso** | ~97% (PDFs sem imagens) | ~100% (API sempre fornece) |
| **Velocidade** | < 1s por PDF | < 1s por padrão |
| **Autenticação** | Não necessária | API Key necessária |

## ⚠️ Observações

- **Rate Limiting:** O script respeita rate limits com `asyncio.sleep(1.0)` entre batches
- **Credenciais:** Certifique-se de ter acesso "Read Only" na API (suficiente para buscar imagens)
- **Armazenamento:** Imagens são JPEG otimizadas (~140 KB média vs ~240 KB do Scribd)

---

**Status:** ✅ Implementado e testado com 100% de sucesso em 94 padrões
