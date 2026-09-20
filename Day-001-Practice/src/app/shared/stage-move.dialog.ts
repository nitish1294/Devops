import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

export interface StageMoveData {
  candidateName: string;
  toLabel: string;
  requiresReason: boolean;
}

const REASONS = [
  'Skills did not match the requirement',
  'Compensation expectations out of range',
  'Notice period too long',
  'Withdrew from the process',
  'Position filled by another candidate',
  'Communication or culture fit',
];

/** Asked whenever a move needs a human explanation - rejections always do. */
@Component({
  selector: 'app-stage-move-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
  ],
  template: `
    <h2 mat-dialog-title>Move to {{ data.toLabel }}</h2>
    <mat-dialog-content>
      <p class="muted small">{{ data.candidateName }}</p>
      <form [formGroup]="form">
        @if (data.requiresReason) {
          <mat-form-field appearance="outline">
            <mat-label>Reason</mat-label>
            <mat-select formControlName="rejection_reason">
              @for (r of reasons; track r) { <mat-option [value]="r">{{ r }}</mat-option> }
            </mat-select>
            <mat-hint>Recorded on the candidate's timeline</mat-hint>
          </mat-form-field>
        }
        <mat-form-field appearance="outline">
          <mat-label>Note (optional)</mat-label>
          <textarea matInput rows="3" formControlName="note"></textarea>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button
        mat-flat-button
        color="primary"
        type="button"
        [disabled]="data.requiresReason && !form.value.rejection_reason"
        (click)="confirm()"
      >
        Move to {{ data.toLabel }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 340px; padding-top: 6px; }
    form { display: flex; flex-direction: column; margin-top: 10px; }
    mat-form-field { width: 100%; }
  `],
})
export class StageMoveDialog {
  ref = inject(MatDialogRef<StageMoveDialog>);
  data = inject<StageMoveData>(MAT_DIALOG_DATA);
  private fb = inject(FormBuilder);

  reasons = REASONS;
  form = this.fb.nonNullable.group({ rejection_reason: [''], note: [''] });

  confirm(): void {
    const value = this.form.getRawValue();
    this.ref.close({
      note: value.note || undefined,
      rejection_reason: this.data.requiresReason ? value.rejection_reason : undefined,
    });
  }
}
