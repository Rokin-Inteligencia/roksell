# Correção: coluna `products.code` não existe

## Erro observado

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedColumn) column products.code does not exist
LINE 1: ...id, products.category_id AS products_category_id, products.c...
```

**Onde:** `get_catalog_for_admin` em `app/services/catalog_admin.py` (query de `Product`).

## Causas possíveis

1. **Migração não aplicada:** O modelo SQLAlchemy foi alterado para incluir `code` e `unit_of_measure`, mas a migração `20260312_product_code_um` ainda não foi aplicada ao banco.
2. **Revisão fantasma no banco:** O banco pode estar com uma revisão em `alembic_version` que não existe mais no código (ex.: `20260306_provider_order_id`), fazendo `alembic upgrade head` falhar com "Can't locate revision".

## Hipótese confirmada (H1)

- A migração `20260312_add_product_code_and_unit_of_measure` **não foi aplicada** ao banco conectado pela aplicação (ou foi aplicada em outro ambiente).

## Correção

### Se `alembic upgrade head` falhar com "Can't locate revision"

1. Corrija a revisão gravada no banco (ex.: de `20260306_provider_order_id` para uma revisão existente):

   ```bash
   cd roksell-backend
   .\.venv\Scripts\python.exe scripts\fix_alembic_revision.py
   ```

2. Depois aplique as migrações:

   ```bash
   .\.venv\Scripts\alembic.exe upgrade head
   ```

### Caso normal

1. Ative o ambiente virtual do backend (se usar um).
2. No diretório do backend:

   ```bash
   cd roksell-backend
   alembic upgrade head
   ```

3. Reinicie o servidor da API (ex.: uvicorn) para usar o schema atualizado.

A migração:

- Cria as colunas `products.code` (integer) e `products.unit_of_measure` (varchar 24).
- Preenche `code` de forma sequencial por `(tenant_id, store_id)`.
- Torna `code` NOT NULL com default 1.
- Cria o índice único `uq_product_code_tenant_store` para garantir código único por tenant e loja.

## Verificação

Após `alembic upgrade head` e reinício do servidor:

- O catálogo admin (GET do catálogo) deve responder sem erro.
- Em `debug-1a155e.log`, a linha de “products.code column check” deve ter `"column_code_exists": true`.

## UniqueViolation ao salvar produto (troca de loja)

Se ao **editar/salvar** um produto aparecer:

```text
UniqueViolation: duplicate key value violates unique constraint "uq_product_code_tenant_store"
Key (tenant_id, COALESCE(store_id::text, ''), code)=(..., ..., 1) already exists.
```

é porque o produto está sendo alterado para uma loja onde já existe outro produto com o mesmo `code`. O `code` é único por (tenant_id, store_id). Ao **mudar a loja** do produto, o sistema passa a atribuir um novo `code` sequencial para a loja de destino em `update_product`, evitando esse conflito. Garanta que está usando a versão atual do serviço (com essa correção).

## Referências

- Migração: `roksell-backend/alembic/versions/20260312_add_product_code_and_unit_of_measure.py`
- Modelo: `roksell-backend/app/domain/catalog/models.py` (classe `Product`)
- Documentação de schema: `docs/database.md` (seção 3.3 Catalogo e produto)
