import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { debounceTime, switchMap } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { Candidate, Job, STAGES } from '../../core/models';

/**
 * Two ways in: pick an existing candidate, or pick the job for a candidate you
 * already have open. `data.job` decides which side is fixed.
 */
@Component({
  selector: 'app-add-to-pipeline-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatAutocompleteModule,
  ],
  template: `
    <h2 mat-dialog-title>Add to pipeline</h2>
    <mat-dialog-content>
      <form [formGroup]="form">
        @if (data.job) {
          <p class="fixed small">
            <span class="muted">Requisition</span><br />
            <span class="strong">{{ data.job.code }} — {{ data.job.title }}</span>
          </p>

          <mat-form-field appearance="outline">
            <mat-label>Find a candidate</mat-label>
            <input matInput [matAutocomplete]="auto" formControlName="candidateSearch"
                   placeholder="Type a name or email" />
            <mat-autocomplete #auto (optionSelected)="pickCandidate($event.option.value)"
                              [displayWith]="displayCandidate">
              @for (c of matches(); track c.id) {
                <mat-option [value]="c">
                  {{ c.full_name }}
                  <span class="muted small"> · {{ c.email }}</span>
                </mat-option>
              }
            </mat-autocomplete>
            <mat-hint>Search the candidate database</mat-hint>
          </mat-form-field>
        } @else {
          <p class="fixed small">
            <span class="muted">Candidate</span><br />
            <span class="strong">{{ data.candidate?.full_name }}</span>
          </p>

          <mat-form-field appearance="outline">
            <mat-label>Requisition</mat-label>
            <mat-select formControlName="job_id">
              @for (j of openJobs(); track j.id) {
                <mat-option [value]="j.id">{{ j.code }} — {{ j.title }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        }

        <mat-form-field appearance="outline">
          <mat-label>Starting stage</mat-label>
          <mat-select formControlName="stage">
            @for (s of stages; track s.value) {
              <mat-option [value]="s.value">{{ s.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="!ready() || saving"
              (click)="save()">
        Add to pipeline
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 400px; padding-top: 6px; }
    form { display: flex; flex-direction: column; }
    .fixed { margin: 0 0 16px; padding: 10px 12px; background: #f3f6f7;
             border-radius: var(--radius); border: 1px solid var(--rule); }
  `],
})
export class AddToPipelineDialog {
  ref = inject(MatDialogRef<AddToPipelineDialog>);
  data = inject<{ job?: Job; candidate?: Candidate }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  stages = STAGES.filter((s) => !['hired', 'rejected'].includes(s.value));
  matches = signal<Candidate[]>([]);
  openJobs = signal<Job[]>([]);
  selectedCandidateId: number | null = this.data.candidate?.id ?? null;
  saving = false;

  form = this.fb.group({
    candidateSearch: [''],
    job_id: [this.data.job?.id ?? null, this.data.job ? [] : [Validators.required]],
    stage: ['sourced' as const, [Validators.required]],
  });

  constructor() {
    if (!this.data.job) {
      this.api
        .jobs({ status: 'open', page_size: 100 })
        .subscribe((res) => this.openJobs.set(res.items));
    }

    this.form.controls.candidateSearch.valueChanges
      .pipe(
        debounceTime(300),
        switchMap((term) =>
          this.api.candidates({ q: typeof term === 'string' ? term : '', page_size: 10 }),
        ),
      )
      .subscribe((res) => this.matches.set(res.items));
  }

  displayCandidate(value: Candidate | string): string {
    return typeof value === 'string' ? value : value?.full_name ?? '';
  }

  pickCandidate(candidate: Candidate): void {
    this.selectedCandidateId = candidate.id;
  }

  ready(): boolean {
    return this.selectedCandidateId !== null && this.form.controls.stage.valid &&
      (this.data.job ? true : this.form.controls.job_id.valid);
  }

  save(): void {
    const jobId = this.data.job?.id ?? this.form.value.job_id;
    if (!jobId || !this.selectedCandidateId) return;
    this.saving = true;

    this.api
      .createApplication({
        job_id: Number(jobId),
        candidate_id: this.selectedCandidateId,
        stage: this.form.value.stage ?? 'sourced',
      })
      .subscribe({
        next: (app) => this.ref.close(app),
        error: () => (this.saving = false),
      });
  }
}
