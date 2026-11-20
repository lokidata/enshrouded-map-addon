import { provideBrowserGlobalErrorListeners } from '@angular/core';
import { createCustomElement } from '@angular/elements';
import { createApplication } from '@angular/platform-browser';
import { Session } from './app/core/session';
import { Mods } from './app/mods/mods';
import { Server } from './app/server/server';

/** The add-ons the site mounts as custom elements (see the manifest): one Angular application, two elements. */
export const ELEMENTS = { 'addon-server': Server, 'addon-chestsort': Mods } as const;

createApplication({ providers: [provideBrowserGlobalErrorListeners()] })
  .then(async (app) => {
    for (const [tag, component] of Object.entries(ELEMENTS)) {
      if (!customElements.get(tag))
        customElements.define(tag, createCustomElement(component, { injector: app.injector }));
    }
    await app.injector.get(Session).load();
  })
  .catch((err) => console.error(err));
