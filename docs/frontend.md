# Frontend - Arquitetura, Fluxos e Padroes

## 1. Stack

- Framework: Next.js 15 (App Router)
- Linguagem: TypeScript
- UI: React 19 + Tailwind CSS v4
- Estado global: Zustand (carrinho)
- PWA: `next-pwa` (build de producao)

## 2. Estrutura de Pastas

Base: `roksell-frontend/src`

- `app/`
  - paginas publicas, portal e admin central
  - route handlers internos (`app/api/*`)
- `components/`
  - componentes compartilhados e componentes admin
  - `catalog/PriceInput.tsx`: campo de preço com preenchimento a partir dos centavos (portal catálogo)
  - `admin/FieldTooltip.tsx`: ícone ? com tooltip para campos de formulário
  - `admin/BannerCropModal.tsx`: ajuste de imagem de banner com zoom e dimensões pré-definidas (1200×400 px)
- `lib/`
  - utilitarios HTTP, auth e hooks
- `store/`
  - estado global (`cart.ts`)
- `config/`
  - configuracao de menu admin
- `types.ts`
  - tipos compartilhados de API/UI

## 3. Arquitetura de Rotas

## 3.1 Publicas

- `/`: landing
- `/vitrine/[slug]`: vitrine do tenant
- `/vitrine/[slug]/[store]`: vitrine por loja
- `/checkout`: checkout client-side
- `/pedido/[id]`: rastreio de pedido publico
- `/pedidos/[id]`: redirect de compatibilidade para `/pedido/[id]`

## 3.2 Portal (tenant) — ferramenta RokSell

Prefixo: `/roksell/*`

Paginas principais:

- home
- login
- primeiro acesso
- catalogo
- pedidos
- clientes
- usuarios
- lojas
- estoque
- campanhas
- insights
- mensagens
- billing
- config (redirect)

## 3.3 Admin central SaaS

Prefixo: `/admin/*`

- `/admin/login`
- `/admin`
- `/admin/planos`

## 3.4 Route handlers internos (`/api/*`)

Objetivo: atuar como BFF/proxy entre browser e backend.

Grupos:

- auth:
  - `/api/auth/login`
  - `/api/auth/logout`
  - `/api/auth/me`
- proxy admin autenticado por cookie:
  - `/api/admin/[...path]`
- proxy publico:
  - `/api/catalog`
  - `/api/stores`
  - `/api/shipping`
  - `/api/checkout`
  - `/api/checkout/preview`

## 4. Camada de Dados no Front

## 4.1 `src/lib/api.ts`

Uso para chamadas gerais (publicas, SSR/CSR):

- escolhe base URL por contexto:
  - server: `API_URL`
  - browser: `NEXT_PUBLIC_API_URL`

## 4.2 `src/lib/admin-api.ts`

Uso para area admin/portal:

- sempre chama `/api/admin/*`
- `credentials: include`
- parse padronizado de erro
- `adminFetch` para JSON
- `adminUpload` para `FormData`

Regra: pagina de portal/admin nao deve chamar backend autenticado direto; deve usar proxy.

## 5. Auth e Guardas de Rota

## 5.1 Cookies de sessao

- `admin_token` (HttpOnly)
- `tenant_slug` (nao HttpOnly, usado para contexto visual/guard)

## 5.2 Hooks

- `useAdminGuard`
  - protege `/roksell/*`
  - valida `/api/auth/me`
  - redireciona para login quando invalido
  - verifica onboarding e redireciona quando necessario
- `useSuperAdminGuard`
  - protege `/admin/*`
  - exige `tenant_slug` igual ao `NEXT_PUBLIC_SUPER_ADMIN_SLUG`

## 5.3 Modulos por assinatura

- hook `useTenantModules`
  - consome `/api/admin/modules`
  - fornece:
    - `hasModule(key)`
    - `hasModuleAction(key, 'view' | 'edit')`

## 6. Estado e Formularios

## 6.1 Estado global

- `useCart` (Zustand):
  - itens, subtotal e manipulacao de quantidade
  - suporte a produtos customizados e adicionais

## 6.2 Estado local

Padrao dominante:

- `useState` para formulario/tabela/modal
- `useEffect` para carga inicial e refresh
- sem biblioteca dedicada de form/state machine no momento

## 7. Componentes Estruturais de Admin

## 7.1 `AdminSidebar`

Responsavel por:

- navegacao lateral
- leitura de tenant info
- exibicao de modulos ativos
- badge de mensagens nao lidas
- atalhos de copia de link de vitrine

## 7.2 `ProfileBadge`

Identificacao do usuario autenticado no topo das telas.

## 7.3 `UsersManagerPanel`

Painel complexo para:

- grupos de permissao
- usuarios
- associacao de loja e sessoes maximas

## 8. UI/UX e Estilo

- Tailwind classes utilitarias, sem design system formal em componentes atomicos.
- Tema atual usa base roxa (`#6320ee`) em varias paginas.
- `globals.css` contem variaveis e utilitarios de input.
- Layouts de portal/admin priorizam desktop com responsividade progressiva.

Ponto tecnico:

- existem sinais de divergencia entre tema definido e tema praticado.
- consolidar tokens visuais em uma fonte unica e recomendado.

## 9. PWA

Configuracao:

- plugin `next-pwa` no `next.config.js`
- `manifest.json` em `public/`
- desativado em dev, ativo em producao

## 10. Como Criar Nova Pagina no Portal (Padrao)

1. Criar rota em `src/app/roksell/<modulo>/page.tsx`.
2. Marcar como client component se usar hooks (`"use client"`).
3. Aplicar `const ready = useAdminGuard();`.
4. Carregar dados via `adminFetch`.
5. Bloquear modulo quando necessario com `useTenantModules`.
6. Renderizar com `AdminSidebar` + `ProfileBadge`.
7. Tratar estados de loading/erro/empty.
8. Atualizar menu em `src/config/adminMenu.ts` se aplicavel.

## 11. Riscos Tecnicos Atuais no Front

- varias telas densas e totalmente client-side
- ausencia de testes automatizados de interface
- sem convencao unica para extracao de hooks de pagina
- validacao de formulario concentrada em componentes grandes

## 12. Recomendacoes Prioritarias

1. Extrair hooks de dados por modulo (`useOrdersData`, `useCatalogData`, etc).
2. Padronizar componentes de tabela/form/modal.
3. Definir guideline de mensagens de erro e estados de loading.
4. Introduzir testes de smoke para rotas criticas (login, catalogo, checkout, pedidos).

## 13. Pagina de Produtos (Portal Catalogo)

- Rota: `/roksell/produtos`. Abas: Produtos, Categorias, Adicionais (cada uma com listagem e filtro de status).
- Produtos: ate 5 fotos em carrossel, video unico com posicao (inicio ou final). Campo preco: componente `PriceInput` (centavos-first).
- Categorias: hierarquia aberta por padrao, minimizar por categoria; campo "Ordem de exibicao".
- Adicionais: foto (upload) e mesmo formato de preco. Labels obrigatorio/opcional nos formularios.
- Produtos: campo opcional "Unidade de medida" (ex.: un, kg, cx) exibida no menu de estoque.

## 14. Pagina de Estoque (Portal)

- Rota: `/roksell/estoque`. Listagem por loja com filtro de status (Ativos/Todos/Inativos), padrao Ativos.
- Tabela: foto (thumbnail), codigo do produto (6 digitos), nome, estoque atual (quantidade + unidade de medida) e botao de movimentacao.
- Busca: filtra por nome ou codigo do produto (campo unico).
- Filtro de status: um botao com icone de filtro; ao clicar, exibe as opcoes Ativos / Todos / Inativos.
- Movimentacao: modal com tipo (adicao ou subtracao) e quantidade; chama `POST /admin/inventory/move`.
- Contagem de produtos exibida abaixo do titulo "Produtos" da grade, em italico ("X produtos").
