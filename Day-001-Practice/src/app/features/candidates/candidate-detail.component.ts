import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { saveResponse } from '../../core/download';
import { AuthService } from '../../core/auth.service';
import { ago, day, lakhs, titleCase, when } from '../../core/format';
import {
  Application, Candidate, Interview, Note, Resume, STAGES, Scorecard,
} from '../../core/models';
import { AddToPipelineDialog } from './add-to-pipeline.dialog';
import { CandidateFormDialog } from './candidate-form.dialog';

@Component({
  selector: 'app-candidate-detail',
  standalone: true,
  imports: [
    FormsModule, RouterLink, MatButtonModule, MatIconModule, MatTabsModule,
    MatFormFieldModule, MatInputModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <div class="page">
      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (candidate(); as c) {
        <div class="page-head">
          <div>
            <a routerLink="/candidates" class="small back">
              <mat-icon>arrow_back</mat-icon> All candidates
            </a>
            <h1>{{ c.full_name }}</h1>
            <p>
              {{ c.current_title || 'Role not recorded' }}
              @if (c.current_company) { at {{ c.current_company }} }
              · {{ c.location || 'Location not recorded' }}
            </p>
          </div>
          @if (canManage) {
            <div class="actions">
              <button mat-stroked-button type="button" (click)="addToPipeline(c)">
                <mat-icon>playlist_add</mat-icon>
                Add to requisition
              </button>
              <button mat-flat-button color="primary" type="button" (click)="edit(c)">
                <mat-icon>edit</mat-icon>
                Edit
              </button>
            </div>
          }
        </div>

        <div class="two-col">
          <div class="stack">
            <section class="card panel">
              <h3>Contact and package</h3>
              <dl class="pairs">
                <div><dt>Email</dt><dd>{{ c.email }}</dd></div>
                <div><dt>Phone</dt><dd>{{ c.phone || '—' }}</dd></div>
                <div><dt>Experience</dt><dd>{{ c.total_experience ?? '—' }} yrs</dd></div>
                <div><dt>Notice period</dt><dd>{{ c.notice_period_days ?? '—' }} days</dd></div>
                <div><dt>Current CTC</dt><dd>{{ money(c.current_ctc) }}</dd></div>
                <div><dt>Expected CTC</dt><dd>{{ money(c.expected_ctc) }}</dd></div>
                <div><dt>Source</dt><dd>{{ label(c.source) }}</dd></div>
                <div><dt>Referred by</dt><dd>{{ c.referred_by || '—' }}</dd></div>
              </dl>

              @if (skills().length) {
                <h3>Skills</h3>
                <div class="chips">
                  @for (s of skills(); track s) { <span class="chip">{{ s }}</span> }
                </div>
              }

              @if (c.linkedin_url) {
                <h3>Links</h3>
                <a [href]="c.linkedin_url" target="_blank" rel="noopener">LinkedIn profile</a>
              }
            </section>

            <section class="card panel">
              <h3>Resume</h3>
              @if (resume(); as r) {
                <p class="small">
                  <span class="strong">{{ r.filename }}</span>
                  <span class="muted"> · {{ kb(r.size_bytes) }} · uploaded {{ dayOf(r.uploaded_at) }}</span>
                </p>
                <dl class="pairs">
                  <div>
                    <dt>Skills found</dt>
                    <dd>{{ r.parsed.skills.length }}</dd>
                  </div>
                  <div>
                    <dt>Experience detected</dt>
                    <dd>{{ r.parsed.years_experience ?? '—' }} yrs</dd>
                  </div>
                  <div>
                    <dt>Education</dt>
                    <dd>{{ r.parsed.education.length ? upper(r.parsed.education) : '—' }}</dd>
                  </div>
                </dl>
                <p class="preview small">{{ r.raw_text_preview }}…</p>
                <button mat-stroked-button type="button" (click)="downloadResume()">
                  <mat-icon>download</mat-icon>
                  Download original
                </button>
              } @else {
                <p class="muted small">
                  No resume on file. Upload a PDF, DOCX or TXT and skills get pulled out
                  automatically.
                </p>
              }

              @if (canManage) {
                <input
                  #fileInput
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  hidden
                  (change)="upload($event)"
                />
                <button mat-stroked-button type="button" [disabled]="uploading()"
                        (click)="fileInput.click()">
                  <mat-icon>upload_file</mat-icon>
                  {{ resume() ? 'Replace resume' : 'Upload resume' }}
                </button>
                @if (uploading()) { <mat-progress-bar mode="indeterminate" /> }
              }
            </section>
          </div>

          <div class="stack">
            <mat-tab-group>
              <mat-tab label="Applications ({{ applications().length }})">
                <div class="tab-body">
                  @for (a of applications(); track a.id) {
                    <div class="app-row card">
                      <div class="app-main">
                        <a [routerLink]="['/jobs', a.job.id]" class="strong">{{ a.job.title }}</a>
                        <span class="muted small">{{ a.job.code }}</span>
                      </div>
                      <span class="pill" [class]="'stage-' + a.stage">{{ stageLabel(a.stage) }}</span>
                      <span class="small muted">
                        {{ a.match_score !== null ? a.match_score + '% match' : 'no score' }} ·
                        {{ a.interview_count }} interviews · {{ a.days_in_stage }}d in stage
                      </span>
                      @if (a.rejection_reason) {
                        <span class="small reason">{{ a.rejection_reason }}</span>
                      }
                    </div>
                  } @empty {
                    <div class="empty">
                      <span class="empty-title">Not on any requisition</span>
                      <p>Add this candidate to a requisition to start their pipeline.</p>
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Interviews ({{ interviews().length }})">
                <div class="tab-body">
                  @for (iv of interviews(); track iv.id) {
                    <div class="app-row card">
                      <div class="app-main">
                        <span class="strong">{{ iv.round_name }}</span>
                        <span class="muted small">{{ iv.job_title }}</span>
                      </div>
                      <span class="small">{{ whenOf(iv.scheduled_at) }}</span>
                      <span class="small muted">
                        {{ label(iv.mode) }} · {{ iv.duration_minutes }} min ·
                        {{ panel(iv) }}
                      </span>
                      @if (iv.overall_rating) {
                        <span class="small strong">
                          Rated {{ iv.overall_rating }}/5 · {{ label(iv.recommendation) }}
                        </span>
                      }
                      @if (iv.feedback_summary) {
                        <span class="small muted">{{ iv.feedback_summary }}</span>
                      }
                    </div>
                  } @empty {
                    <div class="empty">
                      <span class="empty-title">No interviews yet</span>
                      <p>Schedule one from the Interviews page.</p>
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Scorecards ({{ scorecards().length }})">
                <div class="tab-body">
                  @for (sc of scorecards(); track sc.id) {
                    <div class="card panel">
                      <p class="small">
                        <span class="strong">{{ label(sc.recommendation) }}</span>
                        <span class="muted"> · rated {{ sc.overall_rating ?? '—' }}/5 ·
                          {{ dayOf(sc.submitted_at) }}</span>
                      </p>
                      <ul class="criteria">
                        @for (row of criteriaOf(sc); track row.key) {
                          <li>
                            <span class="c-label">{{ label(row.key) }}</span>
                            <span class="c-bar" aria-hidden="true">
                              <span class="c-fill" [style.width.%]="row.value * 20"></span>
                            </span>
                            <span class="num small">{{ row.value }}/5</span>
                          </li>
                        }
                      </ul>
                      @if (sc.strengths.length) {
                        <p class="small"><span class="muted">Strengths: </span>{{ sc.strengths.join('; ') }}</p>
                      }
                      @if (sc.concerns.length) {
                        <p class="small"><span class="muted">Concerns: </span>{{ sc.concerns.join('; ') }}</p>
                      }
                    </div>
                  } @empty {
                    <div class="empty">
                      <span class="empty-title">No feedback submitted</span>
                      <p>Panelists submit scorecards after each round.</p>
                    </div>
                  }
                </div>
              </mat-tab>

              <mat-tab label="Notes">
                <div class="tab-body">
                  <div class="card panel">
                    <mat-form-field appearance="outline">
                      <mat-label>Add a note</mat-label>
                      <textarea matInput rows="3" [(ngModel)]="draftNote"
                                placeholder="What should the team know?"></textarea>
                    </mat-form-field>
                    <button mat-flat-button color="primary" type="button"
                            [disabled]="!draftNote.trim()" (click)="saveNote()">
                      Save note
                    </button>

                    <ul class="notes">
                      @for (n of notes(); track n.id) {
                        <li>
                          <div class="n-head small">
                            <span class="strong">{{ n.author_name }}</span>
                            <span class="muted"> · {{ agoOf(n.created_at) }}</span>
                            <button mat-icon-button type="button" class="tiny"
                                    (click)="removeNote(n)" aria-label="Delete note">
                              <mat-icon>close</mat-icon>
                            </button>
                          </div>
                          <p>{{ n.body }}</p>
                        </li>
                      } @empty {
                        <li class="muted small">No notes yet.</li>
                      }
                    </ul>
                  </div>
                </div>
              </mat-tab>
            </mat-tab-group>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .back { display: inline-flex; align-items: center; gap: 4px; color: var(--muted); }
    .back mat-icon { font-size: 15px; width: 15px; height: 15px; }
    .actions { display: flex; gap: 8px; }

    .two-col { display: grid; grid-template-columns: 340px 1fr; gap: 16px; align-items: start; }
    @media (max-width: 1080px) { .two-col { grid-template-columns: 1fr; } }
    .stack { display: grid; gap: 14px; }

    .panel { padding: 16px 18px; }
    .panel h3 { margin: 0 0 9px; font-size: 12.5px; color: var(--muted); font-weight: 600; }
    .panel h3:not(:first-child) { margin-top: 20px; }

    .pairs { margin: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 11px 14px; }
    .pairs dt { font-size: 11.5px; color: var(--muted); }
    .pairs dd { margin: 1px 0 0; font-weight: 500; font-size: 13px; word-break: break-word; }

    .chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .chip {
      background: #eef4f3; color: var(--accent-dark); border: 1px solid #cfe1de;
      border-radius: 4px; padding: 2px 7px; font-size: 12px; font-weight: 500;
    }

    .preview {
      margin: 12px 0; padding: 10px; background: #f7f9fa;
      border-radius: var(--radius); color: var(--muted);
      max-height: 108px; overflow: hidden; white-space: pre-wrap;
    }

    .tab-body { padding-top: 14px; display: grid; gap: 10px; }
    .app-row { padding: 12px 14px; display: grid; gap: 4px; }
    .app-main { display: flex; align-items: baseline; gap: 8px; }
    .app-row .pill { justify-self: start; }
    .reason { color: var(--danger); }

    .criteria { list-style: none; margin: 10px 0 12px; padding: 0; display: grid; gap: 7px; }
    .criteria li { display: grid; grid-template-columns: 130px 1fr 40px; align-items: center; gap: 9px; }
    .c-label { font-size: 12.5px; }
    .c-bar { height: 6px; background: #eceff2; border-radius: 3px; overflow: hidden; }
    .c-fill { display: block; height: 100%; background: var(--accent); }

    .notes { list-style: none; margin: 16px 0 0; padding: 0; display: grid; gap: 12px; }
    .notes li { border-top: 1px solid var(--rule); padding-top: 10px; }
    .notes p { margin: 3px 0 0; font-size: 13px; white-space: pre-wrap; }
    .n-head { display: flex; align-items: center; }
    .n-head .tiny { margin-left: auto; width: 24px; height: 24px; line-height: 24px; }
    .n-head .tiny mat-icon { font-size: 15px; width: 15px; height: 15px; }
  `],
})
export class CandidateDetailComponent implements OnInit {
  id = input.required<string>();

  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  candidate = signal<Candidate | null>(null);
  applications = signal<Application[]>([]);
  interviews = signal<Interview[]>([]);
  scorecards = signal<Scorecard[]>([]);
  notes = signal<Note[]>([]);
  resume = signal<Resume | null>(null);
  loading = signal(true);
  uploading = signal(false);
  draftNote = '';
  canManage = this.auth.can('manage_jobs');

  skills = computed(() =>
    (this.candidate()?.skills ?? '').split(',').map((s) => s.trim()).filter(Boolean),
  );

  ngOnInit(): void {
    this.refresh();
  }

  private refresh(): void {
    const candidateId = Number(this.id());
    this.loading.set(true);

    this.api.candidate(candidateId).subscribe({
      next: (c) => {
        this.candidate.set(c);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });

    this.api.applications({ candidate_id: candidateId, page_size: 100 }).subscribe((res) => {
      this.applications.set(res.items);
      this.interviews.set([]);
      this.scorecards.set([]);
      for (const app of res.items) {
        this.api
          .interviews({ application_id: app.id, page_size: 50 })
          .subscribe((ivs) => this.interviews.update((list) => [...list, ...ivs.items]));
        this.api
          .scorecards(app.id)
          .subscribe((cards) => this.scorecards.update((list) => [...list, ...cards]));
      }
    });

    this.api.notes(candidateId).subscribe((n) => this.notes.set(n));
    this.api.resume(candidateId).subscribe({
      next: (r) => this.resume.set(r),
      error: () => this.resume.set(null),
    });
  }

  edit(candidate: Candidate): void {
    this.dialog
      .open(CandidateFormDialog, { data: { candidate } })
      .afterClosed()
      .subscribe((updated) => {
        if (updated) {
          this.snack.open('Candidate updated', 'Dismiss', { duration: 3000 });
          this.refresh();
        }
      });
  }

  addToPipeline(candidate: Candidate): void {
    this.dialog
      .open(AddToPipelineDialog, { data: { candidate } })
      .afterClosed()
      .subscribe((created) => {
        if (created) {
          this.snack.open('Added to the pipeline', 'Dismiss', { duration: 3000 });
          this.refresh();
        }
      });
  }

  /** The original file, not the parsed text — that is what gets forwarded on. */
  downloadResume(): void {
    this.api.resumeFile(Number(this.id())).subscribe((res) => {
      saveResponse(res, `${this.candidate()?.full_name ?? 'candidate'} resume`);
    });
  }

  upload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.uploading.set(true);
    this.api.uploadResume(Number(this.id()), file).subscribe({
      next: (r) => {
        this.resume.set(r);
        this.uploading.set(false);
        input.value = '';
        this.snack.open(
          `Resume parsed — ${r.parsed.skills.length} skills found`,
          'Dismiss',
          { duration: 4500 },
        );
        this.refresh();
      },
      error: () => {
        this.uploading.set(false);
        input.value = '';
      },
    });
  }

  saveNote(): void {
    const body = this.draftNote.trim();
    if (!body) return;
    this.api.addNote(Number(this.id()), body).subscribe((note) => {
      this.notes.update((list) => [note, ...list]);
      this.draftNote = '';
    });
  }

  removeNote(note: Note): void {
    this.api.deleteNote(note.id).subscribe(() => {
      this.notes.update((list) => list.filter((n) => n.id !== note.id));
    });
  }

  criteriaOf(card: Scorecard): { key: string; value: number }[] {
    return Object.entries(card.criteria).map(([key, value]) => ({ key, value }));
  }

  panel(iv: Interview): string {
    return iv.panelists.length ? iv.panelists.map((p) => p.full_name).join(', ') : 'no panel set';
  }

  stageLabel(stage: Application['stage']): string {
    return STAGES.find((s) => s.value === stage)?.label ?? stage;
  }

  label(value?: string | null): string {
    return titleCase(value);
  }

  upper(values: string[]): string {
    return values.map((v) => v.toUpperCase()).join(', ');
  }

  money(value?: number | null): string {
    return lakhs(value);
  }

  kb(bytes: number): string {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  dayOf(value?: string | null): string {
    return day(value);
  }

  whenOf(value?: string | null): string {
    return when(value);
  }

  agoOf(value?: string | null): string {
    return ago(value);
  }
}
