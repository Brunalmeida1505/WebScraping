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

# Limitar número de páginas (apenas mariskavos e alwaysfreeamigurumi)
python main.py mariskavos --max-pages 10

# Limitar número de scrolls no Amigurum
python main.py amigurum --max-pages 30
```

### Exemplos

```bash
# Scraper do Circulo
python main.py circulo

# Scraper do Lovecrafts (com credenciais do .env)
python main.py lovecrafts

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

### Formato CSV

Todos os scrapers salvam dados no formato:
- `titulo` - Título da receita
- `url` - URL da receita
- `materiais` - Materiais necessários / Abreviações
- `receita` - Instruções da receita
- `origem` - Nome do site de origem

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
│   └── amigurum_scraper.py       # Com condições de parada inteligentes
├── db/
│   ├── resultados/               # CSVs com dados
│   └── *_urls.txt               # Arquivos com URLs
├── downloads/                    # PDFs do Lovecrafts
├── main.py                       # Entry point
├── requirements.txt
├── .env.example                  # Template de credenciais
└── .env                          # Suas credenciais (não commitado)
```

## Troubleshooting

### Lovecrafts não faz login
- Verifique se o arquivo `.env` existe e está preenchido
- Teste suas credenciais no site manualmente
- Use `--no-headless` para ver o que está acontecendo

### Downloads muito lentos
- O scraper já está otimizado
- Considere limitar o número de receitas processadas
- A velocidade depende da conexão com a internet

### Erro de elemento não clicável
- Use `--no-headless` para debug
- O scraper tenta múltiplas estratégias de click
- Pode haver mudanças no site que requerem atualização do scraper
