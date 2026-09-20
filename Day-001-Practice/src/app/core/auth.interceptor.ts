import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { catchError, switchMap, throwError } from 'rxjs';

import { AuthService } from './auth.service';

const AUTH_FREE = ['/auth/login', '/auth/refresh'];

/** Attaches the bearer token, refreshes it on expiry, and makes errors readable. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const snack = inject(MatSnackBar);

  const withToken = (request: HttpRequest<unknown>) => {
    const token = auth.token;
    return token
      ? request.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : request;
  };

  const isAuthCall = AUTH_FREE.some((path) => req.url.includes(path));

  return next(withToken(req)).pipe(
    catchError((error: HttpErrorResponse) => {
      // An expired access token is recoverable: swap it and replay the request
      // once. Only once — a second 401 means the refresh token is finished too.
      if (error.status === 401 && !isAuthCall && auth.refreshToken) {
        return auth.refresh().pipe(
          switchMap(() => next(withToken(req))),
          catchError(() => {
            auth.logout();
            snack.open('Your session ended. Sign in again.', 'Dismiss', { duration: 6000 });
            return throwError(() => error);
          }),
        );
      }

      let message = 'Something went wrong. Try again.';

      if (error.status === 0) {
        message = 'Cannot reach the server. Check that the API is running.';
      } else if (error.status === 401 && !isAuthCall) {
        auth.logout();
        message = 'Your session ended. Sign in again.';
      } else if (error.status === 429) {
        message = error.error?.detail ?? 'Too many attempts. Wait a moment and try again.';
      } else if (error.error?.problems?.length) {
        const first = error.error.problems[0];
        message = `${first.field}: ${first.message}`;
      } else if (typeof error.error?.detail === 'string') {
        message = error.error.detail;
        // The request id is what ties a user's report to a line in the log.
        if (error.status >= 500 && error.error?.request_id) {
          message += ` (ref ${String(error.error.request_id).slice(0, 8)})`;
        }
      }

      if (!req.url.includes('/auth/login')) {
        snack.open(message, 'Dismiss', { duration: 6000 });
      }
      return throwError(() => ({ ...error, message }));
    }),
  );
};
