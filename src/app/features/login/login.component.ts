import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatButtonModule, MatFormFieldModule,
    MatInputModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    <div class="split">
      <section class="pitch">
        <span class="mark" aria-hidden="true">TP</span>
        <h1>Talent Pipeline</h1>
        <p>
          Every requisition, candidate and interview in one place — from first
          screen to signed offer.
        </p>
        <dl class="facts">
          <div><dt>Requisitions</dt><dd>Track openings, owners and target close dates</dd></div>
          <div><dt>Pipeline</dt><dd>Drag candidates through seven stages, with full history</dd></div>
          <div><dt>Interviews</dt><dd>Schedule panels without double-booking anyone</dd></div>
          <div><dt>Offers</dt><dd>Draft, release and track acceptance</dd></div>
        </dl>
      </section>

      <section class="form-side">
        <div class="box">
          <h2>Sign in</h2>
          <p class="muted small">Use your work email.</p>

          @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

          <form [formGroup]="form" (ngSubmit)="submit()">
            <mat-form-field appearance="outline">
              <mat-label>Email</mat-label>
              <input matInput type="email" formControlName="email" autocomplete="username" />
              @if (form.controls.email.touched && form.controls.email.invalid) {
                <mat-error>Enter a valid email address</mat-error>
              }
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Password</mat-label>
              <input
                matInput
                [type]="reveal() ? 'text' : 'password'"
                formControlName="password"
                autocomplete="current-password"
              />
              <button
                mat-icon-button
                matSuffix
                type="button"
                (click)="reveal.set(!reveal())"
                [attr.aria-label]="reveal() ? 'Hide password' : 'Show password'"
              >
                <mat-icon>{{ reveal() ? 'visibility_off' : 'visibility' }}</mat-icon>
              </button>
              @if (form.controls.password.touched && form.controls.password.invalid) {
                <mat-error>Password is required</mat-error>
              }
            </mat-form-field>

            @if (error()) { <p class="error-text">{{ error() }}</p> }

            <button mat-flat-button color="primary" type="submit" [disabled]="loading()">
              Sign in
            </button>
          </form>

          <div class="demo">
            <span class="strong small">Demo accounts</span>
            <p class="small muted">Password for all: Password&#64;123</p>
            <ul class="small">
              @for (a of accounts; track a.email) {
                <li>
                  <button type="button" (click)="fill(a.email)">{{ a.email }}</button>
                  <span class="muted">{{ a.role }}</span>
                </li>
              }
            </ul>
          </div>
        </div>
      </section>
    </div>
  `,
  styles: [`
    .split { display: grid; grid-template-columns: 1.05fr 1fr; min-height: 100vh; }

    .pitch {
      background: var(--ink);
      color: #cdd8e3;
      padding: 56px 52px;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }
    .mark {
      width: 40px; height: 40px; display: grid; place-items: center;
      background: var(--accent); color: #fff; border-radius: 9px;
      font-weight: 700; margin-bottom: 22px;
    }
    .pitch h1 { color: #fff; font-size: 30px; }
    .pitch > p { max-width: 46ch; margin: 12px 0 34px; font-size: 15px; }

    .facts { margin: 0; display: grid; gap: 18px; }
    .facts div { border-left: 2px solid var(--accent); padding-left: 14px; }
    .facts dt { color: #fff; font-weight: 600; font-size: 13.5px; }
    .facts dd { margin: 2px 0 0; font-size: 13px; color: #93a5b8; max-width: 44ch; }

    .form-side { display: grid; place-items: center; padding: 40px 24px; background: var(--canvas); }
    .box {
      width: 100%; max-width: 380px; background: var(--paper);
      border: 1px solid var(--rule); border-radius: 10px; padding: 28px;
    }
    .box h2 { font-size: 19px; }
    .box > p { margin: 4px 0 18px; }
    form { display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
    form button[type='submit'] { margin-top: 10px; height: 42px; font-size: 14px; }

    .demo { margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--rule); }
    .demo p { margin: 2px 0 8px; }
    .demo ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }
    .demo li { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
    .demo li button {
      background: none; border: none; padding: 0; font: inherit;
      color: var(--accent); cursor: pointer; text-decoration: underline;
    }

    @media (max-width: 860px) {
      .split { grid-template-columns: 1fr; }
      .pitch { padding: 32px 24px; }
      .facts { display: none; }
    }
  `],
})
export class LoginComponent {
  private auth = inject(AuthService);
  private router = inject(Router);
  private fb = inject(FormBuilder);

  loading = signal(false);
  error = signal('');
  reveal = signal(false);

  accounts = [
    { email: 'admin@hrms.co', role: 'Admin' },
    { email: 'hr@hrms.co', role: 'HR manager' },
    { email: 'recruiter@hrms.co', role: 'Recruiter' },
    { email: 'dev1@hrms.co', role: 'Interviewer' },
  ];

  form = this.fb.nonNullable.group({
    email: ['admin@hrms.co', [Validators.required, Validators.email]],
    password: ['Password@123', [Validators.required]],
  });

  fill(email: string): void {
    this.form.patchValue({ email, password: 'Password@123' });
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.error.set('');
    const { email, password } = this.form.getRawValue();

    this.auth.login(email, password).subscribe({
      next: () => {
        this.loading.set(false);
        void this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err?.error?.detail ?? 'Email or password is incorrect');
      },
    });
  }
}
