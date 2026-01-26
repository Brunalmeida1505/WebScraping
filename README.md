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

# Limitar número de páginas (apenas mariskavos, alwaysfreeamigurumi e ravelry)
python main.py mariskavos --max-pages 10

# Limitar número de scrolls no Amigurum
python main.py amigurum --max-pages 30

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
│   └── scribd_scraper.py         # Requer conta paga, baixa e converte PDFs para base64
├── db/
│   ├── resultados/               # CSVs com dados e Parquet
│   ├── exports/                  # Dados consolidados e análises
│   └── *_urls.txt               # Arquivos com URLs
├── downloads/
│   ├── lovecrafts/               # PDFs do Lovecrafts
│   └── scribd/                   # PDFs do Scribd
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

Este script gera 2 arquivos na pasta `db/exports/`:
1. **amigurumi_completo.csv** - Todos os dados (2.051 receitas incluindo 3 Scribd, ~1.7 GB)
2. **amigurumi_receitas_completas.csv** - Apenas receitas com materiais e instruções completas (~1.387 receitas)

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

**Resultado das Análises (Janeiro 2026)**:
```
Total de receitas: 2,051
Total analisadas: 2,051 (100%)

Ranking de Complexidade:
1º AlwaysFreeAmigurumi - 113.4 (Alta)
2º Scribd - 108.0 (Alta)
3º Lovecrafts - 99.0 (Alta)
4º Amigurum - 40.6 (Alta)
5º Mariskavos - 38.2 (Alta)
6º Circulo - 8.7 (Baixa - Iniciantes)
7º Ravelry - API REST

Materiais Mais Comuns:
- pattern: 892 receitas
- amigurumi: 890 receitas
- free: 679 receitas
- crochet: 610 receitas
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
