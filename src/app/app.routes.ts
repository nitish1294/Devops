import { Routes } from '@angular/router';

import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        title: 'Dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      {
        path: 'pipeline',
        title: 'Pipeline',
        loadComponent: () =>
          import('./features/pipeline/pipeline.component').then((m) => m.PipelineComponent),
      },
      {
        path: 'jobs',
        title: 'Requisitions',
        loadComponent: () => import('./features/jobs/jobs.component').then((m) => m.JobsComponent),
      },
      {
        path: 'jobs/:id',
        title: 'Requisition',
        loadComponent: () =>
          import('./features/jobs/job-detail.component').then((m) => m.JobDetailComponent),
      },
      {
        path: 'candidates',
        title: 'Candidates',
        loadComponent: () =>
          import('./features/candidates/candidates.component').then((m) => m.CandidatesComponent),
      },
      {
        path: 'candidates/:id',
        title: 'Candidate',
        loadComponent: () =>
          import('./features/candidates/candidate-detail.component').then(
            (m) => m.CandidateDetailComponent,
          ),
      },
      {
        path: 'interviews',
        title: 'Interviews',
        loadComponent: () =>
          import('./features/interviews/interviews.component').then((m) => m.InterviewsComponent),
      },
      {
        path: 'offers',
        title: 'Offers',
        loadComponent: () =>
          import('./features/offers/offers.component').then((m) => m.OffersComponent),
      },
      {
        path: 'people',
        title: 'Team',
        loadComponent: () =>
          import('./features/people/people.component').then((m) => m.PeopleComponent),
      },
      {
        path: 'settings',
        title: 'Email templates',
        loadComponent: () =>
          import('./features/settings/settings.component').then((m) => m.SettingsComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
