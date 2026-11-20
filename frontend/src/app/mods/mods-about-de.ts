import { Component } from '@angular/core';

/** What the installed mods do and how to install the client plugin (German). */
@Component({
  selector: 'app-mods-about-de',
  template: `
    <p class="hint">
      Der Server läuft mit
      <a href="https://github.com/bjck/shroudlink" target="_blank" rel="noopener noreferrer"
        >ShroudLink</a
      >. Die Client-Seite (das Plugin) ist <strong>nicht erforderlich</strong>: Du kannst dem Server
      beitreten und ganz normal ohne es spielen.
    </p>

    <h3>chestsort: Truhen nach ihrem Namen sortieren</h3>
    <p>
      <strong>Für alle Spieler, kein Plugin nötig.</strong> Stelle eine Truhe auf, wähle Umbenennen
      und gib ihr ein oder mehrere Kategoriewörter, zum Beispiel „Food“, „Ores &amp; Gems“ oder
      „Weapons, Armor“. An der Truhe <strong>R gedrückt halten</strong> (Schnellablage) oder eine
      Schnellablage-Station in der Nähe benutzen: Jeder Gegenstand dieser Kategorien wandert aus
      deinem Rucksack in die Truhe, auch wenn sie noch keinen enthält.
    </p>
    <ul>
      <li>
        Groß- und Kleinschreibung spielen keine Rolle, das Plural-„s“ ist optional: „Ore“
        funktioniert wie „Ores“.
      </li>
      <li>Unbekannte Wörter werden ignoriert: „Bob's Food Box“ bedeutet „Food“.</li>
      <li>
        Angelegte Gegenstände werden nie abgelegt: Rüstung, Ringe, Waffen, Munition, Zauber,
        Gleiter, Rucksack, der Gegenstand in deiner Hand und die Aktionsleiste.
      </li>
      <li>
        Die Kategorien stammen aus einer Datei auf dem Server, die live neu geladen wird: Der Editor
        unten ändert sie.
      </li>
    </ul>
    <h4>Mit dem Client-Plugin</h4>
    <ul>
      <li>
        <strong>Plätze sperren</strong>: Zeige auf einen Platz deines Rucksacks und drücke
        <strong>L</strong>, in einer Truhenansicht oder in deinem Inventar. Er erhält einen goldenen
        Rand und chestsort legt dort nie etwas ab (weder durch Tippen auf R, noch durch Halten von
        R, noch mit einer Station). Drücke erneut L zum Entsperren. Die Sperre gehört zum
        <em>Platz</em>, nicht zum Gegenstand. Sie wird pro Server auf deinem PC gespeichert. Öffne
        nach dem Beitritt einmal eine beliebige Truhe: So lernt das Plugin die Aufteilung deines
        Rucksacks.
      </li>
      <li>
        <strong>Suche in einer Truhe</strong>: Öffne eine Truhe und drücke <strong>/</strong> (oder
        klicke auf SEARCH). Gegenstände, die nicht passen, werden ausgeblendet, im Rucksack und in
        der Truhe. Esc löscht, X löscht und schließt.
      </li>
      <li>
        <strong>Reiter MODS</strong> (Taste K): Das Fenster „Chest categories“ listet die Kategorien
        auf und zeigt dir für einen gesuchten Gegenstand, zu welcher Kategorie (also welchem
        Truhennamen) er gehört.
      </li>
      <li>
        <strong>Die Suche erfolgt auf Englisch</strong> (englische Gegenstandsnamen, zum Beispiel
        „iron bar“).
      </li>
    </ul>

    <h3>storage: alle Truhen als eine Kiste</h3>
    <p>
      <strong>Benötigt das Client-Plugin.</strong> Im Reiter MODS zeigt „Storage“ alles, was in den
      Truhen im Umkreis von 40 m liegt, als ein Raster, größte Stapel zuerst, mit einer Suche (auf
      Englisch). Klicke auf einen Gegenstand, um ihn aus allen Truhen auf einmal zu nehmen, so viel
      dein Rucksack fasst.
    </p>

    <h3>Das Client-Plugin (optional)</h3>
    <p>
      Es fügt den Reiter MODS, die Suche, die Platzsperren und das Storage-Fenster hinzu. Auf
      Servern ohne ShroudLink bleibt es völlig still und schaltet sich selbst ab, wenn ein
      Spiel-Update das Spiel zu stark verändert hat (das Spiel läuft weiter).
    </p>
    <ol>
      <li>
        Lade
        <a
          href="https://github.com/bjck/shroudlink/releases/download/v0.8.0/shroudlink-client.zip"
          rel="noopener noreferrer"
          >shroudlink-client.zip</a
        >
        (enthält <code>dinput8.dll</code>) herunter: Das ist die
        <strong>geprüfte Version, v0.8.0</strong>
        (Prüfsumme:
        <a
          href="https://github.com/bjck/shroudlink/releases/download/v0.8.0/SHA256SUMS.txt"
          rel="noopener noreferrer"
          ><code>SHA256SUMS.txt</code></a
        >). Neuere Versionen findest du auf der
        <a
          href="https://github.com/bjck/shroudlink/releases"
          target="_blank"
          rel="noopener noreferrer"
          >Releases-Seite</a
        >, sie wurden aber für diesen Server nicht geprüft.
      </li>
      <li>
        In Steam: Rechtsklick auf Enshrouded, dann Verwalten, dann Lokale Dateien durchsuchen.
      </li>
      <li>Kopiere <code>dinput8.dll</code> in diesen Ordner, neben <code>enshrouded.exe</code>.</li>
      <li>Starte das Spiel.</li>
    </ol>
    <ul>
      <li>
        Zum Deinstallieren lösche <code>dinput8.dll</code>. Zum Aktualisieren schließe das Spiel und
        ersetze die Datei.
      </li>
      <li>
        Das Plugin erstellt im Spielordner <code>shroudlink_client.log</code> (was es getan hat,
        schau dort nach, wenn etwas nicht stimmt) und <code>shroudlink_store.json</code> (deine
        Sperren, pro Server).
      </li>
      <li>
        Manche Virenscanner sind bei dieser Datei misstrauisch, weil sie als
        <code>dinput8.dll</code> geladen wird: Der Code ist offen (MIT-Lizenz) und jede Version wird
        aus dem Repository gebaut.
      </li>
    </ul>
  `,
})
export class ModsAboutDe {}
