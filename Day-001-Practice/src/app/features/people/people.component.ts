import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subject, debounceTime } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { day } from '../../core/format';
import { Department, ROLE_LABELS, Role, User } from '../../core/models';
import { UserFormDialog } from './user-form.dialog';

@Component({
  selector: 'app-people',
  standalone: true,
  imports: [
    FormsModule, MatButtonModule, MatIconModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatMenuModule, MatProgressBarModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Team</h1>
          <p>Who can use this system, and what each role is allowed to do.</p>
        </div>
        @if (isAdmin) {
          <div class="actions">
            <button mat-stroked-button type="button" (click)="addDepartment()">
              <mat-icon>domain_add</mat-icon>
              New department
            </button>
            <button mat-flat-button color="primary" type="button" (click)="create()">
              <mat-icon>person_add</mat-icon>
              Add member
            </button>
          </div>
        }
      </div>

      <div class="toolbar">
        <mat-form-field appearance="outline" class="search">
          <mat-label>Search name or email</mat-label>
          <input matInput [(ngModel)]="query" (ngModelChange)="search$.next()" />
          <mat-icon matSuffix>search</mat-icon>
        </mat-form-field>
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Role</mat-label>
          <mat-select [(ngModel)]="role" (ngModelChange)="reload()">
            <mat-option [value]="null">All roles</mat-option>
            @for (r of roles; track r) { <mat-option [value]="r">{{ roleLabel(r) }}</mat-option> }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Status</mat-label>
          <mat-select [(ngModel)]="activeOnly" (ngModelChange)="reload()">
            <mat-option [value]="true">Active</mat-option>
            <mat-option [value]="false">Deactivated</mat-option>
            <mat-option [value]="null">Everyone</mat-option>
          </mat-select>
        </mat-form-field>
        <span class="spacer"></span>
        <span class="muted small">{{ total() }} members</span>
      </div>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      <div class="card">
        <table class="data">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Department</th>
              <th>Title</th>
              <th>Phone</th>
              <th>Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (u of users(); track u.id) {
              <tr [class.inactive]="!u.is_active">
                <td>
                  <span class="strong">{{ u.full_name }}</span>
                  <div class="muted small">{{ u.email }}</div>
                </td>
                <td><span class="pill" [class]="roleClass(u.role)">{{ roleLabel(u.role) }}</span></td>
                <td class="small">{{ u.department?.name || '—' }}</td>
                <td class="small">{{ u.title || '—' }}</td>
                <td class="small">{{ u.phone || '—' }}</td>
                <td class="small">{{ dayOf(u.created_at) }}</td>
                <td>
                  @if (isAdmin) {
                    <button mat-icon-button type="button" [matMenuTriggerFor]="menu"
                            aria-label="Member actions">
                      <mat-icon>more_vert</mat-icon>
                    </button>
                    <mat-menu #menu="matMenu">
                      <button mat-menu-item type="button" (click)="edit(u)">
                        <mat-icon>edit</mat-icon> Edit
                      </button>
                      @if (u.is_active && u.id !== me?.id) {
                        <button mat-menu-item type="button" (click)="deactivate(u)">
                          <mat-icon>person_off</mat-icon> Deactivate
                        </button>
                      }
                      @if (!u.is_active) {
                        <button mat-menu-item type="button" (click)="reactivate(u)">
                          <mat-icon>how_to_reg</mat-icon> Reactivate
                        </button>
                      }
                    </mat-menu>
                  }
                </td>
              </tr>
            } @empty {
              <tr><td colspan="7" class="muted">No team members match this view.</td></tr>
            }
          </tbody>
        </table>
      </div>

      <section class="card panel">
        <h2>Departments</h2>
        @if (departments().length) {
          <ul class="depts">
            @for (d of departments(); track d.id) {
              <li>
                <span class="strong">{{ d.name }}</span>
                <span class="muted small">{{ d.location || 'No location' }}</span>
              </li>
            }
          </ul>
        } @else {
          <p class="muted small">No departments yet.</p>
        }
      </section>
    </div>
  `,
  styles: [`
    .search { width: 280px; }
    .narrow { width: 170px; }
    .actions { display: flex; gap: 8px; }
    tr.inactive td { opacity: 0.55; }
    .panel { padding: 16px 18px; margin-top: 16px; }
    .panel h2 { font-size: 15px; margin-bottom: 10px; }
    .depts { list-style: none; margin: 0; padding: 0;
             display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
    .depts li { display: flex; flex-direction: column;
                border-left: 2px solid var(--accent); padding-left: 10px; }
  `],
})
export class PeopleComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  users = signal<User[]>([]);
  departments = signal<Department[]>([]);
  total = signal(0);
  loading = signal(false);

  query = '';
  role: Role | null = null;
  activeOnly: boolean | null = true;
  roles: Role[] = ['admin', 'hr_manager', 'recruiter', 'hiring_manager', 'interviewer'];
  isAdmin = this.auth.can('manage_users');
  me = this.auth.user();
  search$ = new Subject<void>();

  ngOnInit(): void {
    this.search$.pipe(debounceTime(300)).subscribe(() => this.reload());
    this.reload();
    this.loadDepartments();
  }

  reload(): void {
    this.loading.set(true);
    this.api
      .users({
        q: this.query || undefined,
        role: this.role ?? undefined,
        is_active: this.activeOnly ?? undefined,
        page_size: 100,
      })
      .subscribe({
        next: (res) => {
          this.users.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  private loadDepartments(): void {
    this.api.departments().subscribe((d) => this.departments.set(d));
  }

  create(): void {
    this.dialog
      .open(UserFormDialog, { data: {} })
      .afterClosed()
      .subscribe((user) => {
        if (user) {
          this.snack.open(`${user.full_name} added`, 'Dismiss', { duration: 3500 });
          this.reload();
        }
      });
  }

  edit(user: User): void {
    this.dialog
      .open(UserFormDialog, { data: { user } })
      .afterClosed()
      .subscribe((updated) => {
        if (updated) {
          this.snack.open('Member updated', 'Dismiss', { duration: 3000 });
          this.reload();
        }
      });
  }

  deactivate(user: User): void {
    this.api.deactivateUser(user.id).subscribe((res) => {
      this.snack.open(res.detail, 'Dismiss', { duration: 3000 });
      this.reload();
    });
  }

  reactivate(user: User): void {
    this.api.updateUser(user.id, { is_active: true }).subscribe(() => {
      this.snack.open(`${user.full_name} reactivated`, 'Dismiss', { duration: 3000 });
      this.reload();
    });
  }

  addDepartment(): void {
    const name = window.prompt('Department name');
    if (!name?.trim()) return;
    const location = window.prompt('Location (optional)') ?? '';
    this.api.createDepartment({ name: name.trim(), location: location.trim() }).subscribe(() => {
      this.snack.open('Department created', 'Dismiss', { duration: 3000 });
      this.loadDepartments();
    });
  }

  roleLabel(role: Role): string {
    return ROLE_LABELS[role];
  }

  roleClass(role: Role): string {
    return {
      admin: 'stage-rejected',
      hr_manager: 'stage-assessment',
      recruiter: 'stage-screening',
      hiring_manager: 'stage-interview',
      interviewer: 'stage-sourced',
    }[role];
  }

  dayOf(value?: string | null): string {
    return day(value);
  }
}
