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
import { lakhs } from '../../core/format';
import { Application, Offer } from '../../core/models';

@Component({
  selector: 'app-offer-form-dialog',
  standalone: true,
  providers: [provideNativeDateAdapter()],
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatDatepickerModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.offer ? 'Edit offer' : 'Raise an offer' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form-grid">
        @if (!data.offer) {
          <mat-form-field appearance="outline" class="full">
            <mat-label>Candidate and requisition</mat-label>
            <mat-select formControlName="application_id">
              @for (a of eligible(); track a.id) {
                <mat-option [value]="a.id">
                  {{ a.candidate.full_name }} — {{ a.job.code }} {{ a.job.title }}
                </mat-option>
              }
            </mat-select>
            <mat-hint>Candidates at assessment stage or beyond</mat-hint>
          </mat-form-field>
        }

        <mat-form-field appearance="outline" class="full">
          <mat-label>Designation</mat-label>
          <input matInput formControlName="designation" />
          @if (form.controls.designation.touched && form.controls.designation.invalid) {
            <mat-error>Enter the offered designation</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Annual CTC</mat-label>
          <input matInput type="number" min="1" formControlName="annual_ctc" />
          <mat-hint>{{ preview(form.value.annual_ctc) }}</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Fixed component</mat-label>
          <input matInput type="number" min="0" formControlName="fixed_component" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Variable component</mat-label>
          <input matInput type="number" min="0" formControlName="variable_component" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Joining bonus</mat-label>
          <input matInput type="number" min="0" formControlName="joining_bonus" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Joining date</mat-label>
          <input matInput [matDatepicker]="joining" formControlName="joining_date" />
          <mat-datepicker-toggle matIconSuffix [for]="joining" />
          <mat-datepicker #joining />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Offer valid till</mat-label>
          <input matInput [matDatepicker]="valid" formControlName="valid_till" />
          <mat-datepicker-toggle matIconSuffix [for]="valid" />
          <mat-datepicker #valid />
        </mat-form-field>

        <mat-form-field appearance="outline" class="full">
          <mat-label>Internal notes</mat-label>
          <textarea matInput rows="2" formControlName="notes"></textarea>
        </mat-form-field>
      </form>

      @if (splitError()) { <p class="error-text">{{ splitError() }}</p> }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="saving" (click)="save()">
        {{ data.offer ? 'Save changes' : 'Create draft offer' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 560px; max-width: 640px; padding-top: 8px; }
    @media (max-width: 620px) { mat-dialog-content { min-width: auto; } }
  `],
})
export class OfferFormDialog {
  ref = inject(MatDialogRef<OfferFormDialog>);
  data = inject<{ offer?: Offer; applicationId?: number }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  eligible = signal<Application[]>([]);
  saving = false;

  form = this.fb.group({
    application_id: [this.data.offer?.application_id ?? this.data.applicationId ?? null, [Validators.required]],
    designation: [this.data.offer?.designation ?? '', [Validators.required, Validators.minLength(2)]],
    annual_ctc: [this.data.offer?.annual_ctc ?? null, [Validators.required, Validators.min(1)]],
    fixed_component: [this.data.offer?.fixed_component ?? null],
    variable_component: [this.data.offer?.variable_component ?? null],
    joining_bonus: [this.data.offer?.joining_bonus ?? null],
    joining_date: [this.data.offer?.joining_date ? new Date(this.data.offer.joining_date) : null],
    valid_till: [this.data.offer?.valid_till ? new Date(this.data.offer.valid_till) : null],
    notes: [this.data.offer?.notes ?? ''],
  });

  constructor() {
    if (!this.data.offer) {
      this.api.applications({ page_size: 200 }).subscribe((res) =>
        this.eligible.set(
          res.items.filter((a) => ['assessment', 'interview', 'offer'].includes(a.stage)),
        ),
      );
    }
  }

  preview(value: unknown): string {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? lakhs(n) : 'Annual figure in rupees';
  }

  /** Mirrors the server rule so the user finds out before saving. */
  splitError(): string {
    const { annual_ctc, fixed_component, variable_component } = this.form.value;
    const total = Number(annual_ctc ?? 0);
    const fixed = Number(fixed_component ?? 0);
    const variable = Number(variable_component ?? 0);
    if (total > 0 && fixed + variable > total) {
      return 'Fixed plus variable is more than the annual CTC. Adjust the split.';
    }
    return '';
  }

  save(): void {
    if (this.form.invalid || this.splitError()) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving = true;
    const v = this.form.getRawValue();
    const payload: Record<string, unknown> = { ...v };

    for (const key of ['joining_date', 'valid_till']) {
      const value = payload[key];
      payload[key] = value instanceof Date ? value.toISOString().slice(0, 10) : undefined;
    }
    for (const key of Object.keys(payload)) {
      if (payload[key] === '' || payload[key] === null || payload[key] === undefined) {
        delete payload[key];
      }
    }

    const request = this.data.offer
      ? this.api.updateOffer(this.data.offer.id, payload as Partial<Offer>)
      : this.api.createOffer(
          payload as Partial<Offer> & {
            application_id: number; designation: string; annual_ctc: number;
          },
        );

    request.subscribe({
      next: (offer) => this.ref.close(offer),
      error: () => (this.saving = false),
    });
  }
}
