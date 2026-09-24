import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AIVisibilityResponse } from './ai-visibility.models';

@Injectable({ providedIn: 'root' })
export class AiVisibilityService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  calculateVisibility(auditId: string): Observable<AIVisibilityResponse> {
    return this.http.post<AIVisibilityResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/calculate-ai-visibility`,
      {},
    );
  }

  getVisibility(auditId: string): Observable<AIVisibilityResponse> {
    return this.http.get<AIVisibilityResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/ai-visibility`,
    );
  }
}
