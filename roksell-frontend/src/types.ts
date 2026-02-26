export type Category = { id: string; store_id?: string; name: string; is_active: boolean; display_order: number };
export type Product = {
  id: string;
  store_id?: string;
  name: string;
  description?: string;
  price_cents: number;
  is_active: boolean;
  is_custom?: boolean;
  additionals_enabled?: boolean;
  additional_ids?: string[];
  block_sale?: boolean;
  availability_status?: "available" | "order" | "unavailable";
  image_url?: string;
  video_url?: string;
  category_id?: string;
  display_order: number;
};
export type Additional = {
  id: string;
  store_id?: string;
  name: string;
  description?: string;
  price_cents: number;
  is_active: boolean;
  display_order: number;
};
export type OrderSummary = { order_id: string; total_cents: number; tracking_token?: string };

export type Campaign = {
  id: string;
  name: string;
  type: "order_percent" | "shipping_percent" | "category_percent" | "rule";
  value_percent: number;
  coupon_code?: string | null;
  category_id?: string | null;
  min_order_cents?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  is_active: boolean;
  usage_limit?: number | null;
  usage_count: number;
  apply_mode?: "first" | "stack" | null;
  priority?: number | null;
  rule_config?: Record<string, unknown> | null;
  store_ids?: string[] | null;
  banner_enabled: boolean;
  banner_position?: "top" | "between" | null;
  banner_popup: boolean;
  banner_image_url?: string | null;
  banner_link_url?: string | null;
  created_at: string;
};

export type CampaignBanner = {
  id: string;
  name: string;
  banner_image_url?: string | null;
  banner_link_url?: string | null;
  banner_position?: "top" | "between" | null;
  banner_popup?: boolean | null;
  starts_at?: string | null;
  ends_at?: string | null;
  created_at: string;
};

export type PaymentMethod = "pix" | "cash";

export type OperatingHoursDay = {
  day: number;
  enabled: boolean;
  open?: string | null;
  close?: string | null;
};

export type Catalog = {
  categories: Category[];
  products: Product[];
  additionals?: Additional[];
  campaign_banners?: CampaignBanner[];
  cover_image_url?: string | null;
  operating_hours?: OperatingHoursDay[];
  is_open?: boolean | null;
  sla_minutes?: number | null;
  delivery_enabled?: boolean | null;
  whatsapp_contact_phone?: string | null;
  payment_methods?: PaymentMethod[];
  selected_store_id?: string | null;
  selected_store_slug?: string | null;
  selected_store_name?: string | null;
};

export type Store = {
  id: string;
  name: string;
  slug?: string;
  timezone?: string;
  lat: number;
  lon: number;
  is_active: boolean;
  is_delivery: boolean;
  allow_preorder_when_closed?: boolean;
  closed_dates?: string[] | null;
  operating_hours?: OperatingHoursDay[] | null;
  postal_code?: string | null;
  street?: string | null;
  number?: string | null;
  district?: string | null;
  city?: string | null;
  state?: string | null;
  complement?: string | null;
  reference?: string | null;
  phone?: string | null;
  sla_minutes?: number;
  cover_image_url?: string | null;
  whatsapp_contact_phone?: string | null;
  payment_methods?: PaymentMethod[];
  order_statuses?: string[];
  order_status_canceled_color?: string | null;
  order_status_colors?: Record<string, string> | null;
  order_final_statuses?: string[];
  shipping_method?: "distance" | "district" | null;
  shipping_fixed_fee_cents?: number;
};

export type StoreInventoryItem = {
  product_id: string;
  store_id: string;
  quantity: number;
  product_name?: string;
};
