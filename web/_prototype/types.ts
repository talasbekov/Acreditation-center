export type Role = "superadmin" | "superoperator" | "user" | "operator";
export type SubjectType = "user" | "operator";

export interface AuthUser {
  id: string;
  full_name: string;
  login: string;
}

export interface Session {
  token: string;
  role: Role;
  typ: SubjectType;
  user: AuthUser;
}

export interface EventItem {
  id: string;
  code: string;
  name_ru: string;
  name_kz: string;
  name_en: string;
  city: string;
  start_date: string;
  end_date: string;
  participant_count: number;
  is_archived: boolean;
  created_at: string;
}

export interface Operator {
  id: string;
  full_name: string;
  login: string;
  phone?: string;
  organization?: string;
  role: string;
  is_active: boolean;
  events: string[];
}

export interface Participant {
  id: string;
  event_id: string;
  last_name: string;
  first_name: string;
  middle_name?: string;
  last_name_en?: string;
  first_name_en?: string;
  iin?: string;
  birth_date: string;
  gender: "male" | "female";
  citizenship: string;
  position?: string;
  doc_type: string;
  doc_series?: string;
  doc_number: string;
  doc_issued_date: string;
  doc_expiry_date: string;
  photo_url: string;
  doc_scan_url: string;
  doc_scan_status: string;
  visit_objects?: string;
  category?: string;
  is_exported: boolean;
  access_status: "yes" | "no" | "none";
  /** null = бейдж ни разу не печатался; дата перезаписывается при перепечатке */
  badge_printed_at: string | null;
  custom_field_values: Record<string, string>;
  source: string;
  created_at: string;
}

/** Разметка бейджа: размеры в мм, положение ФИО — в долях карточки. */
export interface BadgeLayout {
  badge: { width_mm: number; height_mm: number; dpi: number };
  photo: {
    enabled: boolean;
    x_mm: number;
    y_mm: number;
    width_mm: number;
    height_mm: number;
    corner_radius_mm: number;
    border_mm: number;
    focus_y: number;
    placeholder: boolean;
  };
  name: {
    source: "ru" | "en";
    y_fraction: number;
    x_start_fraction: number;
    x_end_fraction: number;
    max_font_pt: number;
    min_font_pt: number;
    wrap: boolean;
    max_lines: number;
    line_spacing: number;
    color: string;
  };
}

export interface BadgeTemplate {
  id: string;
  event_id: string;
  /** true = свой шаблон не заводили, отдана разметка по умолчанию */
  is_default: boolean;
  background_url: string;
  layout: BadgeLayout;
  updated_at: string;
}

export interface JobWarning {
  participant_id: string;
  message: string;
}

export interface JobItem {
  id: string;
  type: string;
  status: "pending" | "processing" | "completed" | "failed";
  result?: {
    download_url?: string;
    badge_count?: number;
    warnings?: JobWarning[];
  };
  created_at: string;
  completed_at?: string;
}

export interface ExportItem {
  id: string;
  event_id: string;
  status: "created" | "executed";
  participant_count: number;
  created_by: string;
  created_at: string;
  executed_at: string | null;
  granted?: number;
  denied?: number;
}

export interface CustomField {
  id: string;
  event_id: string;
  field_name: string;
  field_type: "text" | "number" | "date" | "select";
  is_required: boolean;
  options: string[] | null;
  sort_order: number;
}

export interface RegistrationLink {
  id: string;
  event_id: string;
  token: string;
  link_type: "single" | "multi";
  is_used: boolean;
  is_active: boolean;
  url: string;
  created_at: string;
}

export interface ApiToken {
  id: string;
  event_id: string;
  name: string;
  token_mask: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  actor_type: string;
  actor_id: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown> | null;
  ip_address: string;
  created_at: string;
}

export interface Pagination {
  page: number;
  per_page: number;
  total: number;
}

export interface ApiError {
  error: string;
  message?: string;
  details?: { field: string; message: string }[];
  /** 422 access_not_granted: кому нельзя печатать бейдж */
  participant_ids?: string[];
}
