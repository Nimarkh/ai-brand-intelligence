import { Component, ElementRef, computed, effect, forwardRef, input, signal, viewChild } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

let nextFieldId = 0;

@Component({
  selector: 'app-input',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => InputComponent),
      multi: true,
    },
  ],
  template: `
    <label class="field">
      <span class="field__label" [attr.for]="inputId">{{ label() }}</span>
      <input
        #input
        [id]="inputId"
        [type]="type()"
        [placeholder]="placeholder()"
        [disabled]="isDisabled()"
        [attr.autocomplete]="autocomplete()"
        [attr.aria-invalid]="error() ? true : null"
        [attr.aria-describedby]="error() ? errorId : null"
        (input)="onInput($event)"
        (blur)="handleBlur()"
      />
      @if (error()) {
        <small class="field__error" [id]="errorId">{{ error() }}</small>
      }
    </label>
  `,
})
export class InputComponent implements ControlValueAccessor {
  readonly label = input.required<string>();
  readonly type = input('text');
  readonly placeholder = input('');
  readonly autocomplete = input<string | null>(null);
  readonly error = input<string | null>(null);
  readonly disabled = input(false);

  readonly inputId = `field-${++nextFieldId}`;
  readonly errorId = `${this.inputId}-error`;

  private readonly inputRef = viewChild<ElementRef<HTMLInputElement>>('input');
  private readonly value = signal('');
  private readonly controlDisabled = signal(false);
  private notifyChange: (value: string) => void = () => undefined;
  private notifyTouched: () => void = () => undefined;

  readonly isDisabled = computed(() => this.disabled() || this.controlDisabled());

  constructor() {
    effect(() => {
      const next = this.value();
      const element = this.inputRef()?.nativeElement;
      if (element && element.value !== next) {
        element.value = next;
      }
    });
  }

  writeValue(value: string | null): void {
    this.value.set(value ?? '');
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

  onInput(event: Event): void {
    const next = (event.target as HTMLInputElement).value;
    this.value.set(next);
    this.notifyChange(next);
  }

  handleBlur(): void {
    this.notifyTouched();
  }
}
