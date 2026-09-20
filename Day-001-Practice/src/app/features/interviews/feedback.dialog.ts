import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ApiService } from '../../core/api.service';
import { Interview, Recommendation } from '../../core/models';

const CRITERIA = [
  { key: 'problem_solving', label: 'Problem solving' },
  { key: 'technical_depth', label: 'Technical depth' },
  { key: 'system_design', label: 'System design' },
  { key: 'communication', label: 'Communication' },
  { key: 'ownership', label: 'Ownership' },
];

@Component({
  selector: 'app-feedback-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>Feedback: {{ data.interview.round_name }}</h2>
    <mat-dialog-content>
      <p class="muted small">
        {{ data.interview.candidate?.full_name }} · {{ data.interview.job_title }}
      </p>

      <form [formGroup]="form">
        <h3>Rate each area</h3>
        <div class="criteria">
          @for (c of criteria; track c.key) {
            <div class="row">
              <span class="c-label">{{ c.label }}</span>
              <span class="stars">
                @for (n of scale; track n) {
                  <button
                    type="button"
                    class="star"
                    [class.on]="score(c.key) >= n"
                    (click)="setScore(c.key, n)"
                    [attr.aria-label]="c.label + ': ' + n + ' of 5'"
                  >
                    <mat-icon>{{ score(c.key) >= n ? 'star' : 'star_border' }}</mat-icon>
                  </button>
                }
              </span>
            </div>
          }
        </div>

        <div class="form-grid">
          <mat-form-field appearance="outline">
            <mat-label>Overall rating</mat-label>
            <mat-select formControlName="overall_rating">
              @for (n of scale; track n) { <mat-option [value]="n">{{ n }} / 5</mat-option> }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Recommendation</mat-label>
            <mat-select formControlName="recommendation">
              <mat-option value="strong_yes">Strong yes</mat-option>
              <mat-option value="yes">Yes</mat-option>
              <mat-option value="no">No</mat-option>
              <mat-option value="strong_no">Strong no</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Strengths</mat-label>
          <input matInput formControlName="strengths" placeholder="Separate with semicolons" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Concerns</mat-label>
          <input matInput formControlName="concerns" placeholder="Separate with semicolons" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Summary</mat-label>
          <textarea matInput rows="3" formControlName="feedback_summary"></textarea>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="saving" (click)="save()">
        Submit feedback
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 520px; max-width: 600px; padding-top: 6px; }
    @media (max-width: 580px) { mat-dialog-content { min-width: auto; } }
    form { display: flex; flex-direction: column; }
    h3 { margin: 14px 0 8px; font-size: 12.5px; color: var(--muted); font-weight: 600; }
    .criteria { display: grid; gap: 6px; margin-bottom: 16px; }
    .row { display: grid; grid-template-columns: 1fr auto; align-items: center; }
    .c-label { font-size: 13px; }
    .stars { display: flex; gap: 1px; }
    .star {
      background: none; border: none; padding: 2px; cursor: pointer;
      color: var(--rule); line-height: 1;
    }
    .star.on { color: #b45309; }
    .star mat-icon { font-size: 19px; width: 19px; height: 19px; }
  `],
})
export class FeedbackDialog {
  ref = inject(MatDialogRef<FeedbackDialog>);
  data = inject<{ interview: Interview }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  criteria = CRITERIA;
  scale = [1, 2, 3, 4, 5];
  scores: Record<string, number> = {};
  saving = false;

  form = this.fb.group({
    overall_rating: [this.data.interview.overall_rating ?? 3, [Validators.required]],
    recommendation: ['yes' as Recommendation, [Validators.required]],
    strengths: [''],
    concerns: [''],
    feedback_summary: [this.data.interview.feedback_summary ?? ''],
  });

  score(key: string): number {
    return this.scores[key] ?? 0;
  }

  setScore(key: string, value: number): void {
    this.scores[key] = value;
    const given = Object.values(this.scores);
    if (given.length) {
      const avg = Math.round(given.reduce((a, b) => a + b, 0) / given.length);
      this.form.controls.overall_rating.setValue(avg);
    }
  }

  private split(value?: string | null): string[] {
    return (value ?? '').split(';').map((s) => s.trim()).filter(Boolean);
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving = true;
    const v = this.form.getRawValue();

    this.api
      .submitFeedback(this.data.interview.id, {
        overall_rating: Number(v.overall_rating),
        recommendation: v.recommendation as Recommendation,
        feedback_summary: v.feedback_summary || undefined,
        criteria: this.scores,
        strengths: this.split(v.strengths),
        concerns: this.split(v.concerns),
      })
      .subscribe({
        next: (card) => this.ref.close(card),
        error: () => (this.saving = false),
      });
  }
}
