export type AdminMenuItem = {
  label: string;
  href: string;
  enabled: boolean;
  copyable?: boolean;
  showStatus?: boolean;
  moduleKey?: string;
};

export const adminMenuItems: AdminMenuItem[] = [
  { label: "Home", href: "/roksell", enabled: true },
  { label: "Vitrine", href: "/vitrine/{tenant}", enabled: true, copyable: true },
  { label: "Insights", href: "/roksell/insights", enabled: true, showStatus: true, moduleKey: "insights" },
  { label: "Pedidos", href: "/roksell/pedidos", enabled: true },
  { label: "Mensagens", href: "/roksell/mensagens", enabled: true, moduleKey: "messages" },
  { label: "Clientes", href: "/roksell/clientes", enabled: true, moduleKey: "customers" },
  { label: "Produtos", href: "/roksell/produtos", enabled: true, moduleKey: "products" },
  { label: "Estoque", href: "/roksell/estoque", enabled: true, showStatus: true, moduleKey: "inventory" },
  { label: "Campanhas", href: "/roksell/campanhas", enabled: true, showStatus: true, moduleKey: "campaigns" },
  { label: "Lojas", href: "/roksell/lojas", enabled: true, showStatus: true, moduleKey: "stores" },
];

export const adminMenuWithHome = adminMenuItems.map((item, idx) =>
  idx === 0 ? { ...item, badge: "Inicio", variant: "primary" as const } : item,
);

