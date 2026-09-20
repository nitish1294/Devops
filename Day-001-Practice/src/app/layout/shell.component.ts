import { Component, computed, inject } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { ROLE_LABELS } from '../core/models';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  adminOnly?: boolean;
}

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, MatIconModule, MatMenuModule],
  template: `
    <div class="frame">
      <nav class="rail" aria-label="Main navigation">
        <div class="brand">
          <span class="mark" aria-hidden="true">TP</span>
          <span class="brand-text">
            <strong>Talent Pipeline</strong>
            <small>Recruitment console</small>
          </span>
        </div>

        <ul class="nav">
          @for (item of visibleNav(); track item.path) {
            <li>
              <a [routerLink]="item.path" routerLinkActive="active">
                <mat-icon>{{ item.icon }}</mat-icon>
                <span>{{ item.label }}</span>
              </a>
            </li>
          }
        </ul>

        <button class="who" [matMenuTriggerFor]="accountMenu" type="button">
          <span class="avatar" aria-hidden="true">{{ initials() }}</span>
          <span class="who-text">
            <strong>{{ user()?.full_name }}</strong>
            <small>{{ roleLabel() }}</small>
          </span>
          <mat-icon>expand_more</mat-icon>
        </button>
        <mat-menu #accountMenu="matMenu">
          <button mat-menu-item disabled>{{ user()?.email }}</button>
          <button mat-menu-item type="button" (click)="auth.logout()">
            <mat-icon>logout</mat-icon>
            Sign out
          </button>
        </mat-menu>
      </nav>

      <main class="content">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    .frame { display: flex; min-height: 100vh; }

    .rail {
      width: var(--rail-width);
      flex: 0 0 var(--rail-width);
      background: var(--ink);
      color: #cdd8e3;
      display: flex;
      flex-direction: column;
      padding: 18px 12px 12px;
      position: sticky;
      top: 0;
      height: 100vh;
    }

    .brand { display: flex; gap: 10px; align-items: center; padding: 0 8px 20px; }
    .mark {
      width: 32px; height: 32px; flex: 0 0 32px;
      display: grid; place-items: center;
      background: var(--accent); color: #fff;
      border-radius: 7px; font-weight: 700; font-size: 13px;
    }
    .brand-text { display: flex; flex-direction: column; line-height: 1.25; }
    .brand-text strong { color: #fff; font-size: 14px; }
    .brand-text small { color: #7d90a3; font-size: 11.5px; }

    .nav { list-style: none; margin: 0; padding: 0; flex: 1; overflow-y: auto; }
    .nav a {
      display: flex; align-items: center; gap: 11px;
      padding: 9px 10px; margin-bottom: 2px;
      border-radius: var(--radius);
      color: #cdd8e3; font-size: 13.5px; font-weight: 500;
      text-decoration: none;
    }
    .nav a:hover { background: var(--ink-soft); color: #fff; text-decoration: none; }
    .nav a.active { background: var(--accent); color: #fff; }
    .nav mat-icon { font-size: 19px; width: 19px; height: 19px; }

    .who {
      display: flex; align-items: center; gap: 10px;
      width: 100%; padding: 9px 10px; margin-top: 8px;
      background: var(--ink-soft); border: none;
      border-radius: var(--radius); color: #cdd8e3;
      cursor: pointer; text-align: left; font: inherit;
    }
    .who:hover { background: #26394c; }
    .avatar {
      width: 28px; height: 28px; flex: 0 0 28px;
      display: grid; place-items: center;
      background: #3d566e; color: #fff;
      border-radius: 50%; font-size: 11.5px; font-weight: 600;
    }
    .who-text { flex: 1; display: flex; flex-direction: column; min-width: 0; line-height: 1.25; }
    .who-text strong {
      color: #fff; font-size: 13px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .who-text small { color: #7d90a3; font-size: 11px; }
    .who mat-icon { font-size: 18px; width: 18px; height: 18px; }

    .content { flex: 1; min-width: 0; }

    @media (max-width: 900px) {
      .frame { flex-direction: column; }
      .rail { width: 100%; flex: none; height: auto; position: static; }
      .nav { display: flex; flex-wrap: wrap; gap: 4px; }
      .nav a span { display: none; }
      .brand-text, .who-text { display: none; }
      .who { width: auto; }
    }
  `],
})
export class ShellComponent {
  auth = inject(AuthService);
  user = this.auth.user;

  private nav: NavItem[] = [
    { path: '/dashboard', label: 'Dashboard', icon: 'insights' },
    { path: '/pipeline', label: 'Pipeline', icon: 'view_kanban' },
    { path: '/jobs', label: 'Requisitions', icon: 'work_outline' },
    { path: '/candidates', label: 'Candidates', icon: 'groups' },
    { path: '/interviews', label: 'Interviews', icon: 'event_note' },
    { path: '/offers', label: 'Offers', icon: 'description' },
    { path: '/people', label: 'Team', icon: 'badge' },
    { path: '/settings', label: 'Templates', icon: 'mail_outline' },
  ];

  visibleNav = computed(() =>
    this.nav.filter((item) => !item.adminOnly || this.auth.can('manage_users')),
  );

  roleLabel = computed(() => {
    const role = this.auth.role();
    return role ? ROLE_LABELS[role] : '';
  });

  initials = computed(() => {
    const name = this.user()?.full_name ?? '';
    return name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join('');
  });
}
