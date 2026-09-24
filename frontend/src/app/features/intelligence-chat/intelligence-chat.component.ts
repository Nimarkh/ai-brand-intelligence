import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, map, of, switchMap } from 'rxjs';

import { ButtonComponent } from '../../shared/components/button/button.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../shared/components/error-state/error-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import {
  AskResponse,
  ChatMessage,
  HistoryMessage,
  IntelligenceAudit,
  IntelligenceAuditList,
  QUESTION_MAX_LENGTH,
  SUGGESTED_QUESTIONS,
  auditOptionLabel,
  evidenceTypeLabel,
  formatAuditDate,
} from './intelligence.models';
import { IntelligenceService } from './intelligence.service';

type PageStatus = 'loading' | 'ready' | 'error';

@Component({
  selector: 'app-intelligence-chat',
  imports: [RouterLink, PageHeaderComponent, ButtonComponent, EmptyStateComponent, ErrorStateComponent],
  templateUrl: './intelligence-chat.component.html',
  styleUrl: './intelligence-chat.component.scss',
})
export class IntelligenceChatComponent {
  private readonly api = inject(IntelligenceService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly loads = new Subject<void>();
  private requestSeq = 0;

  readonly status = signal<PageStatus>('loading');
  readonly audits = signal<IntelligenceAudit[]>([]);
  readonly selectedAuditId = signal<string | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly draft = signal('');
  readonly sending = signal(false);
  readonly httpStatus = signal(0);
  readonly suggestions = SUGGESTED_QUESTIONS;
  readonly questionMax = QUESTION_MAX_LENGTH;
  readonly auditOptionLabel = auditOptionLabel;
  readonly evidenceTypeLabel = evidenceTypeLabel;
  readonly formatAuditDate = formatAuditDate;

  readonly activeAudit = computed(() => {
    const id = this.selectedAuditId();
    return this.audits().find((audit) => audit.id === id) ?? null;
  });

  readonly validationMessage = computed(() => {
    if (this.draft().trim().length > QUESTION_MAX_LENGTH) {
      return 'Questions are limited to 2000 characters.';
    }
    return null;
  });

  readonly sendDisabled = computed(() => {
    const length = this.draft().trim().length;
    return (
      this.sending() ||
      this.status() !== 'ready' ||
      this.activeAudit() === null ||
      length === 0 ||
      length > QUESTION_MAX_LENGTH
    );
  });

  constructor() {
    this.loads
      .pipe(
        switchMap(() => this.fetchAudits()),
        takeUntilDestroyed(),
      )
      .subscribe((result) => this.applyLoad(result));

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const auditId = params.get('audit_id') ?? '';
      const current = this.selectedAuditId();
      if (current === auditId) {
        return;
      }
      const clearConversation = current !== null && current !== '' && current !== auditId;
      this.selectedAuditId.set(auditId);
      if (clearConversation) {
        this.resetConversation();
      }
      this.status.set('loading');
      this.loads.next();
    });
  }

  selectValue(event: Event): string {
    return (event.target as HTMLSelectElement).value;
  }

  onDraft(event: Event): void {
    this.draft.set((event.target as HTMLTextAreaElement).value);
  }

  onAuditChange(auditId: string): void {
    if (!auditId || auditId === this.selectedAuditId()) {
      return;
    }
    this.requestSeq += 1;
    this.sending.set(false);
    this.resetConversation();
    this.selectedAuditId.set(auditId);
    void this.router.navigate(['/intelligence-chat'], {
      queryParams: { audit_id: auditId },
    });
    this.status.set('loading');
    this.loads.next();
  }

  askSuggestion(question: string): void {
    this.draft.set(question);
    this.submit();
  }

  onSubmit(event: Event): void {
    event.preventDefault();
    this.submit();
  }

  onEnter(event: Event): void {
    const keyboard = event as KeyboardEvent;
    if (keyboard.shiftKey) {
      return;
    }
    keyboard.preventDefault();
    this.submit();
  }

  submit(question = this.draft(), echoUser = true): void {
    const text = question.trim();
    const audit = this.activeAudit();
    if (!audit || this.sending() || text.length === 0 || text.length > QUESTION_MAX_LENGTH) {
      return;
    }
    const history = this.historyPayload(echoUser ? false : true);
    if (echoUser) {
      this.messages.update((items) => [...items, this.message('user', text, 'complete')]);
      this.draft.set('');
    }
    const pending = this.message('assistant', 'Analyzing your audit…', 'pending');
    this.messages.update((items) => [...items, pending]);
    this.sending.set(true);
    const seq = ++this.requestSeq;
    this.api
      .ask({ audit_id: audit.id, question: text, history })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (response) => {
          if (seq !== this.requestSeq) {
            return;
          }
          this.sending.set(false);
          this.replacePending(pending.id, this.answerMessage(response));
        },
        error: (error: HttpErrorResponse) => {
          if (seq !== this.requestSeq) {
            return;
          }
          this.sending.set(false);
          if (error.status === 401) {
            void this.router.navigate(['/login']);
            return;
          }
          this.replacePending(pending.id, this.errorMessage(text));
        },
      });
  }

  retry(messageId: string): void {
    const failed = this.messages().find((item) => item.id === messageId);
    const question = failed?.retryQuestion;
    if (!question || this.sending()) {
      return;
    }
    this.messages.update((items) => items.filter((item) => item.id !== messageId));
    this.submit(question, false);
  }

  clearConversation(): void {
    this.requestSeq += 1;
    this.sending.set(false);
    this.resetConversation();
  }

  reload(): void {
    this.status.set('loading');
    this.loads.next();
  }

  private fetchAudits() {
    const requested = this.selectedAuditId();
    return this.api.getAudits(requested || null).pipe(
      map((list) => ({ list, failed: false, httpStatus: 0 })),
      catchError((error: HttpErrorResponse) =>
        of({ list: null, failed: true, httpStatus: error.status ?? 0 }),
      ),
    );
  }

  private applyLoad(result: {
    list: IntelligenceAuditList | null;
    failed: boolean;
    httpStatus: number;
  }): void {
    if (result.failed || result.list === null) {
      this.httpStatus.set(result.httpStatus);
      if (result.httpStatus === 401) {
        void this.router.navigate(['/login']);
        return;
      }
      this.status.set('error');
      return;
    }
    this.audits.set(result.list.audits);
    const requested = this.selectedAuditId() ?? '';
    const selected =
      result.list.audits.find((audit) => audit.id === requested) ??
      result.list.audits.find((audit) => audit.id === result.list?.selected_audit_id) ??
      null;
    this.status.set('ready');
    if (!requested && selected) {
      this.selectedAuditId.set(selected.id);
      void this.router.navigate(['/intelligence-chat'], {
        queryParams: { audit_id: selected.id },
        replaceUrl: true,
      });
    }
  }

  private historyPayload(excludeLatestUser: boolean): HistoryMessage[] {
    let items = this.messages().filter((item) => item.status === 'complete');
    if (excludeLatestUser) {
      const last = items[items.length - 1];
      if (last?.role === 'user') {
        items = items.slice(0, -1);
      }
    }
    return items.slice(-10).map((item) => ({
      role: item.role,
      content: item.content,
    }));
  }

  private answerMessage(response: AskResponse): ChatMessage {
    return this.message('assistant', response.answer ?? '', 'complete', response.sources ?? []);
  }

  private errorMessage(question: string): ChatMessage {
    return {
      ...this.message(
        'assistant',
        "We couldn't complete the analysis.\nPlease try again.",
        'error',
      ),
      retryQuestion: question,
    };
  }

  private message(
    role: ChatMessage['role'],
    content: string,
    status: ChatMessage['status'],
    sources?: ChatMessage['sources'],
  ): ChatMessage {
    return {
      id: this.nextId(),
      role,
      content,
      createdAt: new Date().toISOString(),
      status,
      sources,
    };
  }

  private replacePending(id: string, next: ChatMessage): void {
    this.messages.update((items) => items.map((item) => (item.id === id ? { ...next, id } : item)));
  }

  private resetConversation(): void {
    this.messages.set([]);
    this.draft.set('');
  }

  private nextId(): string {
    if (globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID();
    }
    return `msg-${Date.now()}`;
  }
}
