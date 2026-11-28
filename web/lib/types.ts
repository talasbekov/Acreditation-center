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
