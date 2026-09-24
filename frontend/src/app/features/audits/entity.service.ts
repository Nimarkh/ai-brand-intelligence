import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { EntityStrengthResponse } from './entity.models';

@Injectable({ providedIn: 'root' })
export class EntityService {
  private readonly http = inject(HttpClient);
  private readonly apiBaseUrl = environment.apiBaseUrl;

  calculateEntity(auditId: string): Observable<EntityStrengthResponse> {
    return this.http.post<EntityStrengthResponse>(
      `${this.apiBaseUrl}/audits/${auditId}/calculate-entity`,
      {},
    );
  }

  getEntity(auditId: string): Observable<EntityStrengthResponse> {
    return this.http.get<EntityStrengthResponse>(`${this.apiBaseUrl}/audits/${auditId}/entity`);
  }
}
