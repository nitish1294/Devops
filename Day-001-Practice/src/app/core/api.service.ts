import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  Activity, Application, Board, BulkStageResult, Candidate, DashboardStats, Department,
  EmailPreview, EmailTemplate, Interview, Job, JobStatus, MailStatus, Note, Offer,
  OfferStatus, Page, Recommendation, Resume, ResumeHit, Role, Scorecard, Stage, User,
} from './models';

/** Every server call in the app goes through here. One place to change a route. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private base = environment.apiUrl;

  private params(source: Record<string, unknown>): HttpParams {
    let p = new HttpParams();
    for (const [key, value] of Object.entries(source)) {
      if (value !== null && value !== undefined && value !== '') {
        p = p.set(key, String(value));
      }
    }
    return p;
  }

  // ---- people ----
  users(query: { q?: string; role?: Role; is_active?: boolean; page?: number; page_size?: number } = {}) {
    return this.http.get<Page<User>>(`${this.base}/users`, { params: this.params(query) });
  }
  createUser(body: Partial<User> & { password: string }) {
    return this.http.post<User>(`${this.base}/users`, body);
  }
  updateUser(id: number, body: Partial<User>) {
    return this.http.patch<User>(`${this.base}/users/${id}`, body);
  }
  deactivateUser(id: number) {
    return this.http.delete<{ detail: string }>(`${this.base}/users/${id}`);
  }
  departments(): Observable<Department[]> {
    return this.http.get<Department[]>(`${this.base}/departments`);
  }
  createDepartment(body: { name: string; location?: string }) {
    return this.http.post<Department>(`${this.base}/departments`, body);
  }

  // ---- requisitions ----
  jobs(query: { q?: string; status?: JobStatus; department_id?: number; page?: number; page_size?: number } = {}) {
    return this.http.get<Page<Job>>(`${this.base}/jobs`, { params: this.params(query) });
  }
  job(id: number) {
    return this.http.get<Job>(`${this.base}/jobs/${id}`);
  }
  createJob(body: Partial<Job>) {
    return this.http.post<Job>(`${this.base}/jobs`, body);
  }
  updateJob(id: number, body: Partial<Job>) {
    return this.http.patch<Job>(`${this.base}/jobs/${id}`, body);
  }
  closeJob(id: number) {
    return this.http.delete<{ detail: string }>(`${this.base}/jobs/${id}`);
  }

  // ---- candidates ----
  candidates(query: { q?: string; skill?: string; source?: string; min_experience?: number; page?: number; page_size?: number } = {}) {
    return this.http.get<Page<Candidate>>(`${this.base}/candidates`, { params: this.params(query) });
  }
  candidate(id: number) {
    return this.http.get<Candidate>(`${this.base}/candidates/${id}`);
  }
  createCandidate(body: Partial<Candidate>) {
    return this.http.post<Candidate>(`${this.base}/candidates`, body);
  }
  updateCandidate(id: number, body: Partial<Candidate>) {
    return this.http.patch<Candidate>(`${this.base}/candidates/${id}`, body);
  }
  uploadResume(id: number, file: File) {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.http.post<Resume>(`${this.base}/candidates/${id}/resume`, form);
  }
  resume(id: number) {
    return this.http.get<Resume>(`${this.base}/candidates/${id}/resume`);
  }
  notes(candidateId: number) {
    return this.http.get<Note[]>(`${this.base}/candidates/${candidateId}/notes`);
  }
  addNote(candidateId: number, body: string) {
    return this.http.post<Note>(`${this.base}/candidates/${candidateId}/notes`, { body });
  }
  deleteNote(noteId: string) {
    return this.http.delete<{ detail: string }>(`${this.base}/candidates/notes/${noteId}`);
  }
  searchResumes(term: string) {
    return this.http.get<ResumeHit[]>(`${this.base}/candidates/search/resumes`, {
      params: this.params({ term }),
    });
  }

  // ---- pipeline ----
  applications(query: { job_id?: number; candidate_id?: number; stage?: Stage; q?: string; page?: number; page_size?: number } = {}) {
    return this.http.get<Page<Application>>(`${this.base}/applications`, { params: this.params(query) });
  }
  application(id: number) {
    return this.http.get<Application>(`${this.base}/applications/${id}`);
  }
  board(jobId?: number | null) {
    return this.http.get<Board>(`${this.base}/applications/board`, {
      params: this.params({ job_id: jobId ?? '' }),
    });
  }
  createApplication(body: { job_id: number; candidate_id: number; stage?: Stage }) {
    return this.http.post<Application>(`${this.base}/applications`, body);
  }
  moveStage(id: number, body: { to_stage: Stage; note?: string; rejection_reason?: string; board_position?: number }) {
    return this.http.post<Application>(`${this.base}/applications/${id}/stage`, body);
  }
  withdrawApplication(id: number) {
    return this.http.delete<{ detail: string }>(`${this.base}/applications/${id}`);
  }
  scorecards(applicationId: number) {
    return this.http.get<Scorecard[]>(`${this.base}/applications/${applicationId}/scorecards`);
  }

  // ---- interviews ----
  interviews(query: { application_id?: number; panelist_id?: number; status?: string; upcoming_only?: boolean; page?: number; page_size?: number } = {}) {
    return this.http.get<Page<Interview>>(`${this.base}/interviews`, { params: this.params(query) });
  }
  myInterviews() {
    return this.http.get<Interview[]>(`${this.base}/interviews/my`);
  }
  scheduleInterview(body: {
    application_id: number; round_name: string; scheduled_at: string;
    duration_minutes: number; mode: string; location_or_link?: string; panelist_ids: number[];
  }) {
    return this.http.post<Interview>(`${this.base}/interviews`, body);
  }
  updateInterview(id: number, body: Record<string, unknown>) {
    return this.http.patch<Interview>(`${this.base}/interviews/${id}`, body);
  }
  submitFeedback(id: number, body: {
    overall_rating: number; recommendation: Recommendation; feedback_summary?: string;
    criteria: Record<string, number>; strengths: string[]; concerns: string[];
  }) {
    return this.http.post<Scorecard>(`${this.base}/interviews/${id}/feedback`, body);
  }
  cancelInterview(id: number) {
    return this.http.post<{ detail: string }>(`${this.base}/interviews/${id}/cancel`, {});
  }

  // ---- offers ----
  offers(query: { status?: OfferStatus; application_id?: number; page?: number; page_size?: number } = {}) {
    return this.http.get<Page<Offer>>(`${this.base}/offers`, { params: this.params(query) });
  }
  createOffer(body: Partial<Offer> & { application_id: number; designation: string; annual_ctc: number }) {
    return this.http.post<Offer>(`${this.base}/offers`, body);
  }
  updateOffer(id: number, body: Partial<Offer>) {
    return this.http.patch<Offer>(`${this.base}/offers/${id}`, body);
  }
  setOfferStatus(id: number, status: OfferStatus, notes?: string) {
    return this.http.post<Offer>(`${this.base}/offers/${id}/status`, { status, notes });
  }
  deleteOffer(id: number) {
    return this.http.delete<{ detail: string }>(`${this.base}/offers/${id}`);
  }

  // ---- insights & comms ----
  dashboard() {
    return this.http.get<DashboardStats>(`${this.base}/dashboard`);
  }
  activity(query: { entity_type?: string; entity_id?: number; limit?: number } = {}) {
    return this.http.get<Activity[]>(`${this.base}/activity`, { params: this.params(query) });
  }
  templates() {
    return this.http.get<EmailTemplate[]>(`${this.base}/comms/templates`);
  }
  saveTemplate(body: { code: string; name: string; subject: string; body: string }) {
    return this.http.put<EmailTemplate>(`${this.base}/comms/templates`, body);
  }
  sendEmail(body: { template_code: string; candidate_id: number; context: Record<string, unknown> }) {
    return this.http.post<Record<string, unknown>>(`${this.base}/comms/send`, body);
  }
  outbox(limit = 50, status?: string) {
    return this.http.get<Record<string, unknown>[]>(`${this.base}/comms/outbox`, {
      params: this.params({ limit, status }),
    });
  }
  mailStatus() {
    return this.http.get<MailStatus>(`${this.base}/comms/mail-status`);
  }
  previewEmail(body: {
    template_code: string;
    candidate_id: number;
    context: Record<string, unknown>;
  }) {
    return this.http.post<EmailPreview>(`${this.base}/comms/preview`, body);
  }
  flushOutbox() {
    return this.http.post<Record<string, unknown>>(`${this.base}/comms/outbox/flush`, {});
  }
  retryMessage(id: string) {
    return this.http.post<Record<string, unknown>>(
      `${this.base}/comms/outbox/${id}/retry`,
      {},
    );
  }

  // ---- bulk pipeline ----
  bulkMoveStage(body: {
    application_ids: number[];
    to_stage: Stage;
    note?: string;
    rejection_reason?: string;
  }) {
    return this.http.post<BulkStageResult>(`${this.base}/applications/bulk/stage`, body);
  }

  // ---- files ----
  // Blob responses, because these are downloads rather than JSON payloads.
  resumeFile(candidateId: number) {
    return this.http.get(`${this.base}/candidates/${candidateId}/resume/download`, {
      responseType: 'blob',
      observe: 'response',
    });
  }
  offerLetter(offerId: number) {
    return this.http.get(`${this.base}/offers/${offerId}/letter.pdf`, {
      responseType: 'blob',
      observe: 'response',
    });
  }
  interviewInvite(interviewId: number) {
    return this.http.get(`${this.base}/interviews/${interviewId}/invite.ics`, {
      responseType: 'blob',
      observe: 'response',
    });
  }
  exportCandidates(query: { q?: string; source?: string; min_experience?: number } = {}) {
    return this.http.get(`${this.base}/candidates/export/csv`, {
      params: this.params(query),
      responseType: 'blob',
      observe: 'response',
    });
  }
  exportPipeline(query: { job_id?: number; stage?: Stage } = {}) {
    return this.http.get(`${this.base}/applications/export/csv`, {
      params: this.params(query),
      responseType: 'blob',
      observe: 'response',
    });
  }
}
