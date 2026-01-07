"""Script para raspar dados de receitas do site circulo.com.br.

Funcionalidades:
- Extração inicial: Se o arquivo 'db/resultados/dados.csv' não existir,
uma extração completa é forçada para criar o banco de dados inicial.
- Extração incremental: Anexa novas receitas ao arquivo CSV existente.
- Cache de URLs: Salva as URLs em 'db/urls.txt' para controle.
- Verificação rápida: Compara quantidade estimada (páginas × itens) antes de coletar URLs.

Estratégias de Validação:
- Padrão: Atualiza se a contagem estimada de receitas for diferente da do cache.
- --strict-sync: Atualiza se houver QUALQUER diferença entre o site e o cache.

Outras Flags:
- --update-urls-only: Apenas atualiza a lista de URLs e encerra.
- --force: Força uma nova extração de TODAS as receitas.
- --limit [N] / --range [INICIO] [FIM]: Para testes.
"""