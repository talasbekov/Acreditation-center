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
