import { Component, computed, forwardRef, input, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface SelectOption {
  value: string;
  label: string;
}

let nextSelectId = 0;

@Component({
  selector: 'app-select',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => SelectComponent),
      multi: true,
    },
  ],
  template: `
    <label class="field">
      <span class="field__label" [attr.for]="selectId">{{ label() }}</span>
      <select
        [id]="selectId"
        [disabled]="isDisabled()"
        [value]="value()"
        [attr.aria-invalid]="error() ? true : null"
        [attr.aria-describedby]="error() ? errorId : null"
        (change)="onSelect($event)"
        (blur)="handleBlur()"
      >
        @for (option of options(); track option.value) {
          <option [value]="option.value">{{ option.label }}</option>
        }
      </select>
      @if (error()) {
        <small class="field__error" [id]="errorId">{{ error() }}</small>
      }
    </label>
  `,
})
export class SelectComponent implements ControlValueAccessor {
  readonly label = input.required<string>();
  readonly options = input.required<readonly SelectOption[]>();
  readonly error = input<string | null>(null);
  readonly disabled = input(false);

  readonly selectId = `select-${++nextSelectId}`;
  readonly errorId = `${this.selectId}-error`;

  private readonly valueState = signal('');
  private readonly controlDisabled = signal(false);
  private notifyChange: (value: string) => void = () => undefined;
  private notifyTouched: () => void = () => undefined;

  readonly value = this.valueState.asReadonly();
  readonly isDisabled = computed(() => this.disabled() || this.controlDisabled());

  writeValue(value: string | null): void {
    this.valueState.set(value ?? '');
  }

  registerOnChange(fn: (value: string) => void): void {
    this.notifyChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.notifyTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.controlDisabled.set(isDisabled);
  }

  onSelect(event: Event): void {
    const next = (event.target as HTMLSelectElement).value;
    this.valueState.set(next);
    this.notifyChange(next);
  }

  handleBlur(): void {
    this.notifyTouched();
  }
}
