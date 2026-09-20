import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { RouterLink } from '@angular/router';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ago, titleCase } from '../../core/format';
import { Activity, DashboardStats, Interview, STAGES } from '../../core/models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, MatIconModule, MatButtonModule, MatProgressBarModule, MatTooltipModule],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>{{ greeting() }}, {{ firstName() }}</h1>
          <p>Where hiring stands right now.</p>
        </div>
        <a mat-flat-button color="primary" routerLink="/pipeline">
          <mat-icon>view_kanban</mat-icon>
          Open pipeline
        </a>
      </div>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (stats(); as s) {
        <div class="grid-metrics">
          <a class="card metric" routerLink="/jobs">
            <span class="metric-label">Open requisitions</span>
            <span class="metric-value">{{ s.open_jobs }}</span>
            <span class="metric-foot muted small">{{ s.total_jobs }} total</span>
          </a>
          <a class="card metric" routerLink="/pipeline">
            <span class="metric-label">Active candidates</span>
            <span class="metric-value">{{ s.active_applications }}</span>
            <span class="metric-foot muted small">{{ s.total_candidates }} in database</span>
          </a>
          <a class="card metric" routerLink="/interviews">
            <span class="metric-label">Interviews this week</span>
            <span class="metric-value">{{ s.interviews_next_7_days }}</span>
            <span class="metric-foot muted small">next 7 days</span>
          </a>
          <a class="card metric" routerLink="/offers">
            <span class="metric-label">Offers in play</span>
            <span class="metric-value">{{ s.offers_pending }}</span>
            <span class="metric-foot muted small">
              @if (s.offer_acceptance_rate !== null) {
                {{ s.offer_acceptance_rate }}% accepted to date
              } @else { no decisions yet }
            </span>
          </a>
          <div class="card metric">
            <span class="metric-label">Hired this month</span>
            <span class="metric-value">{{ s.hires_this_month }}</span>
            <span class="metric-foot muted small">
              @if (s.avg_time_to_hire_days !== null) {
                {{ s.avg_time_to_hire_days }} days average to hire
              } @else { not enough history }
            </span>
          </div>
        </div>

        <div class="two-col">
          <section class="card panel">
            <h2>Funnel</h2>
            <p class="muted small">Candidates by stage across every requisition.</p>
            <ul class="funnel">
              @for (row of funnel(); track row.stage) {
                <li [class]="'stage-' + row.stage">
                  <span class="f-label">{{ row.label }}</span>
                  <span class="f-bar" aria-hidden="true">
                    <span class="f-fill" [style.width.%]="row.pct"></span>
                  </span>
                  <span class="f-count num">{{ row.count }}</span>
                </li>
              }
            </ul>
          </section>

          <section class="card panel">
            <h2>Where candidates come from</h2>
            <p class="muted small">Sourcing channel across the candidate database.</p>
            <table class="data">
              <tbody>
                @for (row of sources(); track row.name) {
                  <tr>
                    <td>{{ label(row.name) }}</td>
                    <td class="src-bar">
                      <span class="s-bar" aria-hidden="true">
                        <span class="s-fill" [style.width.%]="row.pct"></span>
                      </span>
                    </td>
                    <td class="num strong">{{ row.count }}</td>
                  </tr>
                } @empty {
                  <tr><td colspan="3" class="muted">No candidates yet</td></tr>
                }
              </tbody>
            </table>
          </section>
        </div>

        <div class="two-col">
          <section class="card panel">
            <h2>Most active requisitions</h2>
            <table class="data">
              <thead>
                <tr><th>Requisition</th><th class="num">Applicants</th></tr>
              </thead>
              <tbody>
                @for (j of s.top_jobs; track j.code) {
                  <tr>
                    <td>
                      <span class="strong">{{ j.title }}</span>
                      <span class="muted small"> · {{ j.code }}</span>
                    </td>
                    <td class="num">{{ j.applications }}</td>
                  </tr>
                } @empty {
                  <tr><td colspan="2" class="muted">Nothing open with applicants yet</td></tr>
                }
              </tbody>
            </table>

            @if (s.hiring_trend.length) {
              <h3 class="trend-title">Applications by month</h3>
              <ul class="trend">
                @for (t of s.hiring_trend; track t.month) {
                  <li>
                    <span class="t-bar" [style.height.%]="barHeight(t.applications)"
                          [matTooltip]="t.applications + ' applications, ' + t.hires + ' hired'">
                    </span>
                    <span class="t-label small muted">{{ t.month.split(' ')[0] }}</span>
                  </li>
                }
              </ul>
            }
          </section>

          <section class="card panel">
            <h2>My upcoming interviews</h2>
            @if (myInterviews().length) {
              <ul class="ivs">
                @for (iv of myInterviews(); track iv.id) {
                  <li>
                    <span class="iv-when small strong">{{ shortWhen(iv.scheduled_at) }}</span>
                    <span class="iv-body">
                      <span class="strong">{{ iv.candidate?.full_name }}</span>
                      <span class="muted small">{{ iv.round_name }} · {{ iv.job_title }}</span>
                    </span>
                  </li>
                }
              </ul>
            } @else {
              <p class="muted small">You are not on any upcoming panels.</p>
            }

            <h3 class="trend-title">Recent activity</h3>
            <ul class="feed">
              @for (a of feed(); track a.id) {
                <li>
                  <span class="dot" aria-hidden="true"></span>
                  <span>
                    {{ a.summary }}
                    <span class="muted small"> · {{ agoOf(a.created_at) }}</span>
                  </span>
                </li>
              } @empty {
                <li class="muted small">No activity recorded yet</li>
              }
            </ul>
          </section>
        </div>
      }
    </div>
  `,
  styles: [`
    .metric {
      display: flex; flex-direction: column; gap: 2px;
      padding: 14px 16px; text-decoration: none; color: inherit;
    }
    a.metric:hover { border-color: var(--accent); text-decoration: none; }
    .metric-label { font-size: 12.5px; color: var(--muted); font-weight: 500; }
    .metric-value { font-size: 30px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.15; }
    .metric-foot { margin-top: 1px; }

    .two-col {
      display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px;
      align-items: start;
    }
    @media (max-width: 1040px) { .two-col { grid-template-columns: 1fr; } }

    .panel { padding: 16px 18px 18px; }
    .panel h2 { font-size: 15px; }
    .panel > p { margin: 3px 0 14px; }

    .funnel { list-style: none; margin: 0; padding: 0; display: grid; gap: 9px; }
    .funnel li { display: grid; grid-template-columns: 92px 1fr 38px; align-items: center; gap: 10px; }
    .f-label { font-size: 13px; color: var(--text); }
    .f-bar { height: 8px; background: #eceff2; border-radius: 4px; overflow: hidden; }
    .f-fill { display: block; height: 100%; background: currentColor; border-radius: 4px; }
    .f-count { text-align: right; font-weight: 600; font-size: 13px; color: var(--text); }

    .src-bar { width: 55%; }
    .s-bar { display: block; height: 7px; background: #eceff2; border-radius: 4px; overflow: hidden; }
    .s-fill { display: block; height: 100%; background: var(--accent); }

    .trend-title { margin: 20px 0 10px; font-size: 13px; color: var(--muted); font-weight: 600; }

    .trend {
      list-style: none; margin: 0; padding: 0;
      display: flex; align-items: flex-end; gap: 10px; height: 96px;
    }
    .trend li { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%;
                justify-content: flex-end; gap: 5px; }
    .t-bar { width: 100%; max-width: 34px; background: var(--accent); border-radius: 3px 3px 0 0;
             min-height: 3px; }

    .ivs { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
    .ivs li { display: grid; grid-template-columns: 108px 1fr; gap: 10px; align-items: baseline; }
    .iv-body { display: flex; flex-direction: column; }

    .feed { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
    .feed li { display: grid; grid-template-columns: 8px 1fr; gap: 9px; align-items: baseline;
               font-size: 13px; }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
           margin-top: 6px; }
  `],
})
export class DashboardComponent implements OnInit {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  stats = signal<DashboardStats | null>(null);
  feed = signal<Activity[]>([]);
  myInterviews = signal<Interview[]>([]);
  loading = signal(true);

  firstName = computed(() => this.auth.user()?.full_name.split(' ')[0] ?? '');

  greeting = computed(() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  });

  funnel = computed(() => {
    const s = this.stats();
    if (!s) return [];
    const max = Math.max(...Object.values(s.pipeline_by_stage), 1);
    return STAGES.map((stage) => {
      const count = s.pipeline_by_stage[stage.value] ?? 0;
      return { stage: stage.value, label: stage.label, count, pct: (count / max) * 100 };
    });
  });

  sources = computed(() => {
    const s = this.stats();
    if (!s) return [];
    const entries = Object.entries(s.applications_by_source);
    const max = Math.max(...entries.map(([, v]) => v), 1);
    return entries
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count, pct: (count / max) * 100 }));
  });

  ngOnInit(): void {
    this.api.dashboard().subscribe({
      next: (s) => {
        this.stats.set(s);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
    this.api.activity({ limit: 8 }).subscribe((f) => this.feed.set(f));
    this.api.myInterviews().subscribe((list) => this.myInterviews.set(list.slice(0, 5)));
  }

  barHeight(applications: number): number {
    const max = Math.max(...(this.stats()?.hiring_trend ?? []).map((t) => t.applications), 1);
    return Math.max(3, (applications / max) * 100);
  }

  label(value: string): string {
    return titleCase(value);
  }

  agoOf(iso: string): string {
    return ago(iso);
  }

  shortWhen(iso: string): string {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
}
