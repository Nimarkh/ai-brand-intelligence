import { HttpErrorResponse } from '@angular/common/http';
import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { IntelligenceChatComponent } from './intelligence-chat.component';
import { AskRequest, AskResponse, IntelligenceAuditList } from './intelligence.models';
import { IntelligenceService } from './intelligence.service';

@Component({ standalone: true, template: 'Brand' })
class BrandStubComponent {}

@Component({ standalone: true, template: 'Sign in' })
class LoginStubComponent {}

const auditId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const otherAuditId = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';

const emptyList: IntelligenceAuditList = { audits: [], selected_audit_id: null };

const auditList: IntelligenceAuditList = {
  audits: [
    {
      id: auditId,
      brand_id: '11111111-1111-4111-8111-111111111111',
      brand_name: 'Acme',
      status: 'COMPLETED',
      created_at: '2026-09-23T12:00:00Z',
      completed_at: '2026-09-23T12:00:00Z',
    },
    {
      id: otherAuditId,
      brand_id: '22222222-2222-4222-8222-222222222222',
      brand_name: 'Harbor',
      status: 'COMPLETED',
      created_at: '2026-09-01T12:00:00Z',
      completed_at: '2026-09-01T12:00:00Z',
    },
  ],
  selected_audit_id: auditId,
};

const answer: AskResponse = {
  audit_id: auditId,
  answer: 'Based on the selected audit, metadata is the largest gap.\n<script>alert(1)</script>',
  context: {
    brand_name: 'Acme',
    audit_date: '2026-09-23T12:00:00Z',
    overall_score: 72,
    overall_status: 'PROVISIONAL',
  },
  sources: [
    { type: 'seo_finding', id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', label: 'Missing meta description' },
    {
      type: 'ai_visibility_metric',
      id: auditId,
      label: 'Mention rate: 33%',
    },
    {
      type: 'recommendation',
      id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      label: 'High-priority recommendation — Improve metadata coverage',
    },
  ],
  empty: false,
  message: null,
};

const noEvidence: AskResponse = {
  ...answer,
  answer: 'The audit context does not contain that detail.',
  sources: [],
};

describe('IntelligenceChatComponent', () => {
  let fixture: ComponentFixture<IntelligenceChatComponent>;
  let api: jasmine.SpyObj<IntelligenceService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj('IntelligenceService', ['getAudits', 'ask']);
    await TestBed.configureTestingModule({
      imports: [IntelligenceChatComponent],
      providers: [
        provideRouter([
          { path: 'intelligence-chat', component: IntelligenceChatComponent },
          { path: 'brands', component: BrandStubComponent },
          { path: 'brands/new', component: BrandStubComponent },
          { path: 'login', component: LoginStubComponent },
        ]),
        { provide: IntelligenceService, useValue: api },
      ],
    }).compileComponents();
  });

  function create(): void {
    fixture = TestBed.createComponent(IntelligenceChatComponent);
    fixture.detectChanges();
  }

  function lastAsk(): AskRequest {
    return api.ask.calls.mostRecent().args[0] as AskRequest;
  }

  function sendButton(): HTMLButtonElement {
    return fixture.nativeElement.querySelector('.ask-composer button') as HTMLButtonElement;
  }

  it('shows a loading state before audits arrive', () => {
    api.getAudits.and.returnValue(new Subject<IntelligenceAuditList>());
    create();

    expect(fixture.nativeElement.querySelector('[aria-label="Loading Ask Intelligence"]')).not.toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Ask Intelligence');
    expect(fixture.nativeElement.textContent).not.toContain('Suggested questions');
    expect(api.ask).not.toHaveBeenCalled();
  });

  it('shows an empty workspace when the user has no audits', () => {
    api.getAudits.and.returnValue(of(emptyList));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Ask Intelligence needs an audit to work with.');
    expect(text).toContain('Create a brand and run an audit to start asking questions.');
    expect(fixture.nativeElement.querySelector('a[href="/brands/new"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('a[href="/brands"]')).not.toBeNull();
    expect(text).not.toContain('Suggested questions');
    expect(api.ask).not.toHaveBeenCalled();
  });

  it('shows the audit selector and suggested prompts', () => {
    api.getAudits.and.returnValue(of(auditList));
    create();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Acme — Sep 23, 2026');
    expect(text).toContain('Harbor — Sep 1, 2026');
    expect(text).toContain('Analyzing');
    expect(text).toContain('Audit — Sep 23, 2026');
    expect(text).toContain('Why is my AI visibility score low?');
    expect(text).toContain('What should I fix first?');
    expect(fixture.nativeElement.querySelectorAll('.ask-suggestion').length).toBe(6);
  });

  it('sends one suggested question and renders the answer with evidence', () => {
    api.getAudits.and.returnValue(of(auditList));
    api.ask.and.returnValue(of(answer));
    create();

    const suggestion = Array.from(
      fixture.nativeElement.querySelectorAll('.ask-suggestion'),
    ).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Why is my AI visibility score low?'),
    ) as HTMLButtonElement;
    suggestion.click();
    fixture.detectChanges();

    expect(lastAsk().question).toBe('Why is my AI visibility score low?');
    expect(lastAsk().audit_id).toBe(auditId);
    expect(lastAsk().history).toEqual([]);
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Based on the selected audit, metadata is the largest gap.');
    expect(text).toContain('<script>alert(1)</script>');
    expect(text).toContain('SEO Finding');
    expect(text).toContain('Missing meta description');
    expect(text).toContain('AI Visibility');
    expect(text).toContain('Mention rate: 33%');
    expect(text).toContain('Recommendation');
    expect(text).toContain('Improve metadata coverage');
    const body = fixture.nativeElement.querySelector(
      '.ask-message--assistant .ask-message__body',
    ) as HTMLElement;
    expect(body.querySelector('script')).toBeNull();
    expect(body.innerHTML).toContain('&lt;script&gt;');
    expect(api.ask).toHaveBeenCalledTimes(1);
  });

  it('shows a pending analysis state and disables send', () => {
    api.getAudits.and.returnValue(of(auditList));
    api.ask.and.returnValue(new Subject<AskResponse>());
    create();

    const input = fixture.nativeElement.querySelector('#ask-question') as HTMLTextAreaElement;
    input.value = 'Why is my score low?';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    sendButton().click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Analyzing your audit…');
    expect(fixture.nativeElement.textContent).toContain('Why is my score low?');
    expect(sendButton().disabled).toBeTrue();
    expect((fixture.nativeElement.querySelector('#ask-question') as HTMLTextAreaElement).disabled).toBeTrue();
    sendButton().click();
    expect(api.ask).toHaveBeenCalledTimes(1);
  });

  it('keeps the question and retries after an error', () => {
    api.getAudits.and.returnValue(of(auditList));
    api.ask.and.returnValues(
      throwError(() => new HttpErrorResponse({ status: 503, error: { detail: 'Traceback: secret' } })),
      of(answer),
    );
    create();

    const input = fixture.nativeElement.querySelector('#ask-question') as HTMLTextAreaElement;
    input.value = 'What should I fix first?';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    sendButton().click();
    fixture.detectChanges();

    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('What should I fix first?');
    expect(text).toContain("We couldn't complete the analysis.");
    expect(text).toContain('Please try again.');
    expect(text).not.toContain('Traceback');
    expect(text).not.toContain('secret');

    const retry = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Retry'),
    ) as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    expect(api.ask).toHaveBeenCalledTimes(2);
    expect(lastAsk().question).toBe('What should I fix first?');
    expect(fixture.nativeElement.textContent).toContain('Based on the selected audit');
    expect(fixture.nativeElement.textContent).not.toContain("We couldn't complete the analysis.");
  });

  it('says when an answer has no direct evidence', () => {
    api.getAudits.and.returnValue(of(auditList));
    api.ask.and.returnValue(of(noEvidence));
    create();

    const input = fixture.nativeElement.querySelector('#ask-question') as HTMLTextAreaElement;
    input.value = 'How is my brand doing?';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    sendButton().click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('No direct evidence was available for this answer.');
  });

  it('clears the conversation and keeps the selected audit', () => {
    api.getAudits.and.returnValue(of(auditList));
    api.ask.and.returnValue(of(answer));
    create();

    (fixture.nativeElement.querySelector('.ask-suggestion') as HTMLButtonElement).click();
    fixture.detectChanges();
    const clear = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Clear conversation'),
    ) as HTMLButtonElement;
    clear.click();
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Suggested questions');
    expect(fixture.nativeElement.textContent).not.toContain('metadata is the largest gap');
    expect(fixture.nativeElement.textContent).toContain('Acme');
    expect((fixture.nativeElement.querySelector('.ask-audit__select') as HTMLSelectElement).value).toBe(auditId);
  });

  it('clears the conversation when the audit changes', () => {
    const navigate = spyOn(TestBed.inject(Router), 'navigate').and.resolveTo(true);
    api.getAudits.and.returnValue(of(auditList));
    api.ask.and.returnValue(of(answer));
    create();

    (fixture.nativeElement.querySelector('.ask-suggestion') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('metadata is the largest gap');

    const select = fixture.nativeElement.querySelector('.ask-audit__select') as HTMLSelectElement;
    select.value = otherAuditId;
    select.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).not.toContain('metadata is the largest gap');
    expect(fixture.nativeElement.textContent).toContain('Suggested questions');
    expect(navigate).toHaveBeenCalledWith(
      ['/intelligence-chat'],
      jasmine.objectContaining({ queryParams: { audit_id: otherAuditId } }),
    );
  });

  it('disables send for an empty or oversized question', () => {
    api.getAudits.and.returnValue(of(auditList));
    create();

    expect(sendButton().disabled).toBeTrue();
    const input = fixture.nativeElement.querySelector('#ask-question') as HTMLTextAreaElement;
    input.value = 'x'.repeat(2001);
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Questions are limited to 2000 characters.');
    expect(sendButton().disabled).toBeTrue();
    sendButton().click();
    expect(api.ask).not.toHaveBeenCalled();
  });

  it('shows a page error and retries the audit load', () => {
    api.getAudits.and.returnValues(
      throwError(() => new HttpErrorResponse({ status: 500, error: { detail: 'Traceback: secret' } })),
      of(emptyList),
    );
    create();

    expect(fixture.nativeElement.textContent).toContain("We couldn't load your audits. Please try again.");
    expect(fixture.nativeElement.textContent).not.toContain('Traceback');
    const retry = Array.from(fixture.nativeElement.querySelectorAll('button')).find((button) =>
      (button as HTMLButtonElement).textContent?.includes('Try again'),
    ) as HTMLButtonElement;
    retry.click();
    fixture.detectChanges();

    expect(api.getAudits).toHaveBeenCalledTimes(2);
    expect(fixture.nativeElement.textContent).toContain('Ask Intelligence needs an audit to work with.');
  });

  it('sends an expired session back to login', async () => {
    api.getAudits.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 401, statusText: 'Unauthorized' })),
    );
    create();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/login');
  });

  it('keeps the workspace readable in dark mode', () => {
    api.getAudits.and.returnValue(of(auditList));
    document.documentElement.setAttribute('data-theme', 'dark');
    create();

    const workspace = fixture.nativeElement.querySelector('.ask-workspace') as HTMLElement;
    expect(workspace).not.toBeNull();
    const background = getComputedStyle(workspace).backgroundColor;
    expect(background).not.toBe('');
    expect(background).not.toBe('rgba(0, 0, 0, 0)');
    document.documentElement.setAttribute('data-theme', 'light');
  });

  it('uses a responsive workspace layout', () => {
    api.getAudits.and.returnValue(of(auditList));
    create();

    const workspace = fixture.nativeElement.querySelector('.ask-workspace') as HTMLElement;
    const suggestions = fixture.nativeElement.querySelector('.ask-suggestions__list') as HTMLElement;
    expect(workspace).not.toBeNull();
    expect(getComputedStyle(workspace).display).toBe('grid');
    expect(getComputedStyle(suggestions).gridTemplateColumns).not.toBe('none');

    const css = Array.from(document.styleSheets)
      .flatMap((sheet) => {
        try {
          return Array.from(sheet.cssRules).map((rule) => rule.cssText);
        } catch {
          return [];
        }
      })
      .join('\n');
    expect(css).toContain('max-width: 720px');
    expect(css).toContain('.ask-composer');
  });
});
