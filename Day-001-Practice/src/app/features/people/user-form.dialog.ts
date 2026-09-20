import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { ApiService } from '../../core/api.service';
import { Department, ROLE_LABELS, Role, User } from '../../core/models';

@Component({
  selector: 'app-user-form-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatButtonModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data.user ? 'Edit team member' : 'Add team member' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form-grid">
        <mat-form-field appearance="outline">
          <mat-label>Full name</mat-label>
          <input matInput formControlName="full_name" />
          @if (form.controls.full_name.touched && form.controls.full_name.invalid) {
            <mat-error>Enter their name</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Work email</mat-label>
          <input matInput type="email" formControlName="email" />
          @if (form.controls.email.touched && form.controls.email.invalid) {
            <mat-error>Enter a valid email address</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Role</mat-label>
          <mat-select formControlName="role">
            @for (r of roles; track r) { <mat-option [value]="r">{{ roleLabel(r) }}</mat-option> }
          </mat-select>
          <mat-hint>{{ roleHint() }}</mat-hint>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Department</mat-label>
          <mat-select formControlName="department_id">
            <mat-option [value]="null">None</mat-option>
            @for (d of departments; track d.id) {
              <mat-option [value]="d.id">{{ d.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Job title</mat-label>
          <input matInput formControlName="title" />
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Phone</mat-label>
          <input matInput formControlName="phone" />
        </mat-form-field>

        @if (!data.user) {
          <mat-form-field appearance="outline" class="full">
            <mat-label>Temporary password</mat-label>
            <input matInput formControlName="password" />
            @if (form.controls.password.touched && form.controls.password.invalid) {
              <mat-error>At least 8 characters</mat-error>
            }
            <mat-hint>They can change it after signing in</mat-hint>
          </mat-form-field>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="ref.close()">Cancel</button>
      <button mat-flat-button color="primary" type="button" [disabled]="saving" (click)="save()">
        {{ data.user ? 'Save changes' : 'Add member' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    mat-dialog-content { min-width: 520px; max-width: 600px; padding-top: 8px; }
    @media (max-width: 580px) { mat-dialog-content { min-width: auto; } }
  `],
})
export class UserFormDialog {
  ref = inject(MatDialogRef<UserFormDialog>);
  data = inject<{ user?: User }>(MAT_DIALOG_DATA);
  private api = inject(ApiService);
  private fb = inject(FormBuilder);

  roles: Role[] = ['admin', 'hr_manager', 'recruiter', 'hiring_manager', 'interviewer'];
  departments: Department[] = [];
  saving = false;

  form = this.fb.group({
    full_name: [this.data.user?.full_name ?? '', [Validators.required, Validators.minLength(2)]],
    email: [this.data.user?.email ?? '', [Validators.required, Validators.email]],
    role: [this.data.user?.role ?? ('recruiter' as Role), [Validators.required]],
    title: [this.data.user?.title ?? ''],
    phone: [this.data.user?.phone ?? ''],
    department_id: [this.data.user?.department_id ?? null],
    password: ['', this.data.user ? [] : [Validators.required, Validators.minLength(8)]],
  });

  constructor() {
    this.api.departments().subscribe((d) => (this.departments = d));
    if (this.data.user) this.form.controls.email.disable();
  }

  roleLabel(role: Role): string {
    return ROLE_LABELS[role];
  }

  roleHint(): string {
    return {
      admin: 'Full access, including managing the team',
      hr_manager: 'Everything except team management; can approve offers',
      recruiter: 'Requisitions, candidates, pipeline and interviews',
      hiring_manager: 'Can move candidates through the pipeline',
      interviewer: 'Sees their own panels and submits feedback',
    }[this.form.value.role ?? 'recruiter'];
  }

  save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving = true;
    const raw = this.form.getRawValue();

    if (this.data.user) {
      const payload: Partial<User> = {
        full_name: raw.full_name!,
        role: raw.role!,
        title: raw.title || null,
        phone: raw.phone || null,
        department_id: raw.department_id ?? null,
      };
      this.api.updateUser(this.data.user.id, payload).subscribe({
        next: (user) => this.ref.close(user),
        error: () => (this.saving = false),
      });
      return;
    }

    this.api
      .createUser({
        email: raw.email!,
        full_name: raw.full_name!,
        role: raw.role!,
        title: raw.title || null,
        phone: raw.phone || null,
        department_id: raw.department_id ?? null,
        password: raw.password!,
      })
      .subscribe({
        next: (user) => this.ref.close(user),
        error: () => (this.saving = false),
      });
  }
}
