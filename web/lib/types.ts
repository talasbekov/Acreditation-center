/** Типы ответов Django API (eventproject/serializers, views/*_api.py). */

export interface EventBrief {
  id: number;
  name_rus: string;
  name_kaz: string;
  name_eng: string;
  event_code: string;
  city_code: string;
  city_name?: string;
  date_start: string | null;
  date_end: string | null;
  parent_id: number | null;
  is_container: boolean;
}

export type RequestStatus = "Active" | "Checking" | "Sent" | "Exported" | string;

export interface CabinetRequest {
  id: number;
  name: string;
  status: RequestStatus;
  event_id: number;
  date_created: string;
  attendee_count: number;
  returned_count: number;
}

export interface Cabinet {
  events: EventBrief[];
  requests: CabinetRequest[];
}

export type AttendeeStatus = "draft" | "submitted" | "in_review" | "ready" | "exported";

/** Полный участник (AttendeeSerializer): поля как в модели старой АЦ. */
export interface Attendee {
  id: number;
  surname: string;
  firstname: string;
  patronymic: string | null;
  birthDate: string;
  post: string;
  countryId: string;
  docTypeId: string;
  docSeries: string;
  iin: string | null;
  docNumber: string;
  docBegin: string;
  docEnd: string;
  docIssue: string;
  photo: string | null;
  docScan: string | null;
  sexId: string;
  visitObjects: string;
  transcription: string;
  stickId: string;
  request: number;
  category: number | null;
  dateEnd: string | null;
  is_resident: boolean;
  status: AttendeeStatus;
  dateAdd: string;
  review_comment: string;
  return_count: number;
  access_status?: "yes" | "no" | "none";
  access_decided_at?: string | null;
  badge_printed_at?: string | null;
  custom_field_values?: Record<string, string>;
}

export interface RequestDetail {
  id: number;
  name: string;
  status: RequestStatus;
  date_created: string;
  registration_time: string;
  event: EventBrief;
  created_by: { id: number; username: string; full_name: string };
  can_add: boolean;
  can_preview: boolean;
  attendees: Attendee[];
  already_sent?: boolean;
}

export interface SendProblem {
  attendee_id: number;
  name: string;
  codes: string[];
}

export interface DirectoryRow {
  code: string;
  name: string;
}

export interface Directories {
  sexes: DirectoryRow[];
  document_types: DirectoryRow[];
  categories: DirectoryRow[];
  countries: DirectoryRow[];
}

export interface City {
  code: string;
  name_rus: string;
  name_kaz: string;
  name_eng: string;
}

export interface OperatorRow {
  id: number;
  username: string;
  last_name: string;
  first_name: string;
  patronymic: string;
  email: string;
  phone_number: string;
  workplace: string;
  role: string;
  is_active: boolean;
  email_status: string;
  event_ids?: number[];
}

export interface AdminRequestRow {
  id: number;
  name: string;
  status: string;
  date_created: string;
  registration_time: string;
  event_id: number;
  created_by: string;
}

export interface AdminHome {
  events: EventBrief[];
  operators: OperatorRow[];
  cities: City[];
}

export interface AdminEventCard {
  event: EventBrief;
  city_name: string;
  operators: OperatorRow[];
  other_operators: OperatorRow[];
  requests: AdminRequestRow[];
  active_requests: AdminRequestRow[];
  unexported: number;
  archive: { name: string; size_mb: number; modified: string } | null;
  events: EventBrief[];
}

export interface AdminOperatorCard {
  operator: OperatorRow;
  events: EventBrief[];
  requests: AdminRequestRow[];
}

export interface DashboardFlag {
  key: string;
  label: string;
  items: { id: number; name: string }[];
  shown: number;
  total: number;
  overflow: boolean;
}

export interface ExportPackage {
  package_id: string;
  category: string | null;
  exported_before: string;
  attendee_count: number;
  archive_name: string;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  can_redownload: boolean;
  executed_at?: string | null;
  denied_count?: number;
}

export interface Dashboard {
  event: EventBrief;
  total: number;
  ready: number;
  review: number;
  submitted: number;
  in_review: number;
  draft: number;
  exported: number;
  all_ready: boolean;
  flags: DashboardFlag[];
  flags_total: number;
  categories: { id: number; name: string; status: string }[];
  packages: ExportPackage[];
  access?: Record<string, number>;
}

export interface ReviewItem {
  id: number;
  surname: string;
  firstname: string;
  patronymic: string;
  status: string;
  transcription: string;
  birthDate: string | null;
  country: string;
  doc_type: string;
  docSeries: string;
  docNumber: string;
  docEnd: string | null;
  post: string;
  visitObjects: string;
  photo: string | null;
  docScan: string | null;
  request_name: string;
  operator: string;
}

export interface ReviewQueue {
  event: EventBrief;
  items: ReviewItem[];
  total: number;
  overflow: boolean;
  summary: Record<string, number>;
  max_reason: number;
}

// ── Второй этап ──

export interface CustomField {
  id: number;
  field_name: string;
  field_type: "text" | "number" | "date" | "select";
  is_required: boolean;
  options: string[];
  sort_order: number;
}

export interface RegistrationLinkRow {
  id: number;
  token: string;
  url: string;
  link_type: "single" | "multi";
  is_used: boolean;
  is_active: boolean;
  is_available: boolean;
  used_count: number;
  request_id: number;
  created_at: string;
  created_by: string;
}

export interface ApiTokenRow {
  id: number;
  name: string;
  token_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  request_id: number;
  endpoint: string;
  created_by: string;
  token?: string;
}

export interface BadgeLayout {
  badge: { width_mm: number; height_mm: number; dpi: number };
  photo: { x_mm: number; y_mm: number; width_mm: number; height_mm: number; radius_mm: number };
  name: { x0: number; x1: number; y: number; line_height: number; max_pt: number; min_pt: number; color: string };
}

export interface BadgeTemplateInfo {
  event_id: number;
  is_default: boolean;
  has_background: boolean;
  layout: BadgeLayout;
  name_source: "ru" | "latin";
  updated_at: string | null;
  font_ok: boolean;
}

export interface BadgeCandidate {
  id: number;
  name: string;
  transcription: string;
  request_name: string;
  status: string;
  access_status: "yes" | "no" | "none";
  badge_printed_at: string | null;
  has_photo: boolean;
}

export interface JobInfo {
  id: number;
  type: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  result: { badge_count: number; warnings: { id: number | null; name: string; problem: string }[]; file_name: string } | null;
  error: string;
  created_at: string;
  completed_at: string | null;
  has_file: boolean;
}
