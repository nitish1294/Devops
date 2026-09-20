export type Role = 'admin' | 'hr_manager' | 'recruiter' | 'hiring_manager' | 'interviewer';
export type JobStatus = 'draft' | 'open' | 'on_hold' | 'closed' | 'filled';
export type EmploymentType = 'full_time' | 'part_time' | 'contract' | 'intern';
export type Stage =
  | 'sourced' | 'screening' | 'interview' | 'assessment' | 'offer' | 'hired' | 'rejected';
export type InterviewMode = 'onsite' | 'video' | 'phone';
export type InterviewStatus = 'scheduled' | 'completed' | 'cancelled' | 'no_show';
export type OfferStatus = 'draft' | 'sent' | 'accepted' | 'declined' | 'withdrawn';
export type Recommendation = 'strong_yes' | 'yes' | 'no' | 'strong_no';

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Department {
  id: number;
  name: string;
  location?: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  title?: string | null;
  phone?: string | null;
  is_active: boolean;
  created_at: string;
  department_id?: number | null;
  department?: Department | null;
}

export interface Job {
  id: number;
  code: string;
  title: string;
  description?: string | null;
  location?: string | null;
  employment_type: EmploymentType;
  status: JobStatus;
  openings: number;
  experience_min?: number | null;
  experience_max?: number | null;
  salary_min?: number | null;
  salary_max?: number | null;
  skills?: string | null;
  target_close_date?: string | null;
  department_id?: number | null;
  hiring_manager_id?: number | null;
  recruiter_id?: number | null;
  department?: Department | null;
  hiring_manager?: User | null;
  recruiter?: User | null;
  applicant_count: number;
  hired_count: number;
  created_at: string;
}

export interface Candidate {
  id: number;
  full_name: string;
  email: string;
  phone?: string | null;
  location?: string | null;
  current_company?: string | null;
  current_title?: string | null;
  total_experience?: number | null;
  current_ctc?: number | null;
  expected_ctc?: number | null;
  notice_period_days?: number | null;
  source?: string | null;
  referred_by?: string | null;
  skills?: string | null;
  linkedin_url?: string | null;
  resume_doc_id?: string | null;
  open_applications: number;
  created_at: string;
}

export interface JobBrief {
  id: number;
  code: string;
  title: string;
  location?: string | null;
}

export interface StageEvent {
  id: number;
  from_stage?: string | null;
  to_stage: string;
  note?: string | null;
  created_at: string;
  moved_by?: User | null;
}

export interface Application {
  id: number;
  stage: Stage;
  board_position: number;
  match_score?: number | null;
  rejection_reason?: string | null;
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
  job: JobBrief;
  candidate: Candidate;
  owner?: User | null;
  interview_count: number;
  days_in_stage: number;
  stage_events?: StageEvent[];
}

export interface BoardColumn {
  stage: Stage;
  label: string;
  count: number;
  items: Application[];
}

export interface Board {
  job_id?: number | null;
  columns: BoardColumn[];
}

export interface CandidateBrief {
  id: number;
  full_name: string;
  email: string;
}

export interface Interview {
  id: number;
  application_id: number;
  round_name: string;
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode;
  location_or_link?: string | null;
  status: InterviewStatus;
  overall_rating?: number | null;
  recommendation?: string | null;
  feedback_summary?: string | null;
  panelists: User[];
  candidate?: CandidateBrief | null;
  job_title?: string | null;
}

export interface Offer {
  id: number;
  application_id: number;
  designation: string;
  annual_ctc: number;
  fixed_component?: number | null;
  variable_component?: number | null;
  joining_bonus?: number | null;
  joining_date?: string | null;
  valid_till?: string | null;
  status: OfferStatus;
  notes?: string | null;
  created_at: string;
  candidate?: CandidateBrief | null;
  job_title?: string | null;
}

export interface ParsedResume {
  emails: string[];
  phones: string[];
  skills: string[];
  education: string[];
  years_experience?: number | null;
  word_count: number;
}

export interface Resume {
  id: string;
  candidate_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
  parsed: ParsedResume;
  raw_text_preview: string;
}

export interface Note {
  id: string;
  entity_type: string;
  entity_id: number;
  body: string;
  author_id: number;
  author_name: string;
  created_at: string;
}

export interface Activity {
  id: string;
  action: string;
  entity_type: string;
  entity_id?: number | null;
  summary: string;
  actor_id?: number | null;
  actor_name?: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Scorecard {
  id: string;
  application_id: number;
  interview_id?: number | null;
  criteria: Record<string, number>;
  strengths: string[];
  concerns: string[];
  overall_rating?: number | null;
  recommendation?: string | null;
  submitted_by?: number | null;
  submitted_at: string;
}

export interface EmailTemplate {
  /** Every $name the subject or body refers to, computed server-side. */
  placeholders?: string[];
  id: string;
  code: string;
  name: string;
  subject: string;
  body: string;
  updated_at: string;
}

export interface DashboardStats {
  open_jobs: number;
  total_jobs: number;
  total_candidates: number;
  active_applications: number;
  interviews_next_7_days: number;
  offers_pending: number;
  hires_this_month: number;
  avg_time_to_hire_days?: number | null;
  offer_acceptance_rate?: number | null;
  pipeline_by_stage: Record<string, number>;
  applications_by_source: Record<string, number>;
  hiring_trend: { month: string; applications: number; hires: number }[];
  top_jobs: { code: string; title: string; applications: number }[];
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface BulkStageResult {
  moved: number;
  skipped: { application_id: number; candidate?: string; reason: string }[];
}

export interface MailStatus {
  smtp_configured: boolean;
  smtp_host: string | null;
  worker_enabled: boolean;
  delivery: string;
  counts: { queued: number; sent: number; failed: number };
}

export interface EmailPreview {
  to_email: string;
  subject: string;
  body: string;
  unresolved: string[];
}

export interface ResumeHit {
  id: string;
  candidate_id: number;
  filename: string;
  score: number;
  matched_terms: string[];
  raw_text_preview: string;
  parsed: { skills: string[]; years_experience: number | null; education: string[] };
}

export const STAGES: { value: Stage; label: string }[] = [
  { value: 'sourced', label: 'Sourced' },
  { value: 'screening', label: 'Screening' },
  { value: 'interview', label: 'Interview' },
  { value: 'assessment', label: 'Assessment' },
  { value: 'offer', label: 'Offer' },
  { value: 'hired', label: 'Hired' },
  { value: 'rejected', label: 'Rejected' },
];

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrator',
  hr_manager: 'HR manager',
  recruiter: 'Recruiter',
  hiring_manager: 'Hiring manager',
  interviewer: 'Interviewer',
};

export const JOB_STATUS_LABELS: Record<JobStatus, string> = {
  draft: 'Draft',
  open: 'Open',
  on_hold: 'On hold',
  closed: 'Closed',
  filled: 'Filled',
};

export const OFFER_STATUS_LABELS: Record<OfferStatus, string> = {
  draft: 'Draft',
  sent: 'Sent',
  accepted: 'Accepted',
  declined: 'Declined',
  withdrawn: 'Withdrawn',
};

export const SOURCES = ['naukri', 'linkedin', 'referral', 'careers_site', 'campus', 'agency'];
