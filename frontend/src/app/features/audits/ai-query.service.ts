import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AiQueryDetail,
  AiQueryListResponse,
  AiQueryRunResponse,
} from './ai-query.models';

@Injectable({ providedIn: 'root' })
export class AiQueryService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  run(auditId: string): Observable<AiQueryRunResponse> {
    return this.http.post<AiQueryRunResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/ai-queries/run`,
      {},
    );
  }

  list(auditId: string): Observable<AiQueryListResponse> {
    return this.http.get<AiQueryListResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/ai-queries`,
    );
  }

  get(auditId: string, queryId: string): Observable<AiQueryDetail> {
    return this.http.get<AiQueryDetail>(
      `${this.apiBaseUrl}/audits/${auditId}/ai-queries/${queryId}`,
    );
  }
}
