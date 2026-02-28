# Identidade Visual Rokin

Este documento contém as diretrizes visuais oficiais da marca **Rokin**. Qualquer agente de IA ou desenvolvedor deve utilizar essas referências como fonte de verdade ao criar, estilizar ou refatorar componentes visuais no projeto (especialmente no frontend com Tailwind CSS).

## 1. Paleta de Cores

As cores abaixo devem ser mapeadas nas configurações de estilo do projeto (ex: `tailwind.config.ts` ou arquivos de tema) usando nomes semânticos apropriados.

| Nome da Cor         | HEX       | RGB           | Uso Sugerido / Semântica |
|---------------------|-----------|---------------|--------------------------|
| **Electric Indigo** | `#6320EE` | (99, 32, 238)| Cor Primária, Ações principais, Botões de destaque, Marcações ativas. |
| **Medium Slate Blue**| `#8075FF` | (128, 117, 255)| Cor Secundária / Variante clara, Hover states de botões primários, Acentos e detalhes suaves. |
| **Raisin Black**    | `#211A1D` | (33, 26, 29)  | Texto principal, Títulos escuros, Fundos escuros invertidos, Contraste alto. |
| **Magnolia**        | `#F8F0FB` | (248, 240, 251)| Backgrounds claros, Cards, Superfícies de base, Textos sobre fundos escuros. |

## 2. Tipografia

O projeto utiliza duas famílias tipográficas principais para garantir a hierarquia de informações correta.

### 2.1. Tipografia Principal: **Anta**
- **Uso:** Ideal para títulos de maior destaque, chamadas fortes, números expressivos (como nos dashboards) ou logotipos.
- **Variações:** (Consultar fontes importadas no projeto, geralmente usada em peso único ou para display).

### 2.2. Tipografia de Apoio: **Space Grotesk**
- **Uso:** Textos de corpo, subtítulos, labels, botões e dados analíticos. Possui ótima legibilidade para números em tabelas e dashboards.
- **Pesos Disponíveis:** Light (300), Regular (400), Medium (500), Semibold (600), Bold (700).

---

## Diretrizes de Implementação para a IA (AI Instructions)

Ao atuar no frontend (ex: React / Tailwind):
1. **NUNCA** invente novas cores hexadecimais (ex: `#5A18D0`) para tentar se aproximar da paleta oficial. Utilize estritamente os valores fornecidos ou a variável Tailwind já configurada com esses hexadecimais.
2. **Textos Escuros:** Prefira usar o *Raisin Black* (`#211A1D`) ao invés do preto absoluto (`#000000`) para suavizar o contraste visual, mantendo a elegância.
3. **Backgrounds Claros:** Sempre que possível, utilize *Magnolia* (`#F8F0FB`) em vez de branco puro (`#FFFFFF`) ou cinza genérico para backgrounds das páginas e containers leves.
4. **Fontes:** Assegure-se de que as classes como `font-anta` e `font-space` estejam sendo aplicadas corretamente conforme a hierarquia. Se não estiverem no `tailwind.config.ts`, instrua a criação ou ajuste do mesmo.
5. **Formas (Border Radius):** A identidade da Rokin valoriza bordas mais amigáveis e curvas (como visto nos blocos de cor da apresentação). Prefira `rounded-lg`, `rounded-xl` ou `rounded-2xl` em botões e cards, evitando bordas retas (ex: `rounded-none`), salvo exceções estruturais específicas.