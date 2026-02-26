export type AdminMenuItem = {
  label: string;
  href: string;
  enabled: boolean;
  copyable?: boolean;
  showStatus?: boolean;
  moduleKey?: string;
};

export const adminMenuItems: AdminMenuItem[] = [
  { label: "Home", href: "/portal", enabled: true },
  { label: "Vitrine", href: "/vitrine/{tenant}", enabled: true, copyable: true },
  { label: "Insights", href: "/portal/insights", enabled: true, showStatus: true, moduleKey: "insights" },
  { label: "Pedidos", href: "/portal/pedidos", enabled: true },
  { label: "Mensagens", href: "/portal/mensagens", enabled: true, moduleKey: "messages" },
  { label: "Clientes", href: "/portal/clientes", enabled: true, moduleKey: "customers" },
  { label: "Produtos", href: "/portal/catalog", enabled: true, moduleKey: "products" },
  { label: "Estoque", href: "/portal/estoque", enabled: true, showStatus: true, moduleKey: "inventory" },
  { label: "Campanhas", href: "/portal/campanhas", enabled: true, showStatus: true, moduleKey: "campaigns" },
  { label: "Lojas", href: "/portal/lojas", enabled: true, showStatus: true, moduleKey: "stores" },
];

export const adminMenuWithHome = adminMenuItems.map((item, idx) =>
  idx === 0 ? { ...item, badge: "Inicio", variant: "primary" as const } : item,
);

