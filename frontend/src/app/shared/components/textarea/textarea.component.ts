import { Component, computed, effect, forwardRef, input, signal, viewChild, ElementRef } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

let nextFieldId = 0;

@Component({
  selector: 'app-textarea',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => TextareaComponent),
      multi: true,
    },
  ],
  template: `
    <label class="field">
      <span class="field__label" [attr.for]="inputId">{{ label() }}</span>
      <textarea
        #input
        [id]="inputId"
        [rows]="rows()"
        [placeholder]="placeholder()"
        [disabled]="isDisabled()"
        [attr.aria-invalid]="error() ? true : null"
        [attr.aria-describedby]="error() ? errorId : null"
        (input)="onInput($event)"
        (blur)="handleBlur()"
      ></textarea>
      @if (error()) {
        <small class="field__error" [id]="errorId">{{ error() }}</small>
      }
    </label>
  `,
})
export class TextareaComponent implements ControlValueAccessor {
  readonly label = input.required<string>();
  readonly placeholder = input('');
  readonly rows = input(4);
  readonly error = input<string | null>(null);
  readonly disabled = input(false);

  readonly inputId = `field-${++nextFieldId}`;
  readonly errorId = `${this.inputId}-error`;

  private readonly inputRef = viewChild<ElementRef<HTMLTextAreaElement>>('input');
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
    const next = (event.target as HTMLTextAreaElement).value;
    this.value.set(next);
    this.notifyChange(next);
  }

  handleBlur(): void {
    this.notifyTouched();
  }
}
