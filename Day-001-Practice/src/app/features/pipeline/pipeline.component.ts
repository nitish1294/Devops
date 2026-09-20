import { CdkDragDrop, DragDropModule } from '@angular/cdk/drag-drop';
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
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Application, Board, BoardColumn, Job, STAGES, Stage } from '../../core/models';
import { MatCheckboxModule } from '@angular/material/checkbox';

import { saveResponse } from '../../core/download';
import { StageMoveDialog } from '../../shared/stage-move.dialog';

@Component({
  selector: 'app-pipeline',
  standalone: true,
  imports: [
    DragDropModule, FormsModule, RouterLink, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatSelectModule, MatMenuModule, MatTooltipModule,
    MatProgressBarModule, MatCheckboxModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Pipeline</h1>
          <p>
            Drag a candidate between stages to move them. Every move is recorded on the
            candidate's timeline.
          </p>
        </div>
      </div>

      <div class="toolbar">
        <mat-form-field appearance="outline" class="req-filter">
          <mat-label>Requisition</mat-label>
          <mat-select [(ngModel)]="jobId" (ngModelChange)="load()">
            <mat-option [value]="null">All requisitions</mat-option>
            @for (j of jobs(); track j.id) {
              <mat-option [value]="j.id">{{ j.code }} — {{ j.title }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <span class="spacer"></span>
        <span class="muted small">{{ totalOnBoard() }} in pipeline</span>
        @if (canMove) {
          <button mat-stroked-button type="button" (click)="toggleSelectMode()">
            <mat-icon>{{ selectMode() ? 'close' : 'checklist' }}</mat-icon>
            {{ selectMode() ? 'Cancel' : 'Select' }}
          </button>
        }
        <button mat-stroked-button type="button" (click)="exportCsv()">
          <mat-icon>download</mat-icon>
          Export
        </button>
        <button mat-stroked-button type="button" (click)="load()">
          <mat-icon>refresh</mat-icon>
          Refresh
        </button>
      </div>

      @if (selectMode()) {
        <div class="bulk-bar" role="region" aria-label="Bulk actions">
          <span class="strong">{{ selected().size }} selected</span>
          <span class="muted small">Screening in batches beats clicking through one at a time.</span>
          <span class="spacer"></span>
          <button mat-stroked-button type="button" [disabled]="!selected().size"
                  [matMenuTriggerFor]="bulkMenu">
            <mat-icon>drive_file_move</mat-icon>
            Move to…
          </button>
          <mat-menu #bulkMenu="matMenu">
            @for (s of stages; track s.value) {
              <button mat-menu-item type="button" (click)="bulkMove(s.value)">{{ s.label }}</button>
            }
          </mat-menu>
          <button mat-stroked-button type="button" [disabled]="!selected().size"
                  (click)="clearSelection()">
            Clear
          </button>
        </div>
      }

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      <div class="board" cdkDropListGroup>
        @for (col of columns(); track col.stage) {
          <section class="col" [class]="'stage-' + col.stage">
            <header>
              <span class="col-name">{{ col.label }}</span>
              <span class="col-count num">{{ col.count }}</span>
            </header>

            <div
              class="drop"
              cdkDropList
              [cdkDropListData]="col"
              [cdkDropListDisabled]="!canMove"
              (cdkDropListDropped)="dropped($event)"
            >
              @for (app of col.items; track app.id) {
                <article class="ticket" cdkDrag [cdkDragData]="app"
                         [class.picked]="selected().has(app.id)"
                         [cdkDragDisabled]="selectMode()">
                  <div class="ticket-head">
                    @if (selectMode()) {
                      <mat-checkbox
                        class="pick"
                        [checked]="selected().has(app.id)"
                        (change)="togglePick(app.id)"
                        [aria-label]="'Select ' + app.candidate.full_name"
                      />
                    }
                    <a [routerLink]="['/candidates', app.candidate.id]" class="cand-name">
                      {{ app.candidate.full_name }}
                    </a>
                    @if (canMove) {
                      <button
                        mat-icon-button
                        type="button"
                        [matMenuTriggerFor]="moveMenu"
                        aria-label="Move to another stage"
                        class="tiny"
                      >
                        <mat-icon>more_vert</mat-icon>
                      </button>
                      <mat-menu #moveMenu="matMenu">
                        @for (s of stages; track s.value) {
                          @if (s.value !== app.stage) {
                            <button mat-menu-item type="button" (click)="moveVia(app, s.value)">
                              Move to {{ s.label }}
                            </button>
                          }
                        }
                      </mat-menu>
                    }
                  </div>

                  <div class="meta small muted">
                    {{ app.job.code }}
                    @if (app.candidate.current_company) { · {{ app.candidate.current_company }} }
                  </div>

                  @if (app.match_score !== null && app.match_score !== undefined) {
                    <div
                      class="match"
                      [matTooltip]="'Skill overlap with the requisition'"
                    >
                      <span class="bar" aria-hidden="true">
                        <span class="fill" [style.width.%]="app.match_score"></span>
                      </span>
                      <span class="num small">{{ app.match_score }}%</span>
                    </div>
                  }

                  <footer class="small muted">
                    @if (app.interview_count > 0) {
                      <span class="chip">
                        <mat-icon>event_note</mat-icon>{{ app.interview_count }}
                      </span>
                    }
                    <span>{{ app.days_in_stage }}d in stage</span>
                  </footer>
                </article>
              } @empty {
                <p class="col-empty small">Nothing here yet</p>
              }
            </div>
          </section>
        }
      </div>
    </div>
  `,
  styles: [`
    .req-filter { width: 320px; }

    .board {
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: minmax(228px, 1fr);
      gap: 12px;
      overflow-x: auto;
      padding-bottom: 12px;
      align-items: start;
    }

    .col { background: #e6eaee; border-radius: var(--radius); min-width: 228px; }

    /* The stage hue is the one strong colour on the page, and it encodes state. */
    .col header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 9px 12px;
      border-top: 3px solid currentColor;
      border-radius: var(--radius) var(--radius) 0 0;
      background: var(--paper);
    }
    .col-name { font-weight: 600; font-size: 13px; color: var(--text); }
    .col-count {
      font-size: 12px; font-weight: 600; color: currentColor;
      background: #f1f4f6; border-radius: 10px; padding: 1px 8px;
    }

    .drop { padding: 8px; min-height: 90px; display: flex; flex-direction: column; gap: 8px; }

    .ticket {
      background: var(--paper);
      border: 1px solid var(--rule);
      border-radius: 5px;
      padding: 9px 10px;
      cursor: grab;
    }
    .ticket:active { cursor: grabbing; }

    .ticket-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 4px; }
    .cand-name { font-weight: 600; font-size: 13.5px; color: var(--text); line-height: 1.3; }
    .cand-name:hover { color: var(--accent); }

    .tiny { width: 24px; height: 24px; line-height: 24px; flex: 0 0 24px; }
    .tiny mat-icon { font-size: 17px; width: 17px; height: 17px; }

    .meta { margin-top: 2px; }

    .match { display: flex; align-items: center; gap: 7px; margin-top: 7px; }
    .bar { flex: 1; height: 4px; background: #e4e9ed; border-radius: 2px; overflow: hidden; }
    .fill { display: block; height: 100%; background: currentColor; }

    .ticket footer { display: flex; align-items: center; gap: 10px; margin-top: 7px; }
    .chip { display: inline-flex; align-items: center; gap: 3px; }
    .chip mat-icon { font-size: 14px; width: 14px; height: 14px; }

    .col-empty { color: #8a99a8; text-align: center; padding: 14px 6px; margin: 0; }

    /* Motion here answers the drag - it shows what moved. */
    .cdk-drag-preview {
      box-shadow: 0 6px 18px rgba(20, 33, 46, 0.22);
      border-radius: 5px;
      opacity: 0.96;
    }
    .cdk-drag-placeholder { opacity: 0.35; }
    .cdk-drop-list-dragging .ticket:not(.cdk-drag-placeholder) {
      transition: transform 180ms cubic-bezier(0.2, 0, 0, 1);
    }
    .bulk-bar {
      display: flex; align-items: center; gap: 12px;
      padding: 9px 14px; margin-bottom: 10px;
      background: var(--ink); color: #fff; border-radius: var(--radius);
    }
    .bulk-bar .muted { color: #a8b6c2; }
    .bulk-bar button { color: #fff; border-color: #40566a; }
    .ticket.picked { outline: 2px solid var(--accent); outline-offset: -1px; }
    .ticket .pick { margin-right: 2px; }
  `],
})
export class PipelineComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);
  private router = inject(Router);

  stages = STAGES;
  jobId: number | null = null;
  jobs = signal<Job[]>([]);
  board = signal<Board | null>(null);
  loading = signal(false);

  columns = computed(() => this.board()?.columns ?? []);
  totalOnBoard = computed(() =>
    this.columns().reduce((sum, c) => sum + c.count, 0),
  );
  canMove = this.auth.can('move_pipeline');

  selectMode = signal(false);
  selected = signal<Set<number>>(new Set());

  ngOnInit(): void {
    this.api.jobs({ page_size: 100 }).subscribe((res) => this.jobs.set(res.items));
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.board(this.jobId).subscribe({
      next: (board) => {
        this.board.set(board);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  toggleSelectMode(): void {
    this.selectMode.update((on) => !on);
    if (!this.selectMode()) this.clearSelection();
  }

  togglePick(id: number): void {
    // A new Set each time, so the signal actually reports a change.
    this.selected.update((current) => {
      const next = new Set(current);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  clearSelection(): void {
    this.selected.set(new Set());
  }

  bulkMove(stage: Stage): void {
    const ids = [...this.selected()];
    if (!ids.length) return;

    const finish = (reason?: string, note?: string) => {
      this.api
        .bulkMoveStage({
          application_ids: ids,
          to_stage: stage,
          note,
          rejection_reason: reason,
        })
        .subscribe((result) => {
          // Partial success is normal here: report both halves plainly.
          const label = STAGES.find((s) => s.value === stage)?.label ?? stage;
          let message = `${result.moved} moved to ${label}`;
          if (result.skipped.length) {
            message += `, ${result.skipped.length} skipped`;
          }
          this.snack.open(message, 'Dismiss', { duration: 5000 });
          this.clearSelection();
          this.selectMode.set(false);
          this.load();
        });
    };

    if (stage === 'rejected') {
      // The server refuses a rejection with no reason, so ask before sending.
      this.dialog
        .open(StageMoveDialog, {
          data: {
            toLabel: STAGES.find((s) => s.value === stage)?.label ?? stage,
            candidateName: `${ids.length} candidates`,
            requiresReason: true,
          },
        })
        .afterClosed()
        .subscribe((result) => {
          if (result) finish(result.rejection_reason, result.note);
        });
      return;
    }
    finish();
  }

  exportCsv(): void {
    this.api.exportPipeline({ job_id: this.jobId ?? undefined }).subscribe((res) => {
      saveResponse(res, 'pipeline.csv');
    });
  }

  dropped(event: CdkDragDrop<BoardColumn>): void {
    const target = event.container.data;
    const source = event.previousContainer.data;
    const app = event.item.data as Application;

    if (target.stage === source.stage) return;
    this.commit(app, target.stage, target.label);
  }

  moveVia(app: Application, stage: Stage): void {
    const label = STAGES.find((s) => s.value === stage)?.label ?? stage;
    this.commit(app, stage, label);
  }

  /** Rejections need a reason, so those go through the dialog first. */
  private commit(app: Application, stage: Stage, label: string): void {
    const requiresReason = stage === 'rejected';

    if (!requiresReason) {
      this.send(app, stage, label, {});
      return;
    }

    this.dialog
      .open(StageMoveDialog, {
        data: { candidateName: app.candidate.full_name, toLabel: label, requiresReason },
      })
      .afterClosed()
      .subscribe((result) => {
        if (!result) {
          this.load();
          return;
        }
        this.send(app, stage, label, result);
      });
  }

  private send(
    app: Application,
    stage: Stage,
    label: string,
    extra: { note?: string; rejection_reason?: string },
  ): void {
    this.api.moveStage(app.id, { to_stage: stage, ...extra }).subscribe({
      next: () => {
        this.snack.open(`${app.candidate.full_name} moved to ${label}`, 'Dismiss', {
          duration: 3500,
        });
        this.load();
        if (stage === 'offer') {
          this.snack
            .open(`${app.candidate.full_name} is at offer stage`, 'Raise offer', { duration: 6000 })
            .onAction()
            .subscribe(() => void this.router.navigate(['/offers'], {
              queryParams: { application_id: app.id },
            }));
        }
      },
      error: () => this.load(),
    });
  }
}
