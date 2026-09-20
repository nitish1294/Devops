import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, shareReplay, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import { AuthResponse, Role, User } from './models';

const TOKEN_KEY = 'hrms.token';
const REFRESH_KEY = 'hrms.refresh';
const USER_KEY = 'hrms.user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  readonly user = signal<User | null>(this.restoreUser());
  readonly isLoggedIn = computed(() => this.user() !== null);
  readonly role = computed<Role | null>(() => this.user()?.role ?? null);

  /** Shared so a burst of parallel 401s triggers one refresh, not five. */
  private refreshInFlight: Observable<AuthResponse> | null = null;

  private restoreUser(): User | null {
    try {
      const raw = sessionStorage.getItem(USER_KEY);
      return raw ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  }

  private read(key: string): string | null {
    try {
      return sessionStorage.getItem(key);
    } catch {
      return null;
    }
  }

  get token(): string | null {
    return this.read(TOKEN_KEY);
  }

  get refreshToken(): string | null {
    return this.read(REFRESH_KEY);
  }

  private store(res: AuthResponse): void {
    try {
      sessionStorage.setItem(TOKEN_KEY, res.access_token);
      sessionStorage.setItem(REFRESH_KEY, res.refresh_token);
      sessionStorage.setItem(USER_KEY, JSON.stringify(res.user));
    } catch {
      // Private browsing can refuse storage; the session still works in memory.
    }
    this.user.set(res.user);
  }

  login(email: string, password: string) {
    return this.http
      .post<AuthResponse>(`${environment.apiUrl}/auth/login`, { email, password })
      .pipe(tap((res) => this.store(res)));
  }

  /**
   * Swap the refresh token for a new pair. Access tokens last an hour, so
   * without this a recruiter working through a morning of screening would be
   * kicked out mid-task.
   */
  refresh(): Observable<AuthResponse> {
    if (this.refreshInFlight) return this.refreshInFlight;

    this.refreshInFlight = this.http
      .post<AuthResponse>(`${environment.apiUrl}/auth/refresh`, {
        refresh_token: this.refreshToken ?? '',
      })
      .pipe(
        tap({
          next: (res) => {
            this.store(res);
            this.refreshInFlight = null;
          },
          error: () => {
            this.refreshInFlight = null;
          },
        }),
        shareReplay(1),
      );

    return this.refreshInFlight;
  }

  changePassword(current_password: string, new_password: string) {
    return this.http.post<{ detail: string }>(
      `${environment.apiUrl}/auth/change-password`,
      { current_password, new_password },
    );
  }

  logout(): void {
    for (const key of [TOKEN_KEY, REFRESH_KEY, USER_KEY]) {
      try {
        sessionStorage.removeItem(key);
      } catch {
        /* nothing to clear */
      }
    }
    this.refreshInFlight = null;
    this.user.set(null);
    void this.router.navigate(['/login']);
  }

  /** Mirrors the server-side role guards so the UI hides what the API would refuse. */
  can(action: 'manage_users' | 'manage_jobs' | 'manage_offers' | 'move_pipeline'): boolean {
    const role = this.role();
    if (!role) return false;
    switch (action) {
      case 'manage_users':
        return role === 'admin';
      case 'manage_jobs':
        return ['admin', 'hr_manager', 'recruiter'].includes(role);
      case 'manage_offers':
        return ['admin', 'hr_manager'].includes(role);
      case 'move_pipeline':
        return ['admin', 'hr_manager', 'recruiter', 'hiring_manager'].includes(role);
    }
  }
}
