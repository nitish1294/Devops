import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ApiService } from '../../core/api.service';
import { titleCase } from '../../core/format';
import { Candidate, SOURCES } from '../../core/models';

@Component({
  selector: 'app-candidate-form-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.candidate ? 'Edit candidate' : 'Add candidate' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form-grid">
        <mat-form-field appearance="outline">
          <mat-label>Full name</mat-label>
          <input matInput formControlName="full_name" />
          @if (form.controls.full_name.touched && form.controls.full_name.invalid) {
            <mat-error>Enter the candidate's name</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Email</mat-label>
          <input matInput type="email" formControlName="email" />
          @if (form.controls.email.touched && form.controls.email.invalid) {
            <mat-error>Enter a valid email address</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Phone</mat-label>
          <input matInput formControlName="phone" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Location</mat-label>
          <input matInput formControlName="location" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Current company</mat-label>
          <input matInput formControlName="current_company" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Current title</mat-label>
          <input matInput formControlName="current_title" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Total experience (years)</mat-label>
          <input matInput type="number" step="0.5" min="0" formControlName="total_experience" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Notice period (days)</mat-label>
          <input matInput type="number" min="0" formControlName="notice_period_days" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Current CTC (annual)</mat-label>
          <input matInput type="number" min="0" formControlName="current_ctc" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Expected CTC (annual)</mat-label>
          <input matInput type="number" min="0" formControlName="expected_ctc" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Source</mat-label>
          <mat-select formControlName="source">
            @for (s of sources; track s) {
              <mat-option [value]="s">{{ label(s) }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Referred by</mat-label>
          <input matInput formControlName="referred_by" />
        </mat-form-field>

        <mat-form-field appearance="outline" class="full">
          <mat-label>Skills</mat-label>
          <input matInput formControlName="skills" placeholder="python, docker, aws" />
          <mat-hint>Comma separated. A resume upload adds to this automatically.</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full">
          <mat-label>LinkedIn URL</mat-label>
          <input matInput formControlName="linkedin_url" />
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="saving" (click)="save()">
        {{ data.candidate ? 'Save changes' : 'Add candidate' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 600px; max-width: 700px; padding-top: 8px; }
    @media (max-width: 680px) { mat-dialog-content { min-width: auto; } }
  `],
})
export class CandidateFormDialog {
  ref = inject(MatDialogRef<CandidateFormDialog>);
  data = inject<{ candidate?: Candidate }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  sources = SOURCES;
  saving = false;
  private editing = this.data.candidate;

  form = this.fb.group({
    full_name: [this.editing?.full_name ?? '', [Validators.required, Validators.minLength(2)]],
    email: [this.editing?.email ?? '', [Validators.required, Validators.email]],
    phone: [this.editing?.phone ?? ''],
    location: [this.editing?.location ?? ''],
    current_company: [this.editing?.current_company ?? ''],
    current_title: [this.editing?.current_title ?? ''],
    total_experience: [this.editing?.total_experience ?? null],
    notice_period_days: [this.editing?.notice_period_days ?? null],
    current_ctc: [this.editing?.current_ctc ?? null],
    expected_ctc: [this.editing?.expected_ctc ?? null],
    source: [this.editing?.source ?? ''],
    referred_by: [this.editing?.referred_by ?? ''],
    skills: [this.editing?.skills ?? ''],
    linkedin_url: [this.editing?.linkedin_url ?? ''],
  });

  constructor() {
    if (this.editing) this.form.controls.email.disable();
  }

  label(value: string): string {
    return titleCase(value);
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving = true;
    const payload: Record<string, unknown> = { ...this.form.getRawValue() };
    for (const key of Object.keys(payload)) {
      if (payload[key] === '' || payload[key] === null) delete payload[key];
    }
    if (this.editing) delete payload['email'];

    const request = this.editing
      ? this.api.updateCandidate(this.editing.id, payload as Partial<Candidate>)
      : this.api.createCandidate(payload as Partial<Candidate>);

    request.subscribe({
      next: (candidate) => this.ref.close(candidate),
      error: () => (this.saving = false),
    });
  }
}
