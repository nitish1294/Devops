import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { when } from '../../core/format';
import { EmailTemplate, MailStatus } from '../../core/models';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    FormsModule, MatButtonModule, MatIconModule, MatFormFieldModule,
    MatInputModule, MatTabsModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Email templates</h1>
          <p>
            What candidates receive at each step. Placeholders like
            <code>$candidate_name</code> are filled in when the message is sent.
          </p>
        </div>
      </div>

      @if (mail(); as m) {
        <div class="mail-state card" [class.warn]="!m.smtp_configured">
          <mat-icon>{{ m.smtp_configured ? 'mark_email_read' : 'schedule_send' }}</mat-icon>
          <div>
            <span class="strong">
              {{ m.smtp_configured ? 'Delivering through ' + m.smtp_host : 'Nothing is being sent' }}
            </span>
            <p class="small muted">
              @if (m.smtp_configured) {
                The worker drains the queue in the background.
              } @else {
                Messages are rendered and queued but no SMTP server is configured,
                so no candidate receives anything. Set SMTP_HOST to start delivery.
              }
            </p>
          </div>
          <span class="spacer"></span>
          <span class="counts small">
            <span class="pill stage-sourced">{{ m.counts.queued }} queued</span>
            <span class="pill stage-hired">{{ m.counts.sent }} sent</span>
            @if (m.counts.failed) {
              <span class="pill stage-rejected">{{ m.counts.failed }} failed</span>
            }
          </span>
          @if (m.smtp_configured && canEdit) {
            <button mat-stroked-button type="button" [disabled]="flushing()" (click)="flush()">
              Send now
            </button>
          }
        </div>
      }

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      <mat-tab-group>
        <mat-tab label="Templates">
          <div class="tab-body">
            <div class="split">
              <nav class="card list" aria-label="Templates">
                @for (t of templates(); track t.code) {
                  <button
                    type="button"
                    class="t-item"
                    [class.on]="selected()?.code === t.code"
                    (click)="select(t)"
                  >
                    <span class="strong">{{ t.name }}</span>
                    <span class="muted small">{{ t.code }}</span>
                  </button>
                } @empty {
                  <p class="muted small pad">No templates found.</p>
                }
              </nav>

              @if (selected(); as t) {
                <section class="card panel">
                  <mat-form-field appearance="outline">
                    <mat-label>Template name</mat-label>
                    <input matInput [(ngModel)]="draftName" />
                  </mat-form-field>

                  <mat-form-field appearance="outline">
                    <mat-label>Subject</mat-label>
                    <input matInput [(ngModel)]="draftSubject" />
                  </mat-form-field>

                  <mat-form-field appearance="outline">
                    <mat-label>Body</mat-label>
                    <textarea matInput rows="12" [(ngModel)]="draftBody"></textarea>
                  </mat-form-field>

                  @if (t.placeholders?.length) {
                    <p class="small muted ph-label">
                      Placeholders this template fills in — a name not on this list
                      renders as literal text:
                    </p>
                    <div class="chips">
                      @for (ph of t.placeholders; track ph) {
                        <code class="chip">\${{ ph }}</code>
                      }
                    </div>
                  }

                  <div class="foot">
                    <span class="muted small">Last updated {{ whenOf(t.updated_at) }}</span>
                    <span class="spacer"></span>
                    @if (canEdit) {
                      <button mat-stroked-button type="button" (click)="select(t)">Reset</button>
                      <button mat-flat-button color="primary" type="button"
                              [disabled]="saving()" (click)="save(t)">
                        Save template
                      </button>
                    } @else {
                      <span class="muted small">Read only for your role</span>
                    }
                  </div>
                </section>
              }
            </div>
          </div>
        </mat-tab>

        <mat-tab label="Sent messages">
          <div class="tab-body">
            <div class="card">
              <table class="data">
                <thead>
                  <tr>
                    <th>To</th><th>Subject</th><th>Template</th><th>Status</th>
                    <th class="num">Tries</th><th>Queued</th><th></th>
                  </tr>
                </thead>
                <tbody>
                  @for (m of outbox(); track $index) {
                    <tr>
                      <td class="small">{{ m['to_email'] }}</td>
                      <td class="small strong">
                        {{ m['subject'] }}
                        @if (m['last_error']) {
                          <div class="err small">{{ m['last_error'] }}</div>
                        }
                      </td>
                      <td class="small muted">{{ m['template_code'] }}</td>
                      <td>
                        <span class="pill" [class]="statusClass(m['status'])">
                          {{ m['status'] }}
                        </span>
                      </td>
                      <td class="num small">{{ m['attempts'] || 0 }}</td>
                      <td class="small">{{ whenOf(m['created_at']) }}</td>
                      <td>
                        @if (m['status'] === 'failed' && canEdit) {
                          <button mat-icon-button type="button" (click)="retry(m)"
                                  matTooltip="Put it back in the queue">
                            <mat-icon>refresh</mat-icon>
                          </button>
                        }
                      </td>
                    </tr>
                  } @empty {
                    <tr><td colspan="7" class="muted">No messages yet.</td></tr>
                  }
                </tbody>
              </table>
            </div>
          </div>
        </mat-tab>
      </mat-tab-group>
    </div>
  `,
  styles: [`
    code { background: #eef1f4; padding: 1px 5px; border-radius: 3px; font-size: 12.5px; }
    .mail-state {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 16px; margin-bottom: 14px;
      border-left: 3px solid var(--stage-hired);
    }
    .mail-state.warn { border-left-color: #b45309; }
    .mail-state p { margin: 2px 0 0; max-width: 62ch; }
    .mail-state mat-icon { color: var(--muted); }
    .counts { display: flex; gap: 5px; }
    .ph-label { margin: 0 0 6px; }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 14px; }
    .chip { background: #eef4f3; border: 1px solid #cfe1de; color: var(--accent-dark); }
    .err { color: var(--danger); font-family: ui-monospace, monospace; }
    .tab-body { padding-top: 16px; }
    .split { display: grid; grid-template-columns: 260px 1fr; gap: 16px; align-items: start; }
    @media (max-width: 900px) { .split { grid-template-columns: 1fr; } }

    .list { overflow: hidden; display: flex; flex-direction: column; }
    .t-item {
      display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
      padding: 11px 14px; background: none; border: none; border-bottom: 1px solid var(--rule);
      cursor: pointer; text-align: left; font: inherit; width: 100%;
    }
    .t-item:last-child { border-bottom: none; }
    .t-item:hover { background: #f7f9fa; }
    .t-item.on { background: #eef4f3; box-shadow: inset 3px 0 0 var(--accent); }
    .pad { padding: 14px; margin: 0; }

    .panel { padding: 18px 20px; display: flex; flex-direction: column; }
    .foot { display: flex; align-items: center; gap: 8px; }
  `],
})
export class SettingsComponent implements OnInit {
  private api = inject(ApiService);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  templates = signal<EmailTemplate[]>([]);
  selected = signal<EmailTemplate | null>(null);
  outbox = signal<Record<string, unknown>[]>([]);
  mail = signal<MailStatus | null>(null);
  loading = signal(true);
  saving = signal(false);
  flushing = signal(false);

  draftName = '';
  draftSubject = '';
  draftBody = '';
  canEdit = this.auth.can('manage_jobs');

  ngOnInit(): void {
    this.api.templates().subscribe({
      next: (list) => {
        this.templates.set(list);
        if (list.length) this.select(list[0]);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
    this.refreshOutbox();
  }

  private refreshOutbox(): void {
    this.api.outbox(100).subscribe((list) => this.outbox.set(list));
    this.api.mailStatus().subscribe((status) => this.mail.set(status));
  }

  /** Drain the queue now rather than waiting for the worker's next cycle. */
  flush(): void {
    this.flushing.set(true);
    this.api.flushOutbox().subscribe({
      next: (result) => {
        this.flushing.set(false);
        this.snack.open(
          result['skipped']
            ? String(result['skipped'])
            : `${result['sent']} sent, ${result['failed']} failed`,
          'Dismiss',
          { duration: 4500 },
        );
        this.refreshOutbox();
      },
      error: () => this.flushing.set(false),
    });
  }

  retry(message: Record<string, unknown>): void {
    this.api.retryMessage(String(message['id'])).subscribe(() => {
      this.snack.open('Message requeued', 'Dismiss', { duration: 3000 });
      this.refreshOutbox();
    });
  }

  statusClass(status: unknown): string {
    return (
      {
        queued: 'stage-sourced',
        sent: 'stage-hired',
        failed: 'stage-rejected',
      }[String(status)] ?? 'stage-screening'
    );
  }

  select(template: EmailTemplate): void {
    this.selected.set(template);
    this.draftName = template.name;
    this.draftSubject = template.subject;
    this.draftBody = template.body;
  }

  save(template: EmailTemplate): void {
    this.saving.set(true);
    this.api
      .saveTemplate({
        code: template.code,
        name: this.draftName,
        subject: this.draftSubject,
        body: this.draftBody,
      })
      .subscribe({
        next: (saved) => {
          this.templates.update((list) =>
            list.map((t) => (t.code === saved.code ? saved : t)),
          );
          this.selected.set(saved);
          this.saving.set(false);
          this.snack.open('Template saved', 'Dismiss', { duration: 3000 });
        },
        error: () => this.saving.set(false),
      });
  }

  whenOf(value: unknown): string {
    return when(typeof value === 'string' ? value : null);
  }
}
