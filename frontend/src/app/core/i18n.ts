import { Injectable, Pipe, PipeTransform, computed, effect, inject, signal } from '@angular/core';
import { en } from './lang.en';
import { fr, Key } from './lang.fr';

export type Lang = 'fr' | 'en';
export type Params = Record<string, string | number>;
/** A translator, for the plain functions that build a sentence. */
export type Translate = (key: Key, params?: Params) => string;

const STORE = 'addon-lang';
const TEXTS: Record<Lang, Record<Key, string>> = { fr, en };

function initial(): Lang {
  try {
    const saved = localStorage.getItem(STORE);
    if (saved === 'fr' || saved === 'en') return saved;
  } catch {
    /* storage unavailable: the browser language decides */
  }
  return navigator.language.toLowerCase().startsWith('fr') ? 'fr' : 'en';
}

/** FR/EN texts. The choice is remembered per browser; the first visit follows the browser language. */
@Injectable({ providedIn: 'root' })
export class I18n {
  readonly lang = signal<Lang>(initial());
  readonly locale = computed(() => (this.lang() === 'fr' ? 'fr-FR' : 'en-GB'));

  constructor() {
    effect(() => (document.documentElement.lang = this.lang()));
  }

  set(lang: Lang): void {
    this.lang.set(lang);
    try {
      localStorage.setItem(STORE, lang);
    } catch {
      /* the choice only lasts for this page */
    }
  }

  readonly t: Translate = (key, params) => {
    const text = TEXTS[this.lang()][key];
    return params ? text.replace(/\{(\w+)\}/g, (m, p: string) => String(params[p] ?? m)) : text;
  };
}

/** `{{ 'key' | t }}` or `{{ 'key' | t: { n: 3 } }}`. Impure: it must follow the language signal. */
@Pipe({ name: 't', pure: false })
export class T implements PipeTransform {
  private readonly i18n = inject(I18n);
  transform(key: Key, params?: Params): string {
    return this.i18n.t(key, params);
  }
}
