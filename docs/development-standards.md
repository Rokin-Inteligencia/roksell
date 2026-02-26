# Padroes de Desenvolvimento

Este documento define padroes obrigatorios para evolucao do projeto.

## 1. Principios Gerais

1. Multi-tenant first: toda feature deve respeitar isolamento por tenant.
2. Seguranca por padrao: nao assumir confianca no cliente.
3. Simplicidade orientada a dominio: regras de negocio no backend.
4. Consistencia de API e UI acima de preferencia individual.
5. Documentacao atualizada junto da mudanca estrutural.

## 2. Backend Standards

## 2.1 Estrutura de codigo

- Router por contexto de negocio em `app/routers/`.
- Modelos e regras de dominio em `app/domain/`.
- Integracoes externas e orquestracao em `app/services/`.
- Schemas de request/response em `app/schemas.py`.

## 2.2 Regras de endpoint

Todo endpoint novo deve:

1. usar schema de entrada/saida (Pydantic)
2. validar tenant com `TenantContext`
3. aplicar `require_roles` conforme criticidade
4. aplicar `require_module`/`require_module_action` quando for funcionalidade de modulo
5. filtrar dados por `tenant_id`
6. responder erro com mensagem clara e sem vazar segredo

## 2.3 Query e persistencia

- Evitar query sem filtro de tenant em tabelas de dominio.
- Para escrita concorrente sensivel (ex: estoque), usar lock (`with_for_update`) quando necessario.
- Avaliar indice ao criar novo padrao de filtro recorrente.

## 2.4 Migracoes

- Toda alteracao de schema deve incluir migration Alembic.
- Nome da migration em ingles e relacionado ao objetivo.
- Mudancas destrutivas devem considerar estrategia de compatibilidade.

## 2.5 Logs e erros

- Logs estruturados para request ja sao padrao; manter `request_id`.
- Erros devem ser explicitos para operacao, sem expor stack trace ao cliente.

## 3. Frontend Standards

## 3.1 Organizacao de pagina

Padrao esperado em pagina de portal/admin:

1. `useAdminGuard` ou `useSuperAdminGuard`
2. composicao com `AdminSidebar` e `ProfileBadge`
3. fetch por `adminFetch`/`adminUpload`
4. estados explicitamente tratados:
   - loading
   - erro
   - vazio
   - sucesso

## 3.2 Camada de acesso HTTP

- Nao chamar backend autenticado direto nas paginas.
- Sempre passar por `/api/admin/*` via `adminFetch`.
- Chamadas publicas podem usar `api(...)` quando apropriado.

## 3.3 Controle de modulo no front

- Para funcionalidades condicionadas a plano/permissao:
  - usar `useTenantModules`
  - aplicar `hasModule`/`hasModuleAction`
- Menu deve refletir disponibilidade do modulo.

## 3.4 Formularios

Padrao minimo:

- estado local tipado
- validacao antes de submit
- bloqueio de botao durante submit
- feedback de erro funcional e claro

## 3.5 UI e estilo

- Preferir componentes reutilizaveis para blocos repetidos.
- Centralizar tokens visuais (cores, espacos, tipografia).
- Garantir responsividade em mobile e desktop.

## 4. Nomenclatura e Convencoes

## 4.1 Backend

- funcoes auxiliares internas: prefixo `_`
- enums para estado controlado
- nomes de campos coerentes entre model e schema

## 4.2 Frontend

- componentes em PascalCase
- hooks em camelCase com prefixo `use`
- tipos compartilhados em `types.ts` quando forem usados em multiplas paginas

## 5. Seguranca de Desenvolvimento

- Nunca commitar segredo.
- Nao logar token, senha, chave privada ou payload sensivel integral.
- Validar MIME e assinatura de arquivo em upload.
- Verificar autorizacao em backend mesmo que front esconda tela/botao.

## 6. Performance de Desenvolvimento

- Evitar loops de requsicao em `useEffect`.
- Evitar payloads gigantes em uma unica resposta sem paginacao.
- Em backend, preferir queries focadas e paginadas.
- Medir antes de otimizar, mas nao ignorar hot paths conhecidos (checkout, insights, mensagens).

## 7. Qualidade e Entrega

## 7.1 Checklist de Done

- [ ] regra de negocio implementada no lugar correto
- [ ] tenancy preservada
- [ ] auth/permissao aplicada
- [ ] migration criada quando necessario
- [ ] frontend atualizado sem bypass de proxy auth
- [ ] docs atualizadas
- [ ] build/lint passando

## 7.2 Revisao de PR

Foco obrigatorio:

- regressao de seguranca
- regressao funcional
- impacto de performance
- impacto de dados/migracao
- clareza da documentacao

## 8. Padrao Especifico do Front (Solicitacao de Negocio)

Para manter padrao visual e de implementacao no front:

1. toda tela de portal deve seguir mesma espinha dorsal (`AdminSidebar`, topo com titulo + `ProfileBadge`)
2. todas as acoes de escrita devem exibir estado de processamento
3. todas as mensagens de erro devem ser legiveis para usuario final
4. todos os modulos novos devem prever estado "modulo bloqueado"
5. toda feature nova de portal deve ter comportamento funcional em mobile e desktop
