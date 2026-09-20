import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { provideNativeDateAdapter } from '@angular/material/core';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ApiService } from '../../core/api.service';
import { Application, User } from '../../core/models';

const ROUNDS = [
  'Screening call',
  'Technical round 1',
  'Technical round 2',
  'System design',
  'Assignment review',
  'Managerial round',
  'HR discussion',
];

@Component({
  selector: 'app-schedule-dialog',
  standalone: true,
  providers: [provideNativeDateAdapter()],
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatDatepickerModule,
  ],
  template: `
    <h2 mat-dialog-title>Schedule an interview</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form-grid">
        <mat-form-field appearance="outline" class="full">
          <mat-label>Candidate and requisition</mat-label>
          <mat-select formControlName="application_id">
            @for (a of applications(); track a.id) {
              <mat-option [value]="a.id">
                {{ a.candidate.full_name }} — {{ a.job.code }} {{ a.job.title }}
              </mat-option>
            }
          </mat-select>
          @if (form.controls.application_id.touched && form.controls.application_id.invalid) {
            <mat-error>Pick who is being interviewed</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Round</mat-label>
          <mat-select formControlName="round_name">
            @for (r of rounds; track r) { <mat-option [value]="r">{{ r }}</mat-option> }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Mode</mat-label>
          <mat-select formControlName="mode">
            <mat-option value="video">Video</mat-option>
            <mat-option value="phone">Phone</mat-option>
            <mat-option value="onsite">Onsite</mat-option>
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Date</mat-label>
          <input matInput [matDatepicker]="picker" formControlName="date" [min]="today" />
          <mat-datepicker-toggle matIconSuffix [for]="picker" />
          <mat-datepicker #picker />
          @if (form.controls.date.touched && form.controls.date.invalid) {
            <mat-error>Choose a date</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Start time</mat-label>
          <input matInput type="time" formControlName="time" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Duration (minutes)</mat-label>
          <mat-select formControlName="duration_minutes">
            @for (d of durations; track d) { <mat-option [value]="d">{{ d }}</mat-option> }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Panel</mat-label>
          <mat-select formControlName="panelist_ids" multiple>
            @for (u of panelists(); track u.id) {
              <mat-option [value]="u.id">{{ u.full_name }} — {{ u.title || u.role }}</mat-option>
            }
          </mat-select>
          <mat-hint>Anyone already booked at this time is rejected on save</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline" class="full">
          <mat-label>Meeting link or room</mat-label>
          <input matInput formControlName="location_or_link" />
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="saving" (click)="save()">
        Schedule and notify
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 580px; max-width: 660px; padding-top: 8px; }
    @media (max-width: 640px) { mat-dialog-content { min-width: auto; } }
  `],
})
export class ScheduleDialog {
  ref = inject(MatDialogRef<ScheduleDialog>);
  data = inject<{ applicationId?: number }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  rounds = ROUNDS;
  durations = [30, 45, 60, 90, 120];
  today = new Date();
  applications = signal<Application[]>([]);
  panelists = signal<User[]>([]);
  saving = false;

  form = this.fb.group({
    application_id: [this.data.applicationId ?? null, [Validators.required]],
    round_name: ['Technical round 1', [Validators.required]],
    mode: ['video', [Validators.required]],
    date: [null as Date | null, [Validators.required]],
    time: ['11:00', [Validators.required]],
    duration_minutes: [45, [Validators.required]],
    panelist_ids: [[] as number[]],
    location_or_link: [''],
  });

  constructor() {
    // Only candidates still in play can be interviewed.
    this.api.applications({ page_size: 200 }).subscribe((res) =>
      this.applications.set(res.items.filter((a) => !['hired', 'rejected'].includes(a.stage))),
    );
    this.api
      .users({ page_size: 200, is_active: true })
      .subscribe((res) => this.panelists.set(res.items));
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const v = this.form.getRawValue();
    const [hours, minutes] = (v.time ?? '11:00').split(':').map(Number);
    const start = new Date(v.date!);
    start.setHours(hours, minutes, 0, 0);

    if (start.getTime() <= Date.now()) {
      this.form.controls.date.setErrors({ past: true });
      return;
    }

    this.saving = true;
    this.api
      .scheduleInterview({
        application_id: Number(v.application_id),
        round_name: v.round_name!,
        scheduled_at: start.toISOString(),
        duration_minutes: Number(v.duration_minutes),
        mode: v.mode!,
        location_or_link: v.location_or_link || undefined,
        panelist_ids: v.panelist_ids ?? [],
      })
      .subscribe({
        next: (iv) => this.ref.close(iv),
        error: () => (this.saving = false),
      });
  }
}
