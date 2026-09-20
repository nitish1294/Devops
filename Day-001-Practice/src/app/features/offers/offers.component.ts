import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';

import { ApiService } from '../../core/api.service';
import { openResponse } from '../../core/download';
import { AuthService } from '../../core/auth.service';
import { day, inr, lakhs } from '../../core/format';
import { OFFER_STATUS_LABELS, Offer, OfferStatus } from '../../core/models';
import { OfferFormDialog } from './offer-form.dialog';

@Component({
  selector: 'app-offers',
  standalone: true,
  imports: [
    FormsModule, MatButtonModule, MatIconModule, MatFormFieldModule,
    MatSelectModule, MatMenuModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <div class="page">
      <div class="page-head">
        <div>
          <h1>Offers</h1>
          <p>
            An offer moves through draft, sent, then accepted or declined. Accepting one
            marks the candidate hired.
          </p>
        </div>
        @if (canManage) {
          <button mat-flat-button color="primary" type="button" (click)="create()">
            <mat-icon>post_add</mat-icon>
            Raise an offer
          </button>
        }
      </div>

      <div class="toolbar">
        <mat-form-field appearance="outline" class="narrow">
          <mat-label>Status</mat-label>
          <mat-select [(ngModel)]="status" (ngModelChange)="reload()">
            <mat-option [value]="null">All</mat-option>
            @for (s of statuses; track s) {
              <mat-option [value]="s">{{ statusLabel(s) }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
        <span class="spacer"></span>
        <span class="muted small">{{ total() }} offers</span>
      </div>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (offers().length) {
        <div class="card">
          <table class="data">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Designation</th>
                <th class="num">Annual CTC</th>
                <th class="num">Fixed</th>
                <th class="num">Variable</th>
                <th>Joining</th>
                <th>Valid till</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (o of offers(); track o.id) {
                <tr>
                  <td>
                    <span class="strong">{{ o.candidate?.full_name || '—' }}</span>
                    <div class="muted small">{{ o.job_title }}</div>
                  </td>
                  <td class="small">{{ o.designation }}</td>
                  <td class="num strong">{{ money(o.annual_ctc) }}</td>
                  <td class="num small">{{ short(o.fixed_component) }}</td>
                  <td class="num small">{{ short(o.variable_component) }}</td>
                  <td class="small">{{ dayOf(o.joining_date) }}</td>
                  <td class="small">{{ dayOf(o.valid_till) }}</td>
                  <td>
                    <span class="pill" [class]="statusClass(o.status)">
                      {{ statusLabel(o.status) }}
                    </span>
                  </td>
                  <td class="row-actions">
                    <button mat-icon-button type="button" (click)="letter(o)"
                            matTooltip="Open the offer letter">
                      <mat-icon>picture_as_pdf</mat-icon>
                    </button>
                    @if (canManage && next(o).length) {
                      <button mat-icon-button type="button" [matMenuTriggerFor]="menu"
                              aria-label="Offer actions">
                        <mat-icon>more_vert</mat-icon>
                      </button>
                      <mat-menu #menu="matMenu">
                        @if (o.status === 'draft') {
                          <button mat-menu-item type="button" (click)="edit(o)">
                            <mat-icon>edit</mat-icon> Edit draft
                          </button>
                        }
                        @for (s of next(o); track s) {
                          <button mat-menu-item type="button" (click)="setStatus(o, s)">
                            <mat-icon>{{ actionIcon(s) }}</mat-icon>
                            {{ actionLabel(s) }}
                          </button>
                        }
                        @if (o.status === 'draft') {
                          <button mat-menu-item type="button" (click)="remove(o)">
                            <mat-icon>delete_outline</mat-icon> Delete draft
                          </button>
                        }
                      </mat-menu>
                    }
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else if (!loading()) {
        <div class="empty">
          <span class="empty-title">No offers in this view</span>
          <p>Raise one for a candidate who has cleared their interviews.</p>
          @if (canManage) {
            <button mat-flat-button color="primary" type="button" (click)="create()">
              Raise an offer
            </button>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .narrow { width: 180px; }
    .row-actions { white-space: nowrap; }
  `],
})
export class OffersComponent implements OnInit {
  private api = inject(ApiService);
  private dialog = inject(MatDialog);
  private snack = inject(MatSnackBar);
  private auth = inject(AuthService);

  offers = signal<Offer[]>([]);
  total = signal(0);
  loading = signal(false);
  status: OfferStatus | null = null;
  statuses: OfferStatus[] = ['draft', 'sent', 'accepted', 'declined', 'withdrawn'];
  canManage = this.auth.can('manage_offers');

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.api.offers({ status: this.status ?? undefined, page_size: 100 }).subscribe({
      next: (res) => {
        this.offers.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  create(): void {
    this.dialog
      .open(OfferFormDialog, { data: {} })
      .afterClosed()
      .subscribe((offer) => {
        if (offer) {
          this.snack.open('Draft offer created', 'Dismiss', { duration: 3500 });
          this.reload();
        }
      });
  }

  edit(offer: Offer): void {
    this.dialog
      .open(OfferFormDialog, { data: { offer } })
      .afterClosed()
      .subscribe((updated) => {
        if (updated) {
          this.snack.open('Offer updated', 'Dismiss', { duration: 3000 });
          this.reload();
        }
      });
  }

  /** Only the transitions the server will accept. */
  next(offer: Offer): OfferStatus[] {
    return {
      draft: ['sent', 'withdrawn'],
      sent: ['accepted', 'declined', 'withdrawn'],
      accepted: [],
      declined: [],
      withdrawn: [],
    }[offer.status] as OfferStatus[];
  }

  setStatus(offer: Offer, status: OfferStatus): void {
    this.api.setOfferStatus(offer.id, status).subscribe(() => {
      const message =
        status === 'accepted'
          ? `${offer.candidate?.full_name} is hired`
          : `Offer marked ${OFFER_STATUS_LABELS[status].toLowerCase()}`;
      this.snack.open(message, 'Dismiss', { duration: 4000 });
      this.reload();
    });
  }

  remove(offer: Offer): void {
    this.api.deleteOffer(offer.id).subscribe((res) => {
      this.snack.open(res.detail, 'Dismiss', { duration: 3000 });
      this.reload();
    });
  }

  /** Rendered on demand, so it always shows the figures currently on the offer. */
  letter(offer: Offer): void {
    this.api.offerLetter(offer.id).subscribe((res) => openResponse(res));
  }

  actionLabel(status: OfferStatus): string {
    return {
      sent: 'Release to candidate',
      accepted: 'Mark accepted',
      declined: 'Mark declined',
      withdrawn: 'Withdraw offer',
      draft: 'Back to draft',
    }[status];
  }

  actionIcon(status: OfferStatus): string {
    return {
      sent: 'send',
      accepted: 'check_circle',
      declined: 'cancel',
      withdrawn: 'undo',
      draft: 'edit_note',
    }[status];
  }

  statusLabel(status: OfferStatus): string {
    return OFFER_STATUS_LABELS[status];
  }

  statusClass(status: OfferStatus): string {
    return {
      draft: 'stage-sourced',
      sent: 'stage-offer',
      accepted: 'stage-hired',
      declined: 'stage-rejected',
      withdrawn: 'stage-rejected',
    }[status];
  }

  money(value?: number | null): string {
    return inr(value);
  }

  short(value?: number | null): string {
    return lakhs(value);
  }

  dayOf(value?: string | null): string {
    return day(value);
  }
}
