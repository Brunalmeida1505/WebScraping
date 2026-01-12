# Web Scraping - Recipe Scrapers

Este projeto contém scrapers para coletar receitas de diversos sites de crochê e tricô.

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
```

### Exemplos

```bash
# Scraper do Circulo
python main.py circulo

# Scraper do Lovecrafts (com credenciais do .env)
python main.py lovecrafts

# Scraper do Mariskavos com 20 páginas
python main.py mariskavos --max-pages 20

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

## Estrutura do Projeto

```
├── scrapers/
│   ├── base_scraper.py           # Classe base (Strategy Pattern)
│   ├── circulo_scraper.py
│   ├── mariskavos_scraper.py
│   ├── always_free_amigurumi_scraper.py
│   └── lovecrafts_scraper.py
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
