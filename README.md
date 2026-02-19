# Web Scraping - Recipe Scrapers

Este projeto contém scrapers para coletar receitas de amigurumis de diversos sites de crochê e tricô.

## Instalação

1. Clone o repositório
2. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Configuração do Lovecrafts Scraper

O scraper do Lovecrafts requer login. Para evitar digitar as credenciais toda vez:

1. Copie o arquivo `.env.example` para `.env`:
   ```bash
   copy .env.example .env
   ```

2. Edite o arquivo `.env` e adicione suas credenciais:
   ```
   LOVECRAFTS_EMAIL=seu_email@lovecrafts.com
   LOVECRAFTS_PASSWORD=sua_senha
   ```

3. O arquivo `.env` está no `.gitignore` e não será commitado

## Uso

### Scrapers Disponíveis

- `circulo` - Scraper para circulo.com.br
- `mariskavos` - Scraper para mariskavos.nl
- `alwaysfreeamigurumi` - Scraper para alwaysfreeamigurumi.com
- `lovecrafts` - Scraper para lovecrafts.com (requer login)
- `amigurum` - Scraper para amigurum.com
- `ravelry` - Scraper para Ravelry.com via API REST (requer credenciais de API)
- `scribd` - Scraper para Scribd.com (requer conta paga e faz download de PDFs)
- `aifanshub` - Scraper para AIFansHub.com com **scroll dinâmico** (Selenium + extração integrada de imagens)

### Comandos

```bash
# Executar um scraper
python main.py <nome_do_scraper>

# Forçar scraping completo (ignora cache)
python main.py <nome_do_scraper> --force

# Apenas atualizar a lista de URLs
python main.py <nome_do_scraper> --update-urls-only

# Mostrar o navegador (útil para debug)
python main.py <nome_do_scraper> --no-headless

# Limitar número de páginas (apenas mariskavos, alwaysfreeamigurumi, amigurum e aifanshub)
python main.py mariskavos --max-pages 10

# Limitar número de scrolls no Amigurum
python main.py amigurum --max-pages 30

# AIFansHub com scroll dinâmico (padrão: 100 scrolls)
python main.py aifanshub

# AIFansHub com scrolls customizados
python main.py aifanshub --max-pages 50

# Scraper do Ravelry (via API - muito rápido!)
python main.py ravelry --max-pages 10
```

### Exemplos

```bash
# Scraper do Circulo
python main.py circulo

# Scraper do Lovecrafts (com credenciais do .env)
python main.py lovecrafts

# Scraper do Scribd (com credenciais do .env)
python main.py scribd

# Scraper do Scribd limitado a 5 documentos
python main.py scribd --limit 5

# Scraper do Mariskavos com 20 páginas
python main.py mariskavos --max-pages 20

# Scraper do Amigurum com 30 scrolls
python main.py amigurum --max-pages 30

# Scraper do AIFansHub - teste rápido (5 scrolls = ~60-65 posts)
python main.py aifanshub --max-pages 5 --limit 10

# Scraper do AIFansHub - coleta média (20 scrolls = ~245 posts)
python main.py aifanshub --max-pages 20

# Scraper do AIFansHub - coleta completa (100 scrolls = ~1200+ posts)
python main.py aifanshub --max-pages 100

# Forçar re-download de todas as receitas do Lovecrafts
python main.py lovecrafts --force
```

## Estrutura de Dados

Os dados são salvos em:
- **URLs**: `db/<scraper>_urls.txt`
- **Dados**: `db/resultados/<scraper>_dados.csv`
- **PDFs Scribd**: `db/resultados/scribd_base64.parquet` (PDFs em base64)
- **Exports**: `db/exports/` (dados consolidados e análises)

### Formato CSV

Todos os scrapers salvam dados no formato:
- `titulo` - Título da receita
- `url` - URL da receita
- `materiais` - Materiais necessários / Abreviações
- `receita` - Instruções da receita
- `origem` - Nome do site de origem

### Scribd - Processamento Automático de PDFs

⚠️ **Nota**: O Scribd armazena receitas em PDFs que são automaticamente processados pelos scripts `exportar_dados.py` e `analises_avancadas.py`.

O módulo `processar_scribd.py`:
- ✅ Lê PDFs do arquivo `scribd_base64.parquet`
- ✅ Extrai texto usando PyPDF2 (~0.2s por PDF)
- ✅ Detecta idioma automaticamente (Espanhol/Inglês/Português)
- ✅ Filtra PDFs sem texto extraível (imagens)
- ✅ Integração automática nas análises

**Resultado**: Scribd totalmente integrado nos exports e análises!

## Otimizações do Lovecrafts Scraper

O scraper foi otimizado para reduzir o tempo de processamento:
- Timeouts reduzidos para 30 segundos no download
- Verificações mais frequentes (0.3s vs 1s)
- Tempos de espera reduzidos entre ações
- Tempo estimado: ~10-15 segundos por receita

## Características Especiais do Amigurum Scraper

O scraper do Amigurum possui **condições de parada inteligentes** para evitar loops infinitos:

### Condições de Parada Automáticas

1. **3 páginas consecutivas sem receitas novas**
   - Para automaticamente quando encontra apenas receitas duplicadas
   - Evita continuar navegando em conteúdo repetido
   - Mensagem: `⚠ No new recipes found for 3 consecutive pages`

2. **2 páginas consecutivas totalmente vazias**
   - Para quando não há mais conteúdo no site
   - Útil para detectar o fim da paginação

3. **Redirect para homepage**
   - Detecta quando uma página inexistente redireciona para a página inicial
   - Para imediatamente ao detectar o redirect

### Como Funciona

O scraper navega pelas páginas numeradas (`/page/2/`, `/page/3/`, etc.) e:
- ✅ Remove URLs duplicadas automaticamente
- ✅ Remove âncoras de comentários (`#comment-xxx`)
- ✅ Mostra progresso detalhado (receitas novas vs total)
- ✅ Para automaticamente quando não há mais receitas novas

**Resultado:** Coleta eficiente de todas as receitas sem loop infinito ou desperdício de recursos!

## Estrutura do Projeto

```
├── scrapers/
│   ├── base_scraper.py           # Classe base (Strategy Pattern)
│   ├── circulo_scraper.py
│   ├── mariskavos_scraper.py
│   ├── always_free_amigurumi_scraper.py
│   ├── lovecrafts_scraper.py     # Requer login e baixa PDFs
│   ├── amigurum_scraper.py       # Com condições de parada inteligentes
│   ├── ravelry_scraper.py        # API REST assíncrona com aiohttp
│   ├── scribd_scraper.py         # Requer conta paga, baixa e converte PDFs para base64
│   └── aifanshub_scraper.py      # Scroll dinâmico com Selenium, 8 campos + imagens
├── db/
│   ├── resultados/               # CSVs com dados e Parquet
│   ├── exports/                  # Dados consolidados e análises
│   └── *_urls.txt               # Arquivos com URLs
├── downloads/
│   ├── lovecrafts/               # PDFs do Lovecrafts
│   ├── scribd/                   # PDFs do Scribd
│   └── images/
│       └── aifanshub_images/     # Imagens do AIFansHub (JPEG)
├── main.py                       # Entry point para scrapers
├── processar_scribd.py           # Módulo para processar PDFs do Scribd
├── exportar_dados.py             # Exporta dados consolidados
├── analises_avancadas.py         # Análises avançadas (complexidade, materiais, etc)
├── requirements.txt
├── .env.example                  # Template de credenciais
└── .env                          # Suas credenciais (não commitado)
```

## Scripts de Análise e Exportação

### Exportar Dados Consolidados

```bash
python exportar_dados.py
```

Este script gera 3 arquivos na pasta `db/exports/`:
1. **amigurumi_completo.csv** - Todos os dados (3.718 receitas, ~1.7 GB)
2. **amigurumi_receitas_completas.csv** - Apenas receitas com título + receita preenchidos (~2.368 receitas, 63.7%)
3. **metadados.txt** - Estatísticas detalhadas do dataset

**⚠️ Importante**: O Scribd é processado **exclusivamente do Parquet** (`scribd_base64.parquet`), nunca do CSV. Isso garante:
- ✅ Dados corretos com texto extraído dos PDFs
- ✅ 790 documentos processados (756 com texto extraível)
- ✅ ~1.099.447 palavras extraídas
- ✅ Sem duplicação ou dados corrompidos

### Análises Avançadas

```bash
python analises_avancadas.py
```

Gera análises detalhadas:
- ✅ **Análise de Complexidade por Scraper** - Ranking baseado em tamanho e variação de texto
- ✅ **Análise de Materiais** - Materiais mais comuns (fio, agulhas, enchimento)
- ✅ **Distribuição de Tamanho de Receitas** - Curta/Média/Longa
- ✅ **Clustering** - Agrupamento de receitas similares
- ✅ **Word Cloud** - Termos mais frequentes

**Resultado das Análises (Fevereiro 2026)**:
```
Total de receitas: 3,718
Receitas completas: 2,368 (63.7%)

Distribuição por Scraper:
• Circulo: 551 receitas
• Scribd: 790 receitas (com PDFs processados)
• Lovecrafts: 469 receitas
• Always Free Amigurumi: 419 receitas
• Amigurum: 438 receitas
• Amigurumi Today: 354 receitas
• AIFansHub: 375 receitas
• Ravelry: 94 receitas
• Mariskavos: 84 receitas
• Menagerie: 52 receitas
• My Amigurumi Farm: 51 receitas
• Lilleliis: 41 receitas
```

## Características Especiais do Ravelry Scraper

O scraper do Ravelry é **diferente dos demais** pois usa a **API REST oficial** em vez de web scraping:

### Estrutura Assíncrona

- ✅ **AsyncRavelryScraper**: Classe interna que gerencia requisições HTTP assíncronas
- ✅ **aiohttp**: Biblioteca para requisições HTTP assíncronas eficientes
- ✅ **Context Manager**: Usa `async with` para gerenciar sessões HTTP
- ✅ **Rate Limiting**: 1 segundo entre requisições (respeita limites da API)
- ✅ **Concurrent Control**: Máximo de 3 requisições simultâneas

### Diferenças em Relação aos Outros Scrapers

| Característica | Outros Scrapers | Ravelry Scraper |
|----------------|-----------------|-----------------|
| Tecnologia | Selenium (navegador) | aiohttp (API REST) |
| Velocidade | Mais lento | Muito mais rápido |
| Autenticação | Login via formulário | HTTP Basic Auth |
| Dados | HTML parsing | JSON estruturado |
| Estrutura | Síncrona | **Assíncrona (async/await)** |

### Vantagens da API

1. **Mais Rápido**: Requisições HTTP diretas são muito mais rápidas que navegar páginas
2. **Dados Estruturados**: JSON bem formatado vs parsing de HTML
3. **Mais Confiável**: API oficial vs scraping que quebra com mudanças no site
4. **Dados Ricos**: Avaliações, dificuldade, materiais detalhados
5. **Rate Limits Claros**: 5000 requisições/hora (muito generoso)

### Como Funciona

```python
# Fluxo assíncrono do scraper
async with AsyncRavelryScraper(...) as scraper:
    # 1. Autentica com API
    await scraper._test_authentication_async()
    
    # 2. Busca padrões (async generator)
    async for pattern in scraper.fetch_patterns(max_pages=10):
        # 3. Busca detalhes de cada padrão
        details = await scraper.obter_detalhes_receita(pattern_id)
        
        # 4. Rate limiting automático (1s entre requests)
        await asyncio.sleep(1.0)
```

### Requisitos Especiais

- **aiohttp**: Adicionado ao `requirements.txt`
- **Credenciais de API**: Não usa credenciais de login normal
- **asyncio**: Usa event loop para operações assíncronas

## Características Especiais do Scribd Scraper

O scraper do Scribd é especializado para **download e conversão de PDFs**:

### Funcionalidades Principais

- ✅ **Login Obrigatório**: Usa conta paga para acessar conteúdo completo
- ✅ **Download de PDFs**: Baixa automaticamente documentos disponíveis
- ✅ **Conversão Base64**: Converte PDFs para formato base64
- ✅ **Extração de Metadados**: Título, autor, descrição
- ✅ **Paginação Inteligente**: Navega por múltiplas páginas de resultados
- ✅ **Validação de Documentos**: Verifica se documentos são baixáveis

### Estrutura de Dados

O CSV gerado contém:
- `url` - URL do documento no Scribd
- `title` - Título do documento
- `author` - Autor do documento
- `description` - Descrição/resumo
- `pdf_downloaded` - True/False indicando sucesso do download
- `pdf_path` - Caminho local do PDF baixado

Os PDFs são armazenados em:
- **Base64**: `db/resultados/scribd_base64.parquet` (para backup e processamento)
- **Arquivos**: `downloads/scribd/` (PDFs originais)

⚠️ **Importante**: Use `processar_scribd.py` (já integrado em `exportar_dados.py` e `analises_avancadas.py`) para processar PDFs do Scribd automaticamente.

### Limitações e Considerações

⚠️ **Importante**:
- Requer conta paga ativa no Scribd
- Alguns documentos podem ter restrições mesmo com conta paga
- Downloads em massa podem acionar medidas de segurança
- Arquivos CSV podem ficar muito grandes devido ao base64
- Respeite os Termos de Serviço do Scribd

### Configuração

Adicione suas credenciais no arquivo `.env`:
```
SCRIBD_EMAIL=seu_email@exemplo.com
SCRIBD_PASSWORD=sua_senha
```

Ou o scraper solicitará suas credenciais durante a execução.

## Características Especiais do AIFansHub Scraper

O scraper do AIFansHub coleta padrões de amigurumi do site [AIFansHub](https://www.aifanshub.com/search/label/AMIGURUMI%20PATTERN) com **scroll dinâmico usando Selenium**:

### Por Que Selenium?

O site AIFansHub **carrega posts dinamicamente via JavaScript** quando você faz scroll na página. Por isso:
- ❌ **Requests simples não funciona**: Só pega 3 posts iniciais
- ✅ **Selenium com scroll**: Carrega TODOS os posts disponíveis (~1200+)

### Funcionalidades Principais

- ✅ **Scroll Dinâmico**: Simula rolagem do usuário para carregar posts via JavaScript
- ✅ **Detecção Inteligente**: Para automaticamente quando não há mais conteúdo
- ✅ **8 Campos Essenciais**: Segue o padrão unificado de todos os scrapers
- ✅ **Extração Integrada de Imagens**: Download automático durante scraping
- ✅ **Receita Completa**: Instruções passo-a-passo preservando estrutura de seções
- ✅ **Materiais Estruturados**: Lista de materiais necessários separados por `|`
- ✅ **Abreviações de Crochê**: Glossário de termos técnicos (MR, sc, inc, dec, etc)
- ✅ **Alta Qualidade**: Imagens forçadas para resolução máxima (1600px via CDN)
- ✅ **Validação de Imagens**: Mínimo 150x150px, aspect ratio < 3:1
- ✅ **Rate Limiting**: 2 segundos entre posts para respeitar o servidor
- ✅ **Fallback Inteligente**: Se Selenium não disponível, usa requests (limitado)

### Estrutura de Dados

O CSV gerado contém exatamente **8 campos** (ordem fixa):

| # | Campo | Descrição | Exemplo |
|---|-------|-----------|---------|
| 1 | `titulo` | Título do padrão | "Leonardo Lobster Amigurumi" |
| 2 | `url` | URL do post | `https://www.aifanshub.com/2026/02/...` |
| 3 | `imagem_url` | URL da imagem principal | `https://blogger.googleusercontent.com/...` |
| 4 | `imagem_local` | Caminho local da imagem | `downloads/images/aifanshub_images/Leonardo_...jpeg` |
| 5 | `materiais` | Materiais (separados por \|) | "Worsted cotton yarn \| 2.75mm hook \| Safety eyes" |
| 6 | `abreviacoes` | Abreviações (separadas por \|) | "MR: Magic Ring \| sc: Single Crochet \| inc: Increase" |
| 7 | `receita` | Instruções completas | "R1: Create a MR, work 6 sc..." |
| 8 | `origem` | Fonte dos dados | "AIFansHub" |

### Exemplo de Uso

```bash
# Usar padrão (100 scrolls = ~1200 posts)
python main.py aifanshub

# Teste rápido (5 scrolls = ~65 posts)
python main.py aifanshub --max-pages 5 --limit 10

# Coleta média (20 scrolls = ~245 posts)
python main.py aifanshub --max-pages 20

# Diferentes categorias
python main.py aifanshub --label bags --max-pages 15
```

### Configuração

O parâmetro `--max-pages` agora controla **número de scrolls**, não páginas:
- **1 scroll** = ~12-15 novos posts carregados
- **5 scrolls** = ~65 posts
- **20 scrolls** = ~245 posts
- **100 scrolls** (padrão) = ~1200 posts

### Como Funciona o Scroll Dinâmico

```python
# 1. Selenium abre navegador
driver.get("https://www.aifanshub.com/search/label/AMIGURUMI%20PATTERN")

# 2. Loop de scrolls
for scroll in range(1, 101):  # 100 scrolls
    # Extrair posts carregados
    posts = extract_posts_from_page()
    
    # Fazer scroll para baixo
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    # Aguardar JavaScript carregar novos posts
    time.sleep(2)
    
    # Verificar se há novos posts
    if no_new_posts_for_3_scrolls:
        break  # Para automaticamente

# 3. Processar cada post individualmente
for post_url in all_posts:
    pattern_data = extract_pattern_data(post_url)
    download_image(pattern_data['imagem_url'])
```

### Extração de Dados Detalhada

#### 1. Materiais
- **Fonte**: Seções "Materials:" ou "PROJECT INFO"
- **Formato**: Lista separada por `|`
- **Exemplo**: `Worsted weight cotton yarn (Red) | 2.75mm crochet hook | 10mm safety eyes | Fiberfill stuffing`

#### 2. Abreviações
- **Fonte**: Seção "KEY ABBREVIATIONS"
- **Formato**: `SIGLA: Significado | SIGLA2: Significado2`
- **Exemplo**: `MR: Magic Ring | sc: Single Crochet | inc: Increase | dec: Invisible Decrease | FLO: Front Loops Only`

#### 3. Receita
- **Fonte**: Seção "✨ THE PATTERN"
- **Estrutura**: Preserva seções (SECTION 1, SECTION 2, etc)
- **Formato**: Linhas iniciando com `R1:`, `R2:`, etc
- **Exemplo**:
  ```
  [SECTION 1: THE ROSTRUM & HEAD]
  R1: Create a MR, work 6 sc into the ring. Pull tight. [6]
  R2: (sc in next st, inc in next st) repeat x3. [9]
  
  [SECTION 2: THE THORAX & BODY]
  R15: (sc in next 5 st, inc in next st) repeat x6. [42]
  ```

#### 4. Imagens
- **Validação**: Mínimo 150x150 pixels, aspect ratio < 3:1
- **Qualidade**: Forçado para `/s1600/` (máxima resolução do CDN Blogger)
- **Formato**: JPEG com qualidade 95, otimizado
- **Nome**: `{titulo_seguro}_{hash}.jpeg`
- **Exclusões**: Ícones, logos, avatares, profiles

### Performance

| Configuração | Scrolls | Posts | Tempo Estimado |
|--------------|---------|-------|----------------|
| Teste | 5 | ~65 | ~3-5 minutos |
| Média | 20 | ~245 | ~12-15 minutos |
| Completa | 100 | ~1200 | ~60-90 minutos |

**Nota**: Tempo inclui scroll + download de imagens (~2s por post)

### Vantagens

1. **Scroll Dinâmico**: Carrega TODOS os posts disponíveis (não apenas 3)
2. **Consistência**: Mesmo padrão de 8 campos dos outros scrapers
3. **Extração Integrada**: Não precisa de script separado para baixar imagens
4. **Receita Estruturada**: Instruções completas com seções organizadas
5. **Alta Qualidade**: Imagens em resolução máxima (1600px)
6. **Dados Completos**: Materiais e abreviações essenciais para replicar padrão
7. **Simplicidade**: Apenas CSV, fácil de integrar com outros dados
8. **Parada Inteligente**: Detecta automaticamente quando não há mais posts

### Estrutura de Arquivos

```
db/
├── aifanshub_urls.txt              # URLs coletadas
└── resultados/
    └── aifanshub_dados.csv         # Dados principais (8 colunas)

downloads/
└── images/
    └── aifanshub_images/           # Imagens baixadas (JPEG)
```

### Comparação com Outros Scrapers

| Aspecto | AIFansHub | Ravelry | Scribd | Lovecrafts |
|---------|-----------|---------|--------|------------|
| **Tecnologia** | Selenium (scroll) | API REST | Selenium | Selenium |
| **Campos** | 8 | 8 | 8 | 8 |
| **Extração de imagem** | Integrada ✅ | Integrada ✅ | Separada ⚙️ | Separada ⚙️ |
| **Receita completa** | Sim ✅ | Sim ✅ | Sim ✅ | Sim ✅ |
| **Materiais** | Sim ✅ | Sim ✅ | Sim ✅ | Sim ✅ |
| **Abreviações** | Sim ✅ | Sim ✅ | Sim ✅ | Sim ✅ |
| **Formato** | CSV | CSV | CSV | CSV |
| **Autenticação** | Não | Sim (API) | Não | Não |
| **Paginação** | Scroll JS | API pages | Static | Static |
| **Posts disponíveis** | ~1200+ | ~94 | ~790 | ~469 |

### Configurações Avançadas

#### Ajustar Número de Scrolls
```bash
# Teste rápido (5 scrolls = ~65 posts)
python main.py aifanshub --max-pages 5

# Coleta média (20 scrolls = ~245 posts)
python main.py aifanshub --max-pages 20

# Coleta completa (100 scrolls = ~1200 posts)
python main.py aifanshub --max-pages 100
```

#### Limitar Número de Padrões Processados
```bash
# Apenas primeiros 20 posts
python main.py aifanshub --limit 20

# Processar todos encontrados
python main.py aifanshub
```

#### Diferentes Categorias
```bash
# Amigurumi (padrão)
python main.py aifanshub --label amigurumi

# Bolsas
python main.py aifanshub --label bags

# Estilo
python main.py aifanshub --label style

# Todos os blogs
python main.py aifanshub --label all
```

## Troubleshooting

### Lovecrafts não faz login
- Verifique se o arquivo `.env` existe e está preenchido
- Teste suas credenciais no site manualmente
- Use `--no-headless` para ver o que está acontecendo

### Scribd não faz login ou não baixa PDFs
- Verifique se sua conta Scribd está ativa e paga
- Alguns documentos não permitem download mesmo com conta paga
- Use `--no-headless` para debug visual
- Verifique se o diretório `downloads/scribd` foi criado
- O Scribd pode ter CAPTCHA ou verificação 2FA

### Downloads muito lentos
- O scraper já está otimizado
- Considere limitar o número de receitas processadas
- A velocidade depende da conexão com a internet

### Erro de elemento não clicável
- Use `--no-headless` para debug
- O scraper tenta múltiplas estratégias de click
- Pode haver mudanças no site que requerem atualização do scraper

### AIFansHub - Apenas 3 posts sendo coletados

**Problema**: Site carrega posts dinamicamente via JavaScript

**Causa**: O site AIFansHub usa **scroll infinito**. O HTML inicial contém apenas 3 posts. Mais posts são carregados via JavaScript quando você rola a página.

**Solução**: O scraper agora usa **Selenium com scroll dinâmico**:
- ✅ Simula rolagem do usuário
- ✅ Aguarda JavaScript carregar novos posts
- ✅ Para automaticamente quando não há mais conteúdo
- ✅ Coleta ~1200+ posts disponíveis

```bash
# Usar scraper com scroll dinâmico (padrão: 100 scrolls)
python main.py aifanshub
```

### AIFansHub - Receita vazia
- Verifique se o post tem seção "THE PATTERN" ou "✨ THE PATTERN"
- HTML pode ter estrutura diferente do esperado
- Alguns posts podem ter receita em formato de imagem (OCR necessário)

### AIFansHub - Materiais vazios
- Verifique se há seção "Materials:" ou "PROJECT INFO"
- Formato do post pode ser diferente
- Alguns posts linkam materiais em vez de listar diretamente

### AIFansHub - Abreviações vazias
- Normal: nem todos os posts têm seção de abreviações
- Posts mais simples podem assumir que leitor conhece termos básicos

### AIFansHub - Imagem não baixa
**Causas possíveis**:
- Imagem muito pequena (< 150x150 pixels)
- Aspect ratio muito alto (> 3:1, ex: banners)
- URL inválida ou imagem deletada do CDN
- Apenas ícones/logos disponíveis (filtrados automaticamente)

**Solução**: Verificar logs do scraper, validar URL manualmente no navegador

### AIFansHub - URLs do Pinterest aparecendo
- Improvável: filtro automático remove pinterest.com, facebook.com, twitter.com, instagram.com
- Se ocorrer, verificar se filtro em `extract_post_links()` está ativo
- Reportar URL específica para ajuste do filtro

### Exportador - Scribd sendo carregado do CSV

**Problema**: Dados do Scribd duplicados ou incorretos no export final

**Causa**: O script `exportar_dados.py` estava carregando `scribd_dados.csv` (dados antigos e incompletos) além do Parquet.

**Sintomas**:
- Dados do Scribd sem texto da receita
- Campos faltando (`materiais`, `abreviacoes`, `receita`)
- Contagem duplicada de receitas

**Solução Aplicada** (Fevereiro 2026):
```python
# Antes (BUGADO)
for f in arquivos_csv:
    try:
        nome = os.path.basename(f)
        if 'scribd' in nome.lower():
            print("Será processado do Parquet")
            continue  # ❌ DENTRO do try, não funcionava!

# Depois (CORRETO)
for f in arquivos_csv:
    nome = os.path.basename(f)
    if 'scribd' in nome.lower():
        print("Ignorado (será processado do Parquet)")
        continue  # ✅ ANTES do try, funciona perfeitamente!
    try:
        # ... processar outros CSVs
```

**Resultado**:
- ✅ Scribd processado APENAS do `scribd_base64.parquet`
- ✅ 790 documentos com texto extraído dos PDFs
- ✅ ~1.099.447 palavras processadas
- ✅ Sem duplicação de dados
