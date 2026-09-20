import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { saveResponse } from '../../core/download';
import { AuthService } from '../../core/auth.service';
import { lakhs, titleCase } from '../../core/format';
import { Candidate, SOURCES } from '../../core/models';
import { AddToPipelineDialog } from './add-to-pipeline.dialog';
import { CandidateFormDialog } from './candidate-form.dialog';

@Component({
  selector: 'app-candidates',
  standalone: true,
  imports: [
    FormsModule, RouterLink, MatButtonModule, MatIconModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatPaginatorModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Candidates</h1>
          <p>Everyone in the database, searchable by name, skill or source.</p>
        </div>
        <div class="actions">
          <button mat-stroked-button type="button" [disabled]="exporting()" (click)="exportCsv()">
            <mat-icon>download</mat-icon>
            Export CSV
          </button>
          @if (canManage) {
            <button mat-flat-button color="primary" type="button" (click)="create()">
              <mat-icon>person_add</mat-icon>
              Add candidate
            </button>
          }
        </div>
      </div>

      <div class="toolbar">
        <mat-form-field appearance="outline" class="search">
          <mat-label>Search name, email or company</mat-label>
          <input matInput [(ngModel)]="query" (ngModelChange)="search$.next()" />
          <mat-icon matSuffix>search</mat-icon>
        </mat-form-field>
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Skill</mat-label>
          <input matInput [(ngModel)]="skill" (ngModelChange)="search$.next()"
                 placeholder="e.g. docker" />
        </mat-form-field>
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Source</mat-label>
          <mat-select [(ngModel)]="source" (ngModelChange)="reload()">
            <mat-option [value]="null">All</mat-option>
            @for (s of sources; track s) { <mat-option [value]="s">{{ label(s) }}</mat-option> }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" class="tiny-field">
          <mat-label>Min exp</mat-label>
          <input matInput type="number" min="0" [(ngModel)]="minExperience"
                 (ngModelChange)="search$.next()" />
        </mat-form-field>
        <span class="spacer"></span>
        <span class="muted small">{{ total() }} candidates</span>
      </div>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (candidates().length) {
        <div class="card">
          <table class="data">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Current</th>
                <th class="num">Exp</th>
                <th class="num">Expected</th>
                <th class="num">Notice</th>
                <th>Source</th>
                <th>Skills</th>
                <th class="num">In pipeline</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (c of candidates(); track c.id) {
                <tr>
                  <td>
                    <a [routerLink]="['/candidates', c.id]" class="strong">{{ c.full_name }}</a>
                    <div class="muted small">
                      {{ c.email }}
                      @if (c.resume_doc_id) {
                        <mat-icon class="resume-flag" matTooltip="Resume on file">description</mat-icon>
                      }
                    </div>
                  </td>
                  <td class="small">
                    {{ c.current_title || '—' }}
                    @if (c.current_company) { <div class="muted">{{ c.current_company }}</div> }
                  </td>
                  <td class="num">{{ c.total_experience ?? '—' }}</td>
                  <td class="num small">{{ money(c.expected_ctc) }}</td>
                  <td class="num small">{{ c.notice_period_days ?? '—' }}</td>
                  <td class="small">{{ label(c.source) }}</td>
                  <td class="small skills">{{ shortSkills(c.skills) }}</td>
                  <td class="num">{{ c.open_applications }}</td>
                  <td>
                    @if (canManage) {
                      <button mat-icon-button type="button" (click)="addToPipeline(c)"
                              matTooltip="Add to a requisition">
                        <mat-icon>playlist_add</mat-icon>
                      </button>
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
          <span class="empty-title">No candidates match these filters</span>
          <p>Clear the filters, or add someone new.</p>
          @if (canManage) {
            <button mat-flat-button color="primary" type="button" (click)="create()">
              Add candidate
            </button>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .actions { display: flex; gap: 8px; }
    .search { width: 300px; }
    .narrow { width: 160px; }
    .tiny-field { width: 100px; }
    table.data a { color: var(--text); }
    table.data a:hover { color: var(--accent); }
    .skills { max-width: 210px; color: var(--muted); }
    .resume-flag {
      font-size: 13px; width: 13px; height: 13px;
      vertical-align: -2px; color: var(--accent);
    }
  `],
})
export class CandidatesComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  candidates = signal<Candidate[]>([]);
  total = signal(0);
  loading = signal(false);
  exporting = signal(false);

  query = '';
  skill = '';
  source: string | null = null;
  minExperience: number | null = null;
  page = 1;
  pageSize = 20;
  sources = SOURCES;
  canManage = this.auth.can('manage_jobs');
  search$ = new Subject<void>();

  ngOnInit(): void {
    this.search$.pipe(debounceTime(300)).subscribe(() => this.reload());
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.api
      .candidates({
        q: this.query || undefined,
        skill: this.skill || undefined,
        source: this.source ?? undefined,
        min_experience: this.minExperience ?? undefined,
        page: this.page,
        page_size: this.pageSize,
      })
      .subscribe({
        next: (res) => {
          this.candidates.set(res.items);
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
      .open(CandidateFormDialog, { data: {} })
      .afterClosed()
      .subscribe((candidate) => {
        if (candidate) {
          this.snack.open(`${candidate.full_name} added`, 'Dismiss', { duration: 3500 });
          this.reload();
        }
      });
  }

  addToPipeline(candidate: Candidate): void {
    this.dialog
      .open(AddToPipelineDialog, { data: { candidate } })
      .afterClosed()
      .subscribe((created) => {
        if (created) {
          this.snack.open(`${candidate.full_name} added to the pipeline`, 'Dismiss', {
            duration: 3500,
          });
          this.reload();
        }
      });
  }

  /** Exports what is on screen, not the whole table — the filters carry over. */
  exportCsv(): void {
    this.exporting.set(true);
    this.api
      .exportCandidates({
        q: this.query || undefined,
        source: this.source ?? undefined,
        min_experience: this.minExperience ?? undefined,
      })
      .subscribe({
        next: (res) => {
          saveResponse(res, 'candidates.csv');
          this.exporting.set(false);
          this.snack.open('Export downloaded', 'Dismiss', { duration: 3000 });
        },
        error: () => this.exporting.set(false),
      });
  }

  label(value?: string | null): string {
    return titleCase(value);
  }

  money(value?: number | null): string {
    return lakhs(value);
  }

  shortSkills(skills?: string | null): string {
    if (!skills) return '—';
    const list = skills.split(',').map((s) => s.trim()).filter(Boolean);
    return list.length > 4 ? `${list.slice(0, 4).join(', ')} +${list.length - 4}` : list.join(', ');
  }
}
