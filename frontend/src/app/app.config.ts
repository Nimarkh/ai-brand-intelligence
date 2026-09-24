import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { catchError, firstValueFrom, of, timeout } from 'rxjs';

import { routes } from './app.routes';
import { AuthService } from './core/auth/auth.service';
import { ThemeService } from './core/theme/theme.service';
import { credentialsInterceptor } from './core/interceptors/credentials.interceptor';
import { PageContextService } from './layout/page-context.service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([credentialsInterceptor])),
    provideAppInitializer(() => {
      inject(ThemeService);
      inject(PageContextService);
      const auth = inject(AuthService);
      return firstValueFrom(
        auth.ensureSession().pipe(
          timeout({ first: 5_000 }),
          catchError(() => of(null)),
        ),
      );
    }),
  ],
};
