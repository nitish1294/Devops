import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { day, lakhs, titleCase } from '../../core/format';
import { JOB_STATUS_LABELS, Job, JobStatus } from '../../core/models';
import { JobFormDialog } from './job-form.dialog';

@Component({
  selector: 'app-jobs',
  standalone: true,
  imports: [
    FormsModule, RouterLink, MatButtonModule, MatIconModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatMenuModule, MatPaginatorModule, MatProgressBarModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Requisitions</h1>
          <p>Open roles, who owns them, and how many candidates are in play.</p>
        </div>
        @if (canManage) {
          <button mat-flat-button color="primary" type="button" (click)="create()">
            <mat-icon>add</mat-icon>
            New requisition
          </button>
        }
      </div>

      <div class="toolbar">
        <mat-form-field appearance="outline" class="search">
          <mat-label>Search title, code or skill</mat-label>
          <input matInput [(ngModel)]="query" (ngModelChange)="search$.next()" />
          <mat-icon matSuffix>search</mat-icon>
        </mat-form-field>
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Status</mat-label>
          <mat-select [(ngModel)]="status" (ngModelChange)="reload()">
            <mat-option [value]="null">All</mat-option>
            @for (s of statuses; track s) {
              <mat-option [value]="s">{{ statusLabel(s) }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <span class="spacer"></span>
        <span class="muted small">{{ total() }} requisitions</span>
      </div>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (jobs().length) {
        <div class="card">
          <table class="data">
            <thead>
              <tr>
                <th>Requisition</th>
                <th>Department</th>
                <th>Status</th>
                <th class="num">Openings</th>
                <th class="num">Applicants</th>
                <th class="num">Hired</th>
                <th>Salary band</th>
                <th>Recruiter</th>
                <th>Target close</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (j of jobs(); track j.id) {
                <tr>
                  <td>
                    <a [routerLink]="['/jobs', j.id]" class="strong">{{ j.title }}</a>
                    <div class="muted small">{{ j.code }} · {{ j.location || 'Location TBD' }}</div>
                  </td>
                  <td>{{ j.department?.name || '—' }}</td>
                  <td><span class="pill" [class]="statusClass(j.status)">{{ statusLabel(j.status) }}</span></td>
                  <td class="num">{{ j.openings }}</td>
                  <td class="num">{{ j.applicant_count }}</td>
                  <td class="num">{{ j.hired_count }}</td>
                  <td class="small">{{ band(j) }}</td>
                  <td class="small">{{ j.recruiter?.full_name || '—' }}</td>
                  <td class="small">{{ dayOf(j.target_close_date) }}</td>
                  <td>
                    @if (canManage) {
                      <button mat-icon-button type="button" [matMenuTriggerFor]="menu"
                              aria-label="Requisition actions">
                        <mat-icon>more_vert</mat-icon>
                      </button>
                      <mat-menu #menu="matMenu">
                        <button mat-menu-item type="button" (click)="edit(j)">
                          <mat-icon>edit</mat-icon> Edit
                        </button>
                        @if (j.status !== 'open') {
                          <button mat-menu-item type="button" (click)="setStatus(j, 'open')">
                            <mat-icon>play_arrow</mat-icon> Mark open
                          </button>
                        }
                        @if (j.status === 'open') {
                          <button mat-menu-item type="button" (click)="setStatus(j, 'on_hold')">
                            <mat-icon>pause</mat-icon> Put on hold
                          </button>
                        }
                        @if (j.status !== 'closed') {
                          <button mat-menu-item type="button" (click)="close(j)">
                            <mat-icon>archive</mat-icon> Close requisition
                          </button>
                        }
                      </mat-menu>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
          <mat-paginator
            [length]="total()"
            [pageSize]="pageSize"
            [pageIndex]="page - 1"
            [pageSizeOptions]="[10, 20, 50]"
            (page)="paginate($event)"
          />
        </div>
      } @else if (!loading()) {
        <div class="empty">
          <span class="empty-title">No requisitions match this view</span>
          @if (canManage) {
            <p>Create one to start collecting candidates.</p>
            <button mat-flat-button color="primary" type="button" (click)="create()">
              New requisition
            </button>
          } @else {
            <p>Ask a recruiter to open a requisition.</p>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .search { width: 320px; }
    .narrow { width: 170px; }
    table.data a { color: var(--text); }
    table.data a:hover { color: var(--accent); }
  `],
})
export class JobsComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  jobs = signal<Job[]>([]);
  total = signal(0);
  loading = signal(false);

  query = '';
  status: JobStatus | null = null;
  page = 1;
  pageSize = 20;
  statuses: JobStatus[] = ['draft', 'open', 'on_hold', 'closed', 'filled'];
  canManage = this.auth.can('manage_jobs');
  search$ = new Subject<void>();

  ngOnInit(): void {
    this.search$.pipe(debounceTime(300)).subscribe(() => this.reload());
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.api
      .jobs({
        q: this.query || undefined,
        status: this.status ?? undefined,
        page: this.page,
        page_size: this.pageSize,
      })
      .subscribe({
        next: (res) => {
          this.jobs.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  paginate(event: PageEvent): void {
    this.page = event.pageIndex + 1;
    this.pageSize = event.pageSize;
    this.reload();
  }

  create(): void {
    this.dialog
      .open(JobFormDialog, { data: {} })
      .afterClosed()
      .subscribe((job) => {
        if (job) {
          this.snack.open(`${job.code} created`, 'Dismiss', { duration: 4000 });
          this.reload();
        }
      });
  }

  edit(job: Job): void {
    this.dialog
      .open(JobFormDialog, { data: { job } })
      .afterClosed()
      .subscribe((updated) => {
        if (updated) {
          this.snack.open('Requisition updated', 'Dismiss', { duration: 3000 });
          this.reload();
        }
      });
  }

  setStatus(job: Job, status: JobStatus): void {
    this.api.updateJob(job.id, { status }).subscribe(() => {
      this.snack.open(`${job.code} is now ${JOB_STATUS_LABELS[status].toLowerCase()}`, 'Dismiss', {
        duration: 3000,
      });
      this.reload();
    });
  }

  close(job: Job): void {
    this.api.closeJob(job.id).subscribe((res) => {
      this.snack.open(res.detail, 'Dismiss', { duration: 3000 });
      this.reload();
    });
  }

  statusLabel(status: JobStatus): string {
    return JOB_STATUS_LABELS[status] ?? titleCase(status);
  }

  statusClass(status: JobStatus): string {
    return {
      open: 'stage-hired',
      draft: 'stage-sourced',
      on_hold: 'stage-offer',
      closed: 'stage-rejected',
      filled: 'stage-interview',
    }[status];
  }

  band(job: Job): string {
    if (!job.salary_min && !job.salary_max) return '—';
    return `${lakhs(job.salary_min)} – ${lakhs(job.salary_max)}`;
  }

  dayOf(value?: string | null): string {
    return day(value);
  }
}
