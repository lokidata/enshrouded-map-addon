import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./server/server').then((m) => m.Server),
    title: 'Serveur',
  },
  { path: 'mods', loadComponent: () => import('./mods/mods').then((m) => m.Mods) },
  { path: '**', redirectTo: '' },
];
