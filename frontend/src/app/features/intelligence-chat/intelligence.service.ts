import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AskRequest, AskResponse, IntelligenceAuditList } from './intelligence.models';

@Injectable({ providedIn: 'root' })
export class IntelligenceService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  getAudits(auditId?: string | null): Observable<IntelligenceAuditList> {
    let params = new HttpParams();
    if (auditId) {
      params = params.set('audit_id', auditId);
    }
    return this.http.get<IntelligenceAuditList>(`${this.apiBaseUrl}/intelligence/audits`, { params });
  }

  ask(request: AskRequest): Observable<AskResponse> {
    return this.http.post<AskResponse>(`${this.apiBaseUrl}/intelligence/ask`, {
      audit_id: request.audit_id,
      question: request.question,
      history: request.history,
    });
  }
}
