import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { day, lakhs, titleCase } from '../../core/format';
import { Activity, Application, JOB_STATUS_LABELS, Job, STAGES } from '../../core/models';
import { AddToPipelineDialog } from '../candidates/add-to-pipeline.dialog';
import { JobFormDialog } from './job-form.dialog';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [
    RouterLink, MatButtonModule, MatIconModule, MatTabsModule,
    MatProgressBarModule, MatFormFieldModule,
  ],
  template: `
    <div class="page">
      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (job(); as j) {
        <div class="page-head">
          <div>
            <a routerLink="/jobs" class="small back">
              <mat-icon>arrow_back</mat-icon> All requisitions
            </a>
            <h1>{{ j.title }}</h1>
            <p>
              {{ j.code }} · {{ j.department?.name || 'No department' }} ·
              {{ j.location || 'Location TBD' }} · {{ label(j.employment_type) }}
            </p>
          </div>
          <div class="actions">
            @if (canManage) {
              <button mat-stroked-button type="button" (click)="addCandidate()">
                <mat-icon>person_add</mat-icon>
                Add candidate
              </button>
              <button mat-flat-button color="primary" type="button" (click)="edit(j)">
                <mat-icon>edit</mat-icon>
                Edit
              </button>
            }
          </div>
        </div>

        <div class="grid-metrics">
          <div class="card metric">
            <span class="m-label">Status</span>
            <span class="pill" [class]="statusClass(j.status)">{{ statusLabel(j.status) }}</span>
          </div>
          <div class="card metric">
            <span class="m-label">Openings</span>
            <span class="m-value num">{{ j.hired_count }} / {{ j.openings }}</span>
            <span class="muted small">filled</span>
          </div>
          <div class="card metric">
            <span class="m-label">In pipeline</span>
            <span class="m-value num">{{ activeCount() }}</span>
            <span class="muted small">{{ j.applicant_count }} total applicants</span>
          </div>
          <div class="card metric">
            <span class="m-label">Experience</span>
            <span class="m-value">{{ experience(j) }}</span>
          </div>
          <div class="card metric">
            <span class="m-label">Salary band</span>
            <span class="m-value">{{ band(j) }}</span>
          </div>
          <div class="card metric">
            <span class="m-label">Target close</span>
            <span class="m-value">{{ dayOf(j.target_close_date) }}</span>
          </div>
        </div>

        <mat-tab-group>
          <mat-tab label="Candidates ({{ applications().length }})">
            <div class="tab-body">
              @if (applications().length) {
                <div class="card">
                  <table class="data">
                    <thead>
                      <tr>
                        <th>Candidate</th>
                        <th>Stage</th>
                        <th class="num">Match</th>
                        <th class="num">Experience</th>
                        <th>Current</th>
                        <th class="num">Interviews</th>
                        <th class="num">Days in stage</th>
                      </tr>
                    </thead>
                    <tbody>
                      @for (a of applications(); track a.id) {
                        <tr>
                          <td>
                            <a [routerLink]="['/candidates', a.candidate.id]" class="strong">
                              {{ a.candidate.full_name }}
                            </a>
                            <div class="muted small">{{ a.candidate.email }}</div>
                          </td>
                          <td>
                            <span class="pill" [class]="'stage-' + a.stage">
                              {{ stageLabel(a.stage) }}
                            </span>
                          </td>
                          <td class="num">{{ a.match_score ?? '—' }}{{ a.match_score !== null ? '%' : '' }}</td>
                          <td class="num">{{ a.candidate.total_experience ?? '—' }}</td>
                          <td class="small">{{ a.candidate.current_company || '—' }}</td>
                          <td class="num">{{ a.interview_count }}</td>
                          <td class="num">{{ a.days_in_stage }}</td>
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
              } @else {
                <div class="empty">
                  <span class="empty-title">No candidates on this requisition</span>
                  <p>Add someone from the candidate database to start the pipeline.</p>
                  @if (canManage) {
                    <button mat-flat-button color="primary" type="button" (click)="addCandidate()">
                      Add candidate
                    </button>
                  }
                </div>
              }
            </div>
          </mat-tab>

          <mat-tab label="Details">
            <div class="tab-body">
              <div class="card panel">
                <h3>Must-have skills</h3>
                @if (skills().length) {
                  <div class="chips">
                    @for (s of skills(); track s) { <span class="chip">{{ s }}</span> }
                  </div>
                } @else {
                  <p class="muted small">No skills listed. Add them so match scores work.</p>
                }

                <h3>Description</h3>
                <p class="desc">{{ j.description || 'No description written yet.' }}</p>

                <h3>Owners</h3>
                <dl class="pairs">
                  <div><dt>Hiring manager</dt><dd>{{ j.hiring_manager?.full_name || '—' }}</dd></div>
                  <div><dt>Recruiter</dt><dd>{{ j.recruiter?.full_name || '—' }}</dd></div>
                  <div><dt>Opened</dt><dd>{{ dayOf(j.created_at) }}</dd></div>
                </dl>
              </div>
            </div>
          </mat-tab>

          <mat-tab label="Activity">
            <div class="tab-body">
              <div class="card panel">
                <ul class="feed">
                  @for (a of feed(); track a.id) {
                    <li>
                      <span class="dot" aria-hidden="true"></span>
                      <span>
                        {{ a.summary }}
                        <span class="muted small">
                          · {{ a.actor_name || 'System' }} · {{ dayOf(a.created_at) }}
                        </span>
                      </span>
                    </li>
                  } @empty {
                    <li class="muted small">Nothing recorded on this requisition yet</li>
                  }
                </ul>
              </div>
            </div>
          </mat-tab>
        </mat-tab-group>
      }
    </div>
  `,
  styles: [`
    .back { display: inline-flex; align-items: center; gap: 4px; color: var(--muted); }
    .back mat-icon { font-size: 15px; width: 15px; height: 15px; }
    .actions { display: flex; gap: 8px; }

    .metric { display: flex; flex-direction: column; gap: 3px; padding: 13px 15px; align-items: flex-start; }
    .m-label { font-size: 12px; color: var(--muted); font-weight: 500; }
    .m-value { font-size: 19px; font-weight: 600; }

    .tab-body { padding-top: 16px; }
    .panel { padding: 18px 20px; }
    .panel h3 { margin: 0 0 8px; font-size: 13px; color: var(--muted); }
    .panel h3:not(:first-child) { margin-top: 22px; }

    .chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chip {
      background: #eef4f3; color: var(--accent-dark); border: 1px solid #cfe1de;
      border-radius: 4px; padding: 2px 8px; font-size: 12.5px; font-weight: 500;
    }

    .desc { margin: 0; white-space: pre-wrap; max-width: 74ch; }

    .pairs { margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .pairs dt { font-size: 12px; color: var(--muted); }
    .pairs dd { margin: 2px 0 0; font-weight: 500; }

    .feed { list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }
    .feed li { display: grid; grid-template-columns: 8px 1fr; gap: 9px; align-items: baseline; font-size: 13px; }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); margin-top: 6px; }
  `],
})
export class JobDetailComponent implements OnInit {
  id = input.required<string>();

  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  job = signal<Job | null>(null);
  applications = signal<Application[]>([]);
  feed = signal<Activity[]>([]);
  loading = signal(true);
  canManage = this.auth.can('manage_jobs');

  skills = computed(() =>
    (this.job()?.skills ?? '').split(',').map((s) => s.trim()).filter(Boolean),
  );
  activeCount = computed(
    () => this.applications().filter((a) => !['hired', 'rejected'].includes(a.stage)).length,
  );

  ngOnInit(): void {
    this.refresh();
  }

  private refresh(): void {
    const jobId = Number(this.id());
    this.loading.set(true);
    this.api.job(jobId).subscribe({
      next: (j) => {
        this.job.set(j);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
    this.api
      .applications({ job_id: jobId, page_size: 200 })
      .subscribe((res) => this.applications.set(res.items));
    this.api
      .activity({ entity_type: 'job', entity_id: jobId, limit: 30 })
      .subscribe((f) => this.feed.set(f));
  }

  edit(job: Job): void {
    this.dialog
      .open(JobFormDialog, { data: { job } })
      .afterClosed()
      .subscribe((updated) => {
        if (updated) {
          this.snack.open('Requisition updated', 'Dismiss', { duration: 3000 });
          this.refresh();
        }
      });
  }

  addCandidate(): void {
    const job = this.job();
    if (!job) return;
    this.dialog
      .open(AddToPipelineDialog, { data: { job } })
      .afterClosed()
      .subscribe((created) => {
        if (created) {
          this.snack.open('Candidate added to the pipeline', 'Dismiss', { duration: 3500 });
          this.refresh();
        }
      });
  }

  statusLabel(status: Job['status']): string {
    return JOB_STATUS_LABELS[status];
  }

  statusClass(status: Job['status']): string {
    return {
      open: 'stage-hired',
      draft: 'stage-sourced',
      on_hold: 'stage-offer',
      closed: 'stage-rejected',
      filled: 'stage-interview',
    }[status];
  }

  stageLabel(stage: Application['stage']): string {
    return STAGES.find((s) => s.value === stage)?.label ?? stage;
  }

  label(value?: string | null): string {
    return titleCase(value);
  }

  band(job: Job): string {
    if (!job.salary_min && !job.salary_max) return '—';
    return `${lakhs(job.salary_min)} – ${lakhs(job.salary_max)}`;
  }

  experience(job: Job): string {
    if (job.experience_min === null && job.experience_max === null) return '—';
    return `${job.experience_min ?? 0}–${job.experience_max ?? '+'} yrs`;
  }

  dayOf(value?: string | null): string {
    return day(value);
  }
}
