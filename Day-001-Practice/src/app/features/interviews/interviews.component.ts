import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/api.service';
import { saveResponse } from '../../core/download';
import { AuthService } from '../../core/auth.service';
import { titleCase, when } from '../../core/format';
import { Interview } from '../../core/models';
import { FeedbackDialog } from './feedback.dialog';
import { ScheduleDialog } from './schedule.dialog';

@Component({
  selector: 'app-interviews',
  standalone: true,
  imports: [
    FormsModule, MatButtonModule, MatIconModule, MatFormFieldModule, MatSelectModule,
    MatMenuModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Interviews</h1>
          <p>Scheduled rounds, panels and feedback. Panelists cannot be double-booked.</p>
        </div>
        @if (canManage) {
          <button mat-flat-button color="primary" type="button" (click)="schedule()">
            <mat-icon>event_available</mat-icon>
            Schedule interview
          </button>
        }
      </div>

      <div class="toolbar">
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Show</mat-label>
          <mat-select [(ngModel)]="view" (ngModelChange)="reload()">
            <mat-option value="upcoming">Upcoming</mat-option>
            <mat-option value="all">All</mat-option>
            <mat-option value="completed">Completed</mat-option>
            <mat-option value="mine">On my panel</mat-option>
          </mat-select>
        </mat-form-field>
        <span class="spacer"></span>
        <span class="muted small">{{ interviews().length }} shown</span>
      </div>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (grouped().length) {
        @for (group of grouped(); track group.label) {
          <h2 class="group-label">{{ group.label }}</h2>
          <div class="card list">
            @for (iv of group.items; track iv.id) {
              <article class="row">
                <div class="slot">
                  <span class="time strong">{{ clock(iv.scheduled_at) }}</span>
                  <span class="date small muted">{{ dayLabel(iv.scheduled_at) }}</span>
                </div>

                <div class="who">
                  <span class="strong">{{ iv.candidate?.full_name || 'Candidate' }}</span>
                  <span class="small muted">{{ iv.round_name }} · {{ iv.job_title }}</span>
                </div>

                <div class="details small">
                  <span>
                    <mat-icon class="i">{{ modeIcon(iv.mode) }}</mat-icon>
                    {{ label(iv.mode) }} · {{ iv.duration_minutes }} min
                  </span>
                  <span class="muted">{{ panel(iv) }}</span>
                </div>

                <div class="verdict">
                  <span class="pill" [class]="statusClass(iv.status)">{{ label(iv.status) }}</span>
                  @if (iv.overall_rating) {
                    <span class="small strong">{{ iv.overall_rating }}/5 · {{ label(iv.recommendation) }}</span>
                  }
                </div>

                <div class="row-actions">
                  @if (iv.location_or_link && iv.status === 'scheduled') {
                    <a mat-icon-button [href]="iv.location_or_link" target="_blank" rel="noopener"
                       matTooltip="Open meeting link">
                      <mat-icon>videocam</mat-icon>
                    </a>
                  }
                  <button mat-icon-button type="button" (click)="addToCalendar(iv)"
                          matTooltip="Add to calendar">
                    <mat-icon>event</mat-icon>
                  </button>
                  @if (canGiveFeedback(iv)) {
                    <button mat-stroked-button type="button" (click)="feedback(iv)">
                      {{ iv.status === 'completed' ? 'Edit feedback' : 'Add feedback' }}
                    </button>
                  }
                  @if (canManage && iv.status === 'scheduled') {
                    <button mat-icon-button type="button" [matMenuTriggerFor]="menu"
                            aria-label="Interview actions">
                      <mat-icon>more_vert</mat-icon>
                    </button>
                    <mat-menu #menu="matMenu">
                      <button mat-menu-item type="button" (click)="cancel(iv)">
                        <mat-icon>event_busy</mat-icon> Cancel interview
                      </button>
                    </mat-menu>
                  }
                </div>
              </article>
            }
          </div>
        }
      } @else if (!loading()) {
        <div class="empty">
          <span class="empty-title">Nothing scheduled in this view</span>
          <p>
            @if (view === 'mine') {
              You are not on any panels right now.
            } @else {
              Schedule a round for a candidate who is in the interview stage.
            }
          </p>
          @if (canManage && view !== 'mine') {
            <button mat-flat-button color="primary" type="button" (click)="schedule()">
              Schedule interview
            </button>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .narrow { width: 200px; }
    .group-label { font-size: 12.5px; color: var(--muted); margin: 18px 0 8px; font-weight: 600; }
    .list { overflow: hidden; }

    .row {
      display: grid;
      grid-template-columns: 96px minmax(160px, 1.3fr) minmax(180px, 1.4fr) 170px auto;
      gap: 14px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--rule);
    }
    .row:last-child { border-bottom: none; }
    .row:hover { background: #f7f9fa; }

    .slot { display: flex; flex-direction: column; }
    .time { font-size: 14px; font-variant-numeric: tabular-nums; }
    .who { display: flex; flex-direction: column; min-width: 0; }
    .details { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .details .i { font-size: 14px; width: 14px; height: 14px; vertical-align: -2px; }
    .details span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .verdict { display: flex; flex-direction: column; gap: 4px; align-items: flex-start; }
    .row-actions { display: flex; align-items: center; gap: 4px; justify-content: flex-end; }

    @media (max-width: 1100px) {
      .row { grid-template-columns: 90px 1fr; row-gap: 8px; }
      .details, .verdict, .row-actions { grid-column: 2; }
    }
  `],
})
export class InterviewsComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  interviews = signal<Interview[]>([]);
  loading = signal(false);
  view: 'upcoming' | 'all' | 'completed' | 'mine' = 'upcoming';
  canManage = this.auth.can('manage_jobs');

  /** Grouped by day so a recruiter reads it like a calendar. */
  grouped = computed(() => {
    const buckets = new Map<string, Interview[]>();
    for (const iv of this.interviews()) {
      const key = this.dayKey(iv.scheduled_at);
      buckets.set(key, [...(buckets.get(key) ?? []), iv]);
    }
    return [...buckets.entries()].map(([label, items]) => ({
      label,
      items: items.sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)),
    }));
  });

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);

    if (this.view === 'mine') {
      this.api.myInterviews().subscribe({
        next: (list) => {
          this.interviews.set(list);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
      return;
    }

    this.api
      .interviews({
        upcoming_only: this.view === 'upcoming',
        status: this.view === 'completed' ? 'completed' : undefined,
        page_size: 200,
      })
      .subscribe({
        next: (res) => {
          this.interviews.set(res.items);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  schedule(): void {
    this.dialog
      .open(ScheduleDialog, { data: {} })
      .afterClosed()
      .subscribe((iv) => {
        if (iv) {
          this.snack.open('Interview scheduled and the candidate notified', 'Dismiss', {
            duration: 4500,
          });
          this.reload();
        }
      });
  }

  feedback(interview: Interview): void {
    this.dialog
      .open(FeedbackDialog, { data: { interview } })
      .afterClosed()
      .subscribe((card) => {
        if (card) {
          this.snack.open('Feedback recorded', 'Dismiss', { duration: 3500 });
          this.reload();
        }
      });
  }

  cancel(interview: Interview): void {
    this.api.cancelInterview(interview.id).subscribe((res) => {
      this.snack.open(res.detail, 'Dismiss', { duration: 3000 });
      this.reload();
    });
  }

  /** Downloads the .ics so a panelist can drop the round into their own calendar. */
  addToCalendar(interview: Interview): void {
    this.api.interviewInvite(interview.id).subscribe((res) => {
      saveResponse(res, `interview-${interview.id}.ics`);
    });
  }

  canGiveFeedback(iv: Interview): boolean {
    if (iv.status === 'cancelled') return false;
    const me = this.auth.user();
    if (!me) return false;
    const onPanel = iv.panelists.some((p) => p.id === me.id);
    return onPanel || this.canManage;
  }

  panel(iv: Interview): string {
    return iv.panelists.length ? iv.panelists.map((p) => p.full_name).join(', ') : 'No panel set';
  }

  modeIcon(mode: Interview['mode']): string {
    return { video: 'videocam', phone: 'call', onsite: 'business' }[mode];
  }

  statusClass(status: Interview['status']): string {
    return {
      scheduled: 'stage-interview',
      completed: 'stage-hired',
      cancelled: 'stage-rejected',
      no_show: 'stage-offer',
    }[status];
  }

  label(value?: string | null): string {
    return titleCase(value);
  }

  whenOf(iso: string): string {
    return when(iso);
  }

  clock(iso: string): string {
    return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  }

  dayLabel(iso: string): string {
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
  }

  private dayKey(iso: string): string {
    const date = new Date(iso);
    const today = new Date();
    const tomorrow = new Date(today.getTime() + 86400000);
    const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();

    if (same(date, today)) return 'Today';
    if (same(date, tomorrow)) return 'Tomorrow';
    return date.toLocaleDateString('en-IN', {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  }
}
