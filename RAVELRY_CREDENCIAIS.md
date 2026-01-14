# 🧶 Como Obter Credenciais do Ravelry - Passo a Passo

## 🎯 Objetivo

Este guia mostra **exatamente** como criar credenciais para usar a API do Ravelry no scraper.

---

## ⚠️ IMPORTANTE

O Ravelry **NÃO aceita** suas credenciais de login normais (email/senha) para acessar a API. 

Você precisa criar **credenciais de desenvolvedor** específicas seguindo os passos abaixo.

---

## 📋 Método Recomendado: Basic Account (HTTP Basic Auth)

### **Passo 1: Criar uma conta no Ravelry** (se ainda não tiver)

1. Acesse: https://www.ravelry.com/account/login
2. Clique em **"Sign up"** (canto superior direito)
3. Preencha:
   - Username (nome de usuário)
   - Email
   - Password
4. Confirme seu email
5. Faça login

### **Passo 2: Acessar a área de desenvolvedor**

1. Após fazer login, acesse: https://www.ravelry.com/pro/developer
2. Você verá a página "Ravelry API Developer Account"

### **Passo 3: Criar um Basic Account**

Na página de desenvolvedor, você verá duas opções:

#### **OPÇÃO A: Basic Account** ⭐ **RECOMENDADO**

1. Procure pela seção **"Basic Authentication"**
2. Clique em **"Enable read-only API access"** ou **"Get Basic Access"**
3. O Ravelry irá gerar automaticamente:
   - **Username**: seu nome de usuário do Ravelry
   - **Read Access Key**: uma chave de acesso única (parece com: `bd9d62f0c0af9f62a3dee81f3f65e57c`)

4. **IMPORTANTE**: Copie e guarde essa chave! Ela não será mostrada novamente.

#### **OPÇÃO B: Registered Application** (mais complexo)

Se você preferir criar um aplicativo registrado:

1. Clique em **"Register New Application"**
2. Preencha o formulário:
   ```
   Application Name: Amigurumi Scraper
   Description: Personal scraper for free amigurumi patterns
   Website: https://github.com/seu-usuario (ou deixe em branco)
   Callback URL: (deixe em branco para uso pessoal)
   ```
3. Clique em **"Create"**
4. Anote as credenciais geradas:
   - **Username**: seu usuário
   - **Access Key**: chave de acesso
   - **Personal Key**: chave pessoal (opcional)

### **Passo 4: Configurar o arquivo `.env`**

Abra o arquivo `.env` na raiz do projeto e adicione suas credenciais:

#### Se usou **Basic Account** (Opção A):

```env
# Ravelry Credentials - Basic Account
RAVELRY_USERNAME=seu_usuario_ravelry
RAVELRY_APIKEY=sua_read_access_key_aqui
RAVELRY_PASSWORD=sua_read_access_key_aqui
RAVELRY_USER_AGENT=AmigurumiScraper/1.0 (seu_email@exemplo.com)
```

**Exemplo real** (substitua com suas credenciais):
```env
RAVELRY_USERNAME=bruna.malmeida91@gmail.com
RAVELRY_APIKEY=bd9d62f0c0af9f62a3dee81f3f65e57c
RAVELRY_PASSWORD=bd9d62f0c0af9f62a3dee81f3f65e57c
RAVELRY_USER_AGENT=AmigurumiScraper/1.0 (bruna.malmeida91@gmail.com)
```

#### Se usou **Registered Application** (Opção B):

```env
# Ravelry Credentials - Registered App
RAVELRY_USERNAME=seu_usuario_ravelry
RAVELRY_APIKEY=sua_access_key_aqui
RAVELRY_PASSWORD=sua_personal_key_aqui
RAVELRY_USER_AGENT=AmigurumiScraper/1.0 (seu_email@exemplo.com)
```

---

## 🔍 Passo 5: Testar as Credenciais

Depois de configurar o `.env`, teste se está funcionando:

```bash
# Teste rápido (1 página)
python main.py ravelry --max-pages 1

# Teste completo (10 páginas)
python main.py ravelry --max-pages 10
```

### **Mensagens esperadas:**

✅ **Se funcionar corretamente:**
```
Setting up WebDriver for 'RavelryScraper'...
✓ Using Ravelry API Key (username: seu_usuario)
Running scraper: Ravelry...

Testing Ravelry API authentication...
✓ Authentication successful! User: seu_usuario

✓ Collecting patterns with details (max 1 pages)...
  Processed 10 patterns...
  Processed 20 patterns...
✓ Data saved to db/resultados/ravelry_dados.csv (100 recipes)
```

❌ **Se as credenciais estiverem erradas:**
```
✗ Authentication failed: 403 Forbidden
  → Your credentials are not authorized for API access
```

---

## 🐛 Solucionando Problemas

### Erro: `403 Forbidden`
**Causa:** Credenciais não autorizadas ou inválidas

**Solução:**
1. Verifique se você criou o **Basic Account** ou **Registered Application**
2. Confirme que copiou a **Read Access Key** corretamente (sem espaços)
3. Certifique-se de que está usando a chave de API, não sua senha de login
4. Tente revogar e criar novas credenciais em: https://www.ravelry.com/pro/developer

### Erro: `401 Unauthorized`
**Causa:** Username ou API Key incorretos

**Solução:**
1. Verifique o username no `.env` (deve ser exatamente igual ao do Ravelry)
2. Confirme que a API Key está correta
3. Não use email como username, use o username do Ravelry

### Erro: `Ravelry credentials not found in .env file`
**Causa:** Arquivo `.env` não configurado ou variáveis ausentes

**Solução:**
1. Verifique se o arquivo `.env` está na **raiz do projeto**
2. Certifique-se que não há **espaços extras** antes/depois do `=`
3. Verifique se as variáveis estão escritas corretamente:
   - `RAVELRY_USERNAME`
   - `RAVELRY_APIKEY`
   - `RAVELRY_PASSWORD`
   - `RAVELRY_USER_AGENT`

### Erro: `Connection error`
**Causa:** Problemas de rede ou site fora do ar

**Solução:**
1. Verifique sua conexão com a internet
2. Tente acessar https://www.ravelry.com no navegador
3. Aguarde alguns minutos e tente novamente

---

## 📖 Links Úteis

- **API Developer Page**: https://www.ravelry.com/pro/developer
- **API Documentation**: https://www.ravelry.com/api
- **Developer Forum**: https://www.ravelry.com/groups/ravelry-api
- **Rate Limits**: 5000 requests/hour (muito generoso!)

---

## 📊 Detalhes Técnicos

### O que o scraper faz:

1. **Autentica** usando HTTP Basic Auth (username:api_key)
2. **Busca padrões** usando `/patterns/search.json` com filtros:
   - `craft: 'crochet'`
   - `query: 'amigurumi'`
   - `availability: 'free'` (apenas receitas gratuitas!)
   - `page_size: 100` (máximo permitido)
3. **Coleta detalhes** de cada padrão via `/patterns/{id}.json`
4. **Extrai informações**: materiais, dificuldade, avaliação, metragem
5. **Salva em CSV**: formato compatível com outros scrapers

### Rate Limiting:

- ✅ 1 segundo entre requisições (automático)
- ✅ Máximo 3 requisições simultâneas
- ✅ Respeita limite de 5000 req/hora da API

### Dados coletados:

```csv
titulo;url;materiais;receita;origem
"Amigurumi Bear";"https://...";Peso do fio: DK | Gauge: 20 sts | Dificuldade: 3.5/5 | Avaliação: 4.8/5;"Ver padrão completo no link";"Ravelry"
```

---

## ✅ Checklist Final

Antes de usar o scraper, confirme:

- [ ] Conta criada no Ravelry
- [ ] Basic Account ou Registered Application criado
- [ ] Read Access Key copiada
- [ ] Arquivo `.env` configurado na raiz do projeto
- [ ] Variáveis `RAVELRY_USERNAME`, `RAVELRY_APIKEY`, `RAVELRY_PASSWORD`, `RAVELRY_USER_AGENT` preenchidas
- [ ] Teste realizado: `python main.py ravelry --max-pages 1`
- [ ] Autenticação bem-sucedida: `✓ Authentication successful!`

---

## 🎉 Pronto!

Se você seguiu todos os passos e a autenticação foi bem-sucedida, o scraper está pronto para coletar receitas gratuitas de amigurumi do Ravelry!

**Vantagens da API do Ravelry:**
- ⚡ Muito mais rápido que web scraping
- 📊 Dados estruturados e ricos (avaliações, dificuldade, materiais)
- 🔒 Mais confiável (não quebra com mudanças no site)
- 🎯 Filtros precisos (apenas receitas gratuitas)

**Aproveite!** 🧶
