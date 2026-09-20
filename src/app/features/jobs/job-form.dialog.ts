import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatSelectModule } from '@angular/material/select';

import { ApiService } from '../../core/api.service';
import { Department, Job, User } from '../../core/models';

@Component({
  selector: 'app-job-form-dialog',
  standalone: true,
  providers: [provideNativeDateAdapter()],
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatDatepickerModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.job ? 'Edit ' + data.job.code : 'New requisition' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form-grid">
        <mat-form-field appearance="outline" class="full">
          <mat-label>Job title</mat-label>
          <input matInput formControlName="title" />
          @if (form.controls.title.touched && form.controls.title.invalid) {
            <mat-error>Give the role a title</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Department</mat-label>
          <mat-select formControlName="department_id">
            @for (d of departments; track d.id) {
              <mat-option [value]="d.id">{{ d.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Location</mat-label>
          <input matInput formControlName="location" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select formControlName="status">
            <mat-option value="draft">Draft</mat-option>
            <mat-option value="open">Open</mat-option>
            <mat-option value="on_hold">On hold</mat-option>
            <mat-option value="closed">Closed</mat-option>
            <mat-option value="filled">Filled</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Employment type</mat-label>
          <mat-select formControlName="employment_type">
            <mat-option value="full_time">Full time</mat-option>
            <mat-option value="part_time">Part time</mat-option>
            <mat-option value="contract">Contract</mat-option>
            <mat-option value="intern">Intern</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Openings</mat-label>
          <input matInput type="number" min="1" formControlName="openings" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Target close date</mat-label>
          <input matInput [matDatepicker]="picker" formControlName="target_close_date" />
          <mat-datepicker-toggle matIconSuffix [for]="picker" />
          <mat-datepicker #picker />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Experience from (years)</mat-label>
          <input matInput type="number" min="0" formControlName="experience_min" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Experience to (years)</mat-label>
          <input matInput type="number" min="0" formControlName="experience_max" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Salary from (annual)</mat-label>
          <input matInput type="number" min="0" formControlName="salary_min" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Salary to (annual)</mat-label>
          <input matInput type="number" min="0" formControlName="salary_max" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Hiring manager</mat-label>
          <mat-select formControlName="hiring_manager_id">
            @for (u of managers; track u.id) {
              <mat-option [value]="u.id">{{ u.full_name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Recruiter</mat-label>
          <mat-select formControlName="recruiter_id">
            @for (u of recruiters; track u.id) {
              <mat-option [value]="u.id">{{ u.full_name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full">
          <mat-label>Must-have skills</mat-label>
          <input matInput formControlName="skills" placeholder="python, fastapi, postgresql" />
          <mat-hint>Comma separated. Used to score candidate matches.</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full">
          <mat-label>Description</mat-label>
          <textarea matInput rows="4" formControlName="description"></textarea>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="saving" (click)="save()">
        {{ data.job ? 'Save changes' : 'Create requisition' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 620px; max-width: 720px; padding-top: 8px; }
    @media (max-width: 700px) { mat-dialog-content { min-width: auto; } }
  `],
})
export class JobFormDialog {
  ref = inject(MatDialogRef<JobFormDialog>);
  data = inject<{ job?: Job }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  departments: Department[] = [];
  managers: User[] = [];
  recruiters: User[] = [];
  saving = false;

  form = this.fb.group({
    title: [this.data.job?.title ?? '', [Validators.required, Validators.minLength(2)]],
    description: [this.data.job?.description ?? ''],
    location: [this.data.job?.location ?? ''],
    status: [this.data.job?.status ?? 'draft'],
    employment_type: [this.data.job?.employment_type ?? 'full_time'],
    openings: [this.data.job?.openings ?? 1, [Validators.required, Validators.min(1)]],
    experience_min: [this.data.job?.experience_min ?? null],
    experience_max: [this.data.job?.experience_max ?? null],
    salary_min: [this.data.job?.salary_min ?? null],
    salary_max: [this.data.job?.salary_max ?? null],
    skills: [this.data.job?.skills ?? ''],
    department_id: [this.data.job?.department_id ?? null],
    hiring_manager_id: [this.data.job?.hiring_manager_id ?? null],
    recruiter_id: [this.data.job?.recruiter_id ?? null],
    target_close_date: [
      this.data.job?.target_close_date ? new Date(this.data.job.target_close_date) : null,
    ],
  });

  constructor() {
    this.api.departments().subscribe((d) => (this.departments = d));
    this.api.users({ page_size: 200, is_active: true }).subscribe((res) => {
      this.managers = res.items.filter((u) =>
        ['hiring_manager', 'admin', 'hr_manager'].includes(u.role),
      );
      this.recruiters = res.items.filter((u) =>
        ['recruiter', 'hr_manager', 'admin'].includes(u.role),
      );
    });
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving = true;
    const raw = this.form.getRawValue();
    const payload: Record<string, unknown> = { ...raw };

    if (raw.target_close_date instanceof Date) {
      payload['target_close_date'] = raw.target_close_date.toISOString().slice(0, 10);
    } else {
      delete payload['target_close_date'];
    }
    for (const key of Object.keys(payload)) {
      if (payload[key] === '' || payload[key] === null) delete payload[key];
    }

    const request = this.data.job
      ? this.api.updateJob(this.data.job.id, payload as Partial<Job>)
      : this.api.createJob(payload as Partial<Job>);

    request.subscribe({
      next: (job) => this.ref.close(job),
      error: () => (this.saving = false),
    });
  }
}
