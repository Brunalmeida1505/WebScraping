# Credenciais do Scribd

Para usar o scraper do Scribd, você precisa de uma conta paga.

## Configuração

### Opção 1: Variáveis de Ambiente (Recomendado)

Crie um arquivo `.env` na raiz do projeto com:

```
SCRIBD_EMAIL=seu_email@exemplo.com
SCRIBD_PASSWORD=sua_senha
```

### Opção 2: Inserir Manualmente

Se você não configurar as variáveis de ambiente, o scraper irá solicitar suas credenciais quando for executado.

## Uso

```python
from selenium import webdriver
from scrapers.scribd_scraper import ScribdScraper

# Configurar driver
driver = webdriver.Chrome()

# Criar scraper
scraper = ScribdScraper(driver)

# Executar
scraper.run({
    'force': False,  # True para forçar nova coleta de URLs
    'limit': 10,     # Número máximo de documentos para processar
    'email': 'seu_email@exemplo.com',  # Opcional se estiver no .env
    'password': 'sua_senha'             # Opcional se estiver no .env
})

driver.quit()
```

## Estrutura de Arquivos

- `db/scribd_urls.txt` - Lista de URLs coletadas
- `db/resultados/scribd_dados.csv` - Dados extraídos (título, autor, descrição, etc.)
- `downloads/scribd/` - PDFs baixados

## Notas Importantes

- ⚠️ O Scribd possui proteções anti-bot. Use delays apropriados entre requisições.
- ⚠️ Respeite os Termos de Serviço do Scribd.
- ⚠️ A conversão para base64 pode gerar arquivos CSV muito grandes.
- ⚠️ Certifique-se de que sua conta Scribd está ativa e com acesso aos documentos.

## Limitações

- Alguns documentos podem não estar disponíveis para download mesmo com conta paga
- O Scribd pode ter diferentes tipos de acesso (preview, download, etc.)
- Downloads em massa podem acionar medidas de segurança do site
