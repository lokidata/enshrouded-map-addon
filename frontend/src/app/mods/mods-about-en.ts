import { Component } from '@angular/core';

/** What the installed mods do and how to install the client plugin (English). */
@Component({
  selector: 'app-mods-about-en',
  template: `
    <p class="hint">
      The server runs
      <a href="https://github.com/bjck/shroudlink" target="_blank" rel="noopener noreferrer"
        >ShroudLink</a
      >. The client side (the plugin) is <strong>not required</strong>: you can join the server and
      play normally without it.
    </p>

    <h3>chestsort: sort chests by their name</h3>
    <p>
      <strong>For every player, no plugin needed.</strong> Place a chest, press Rename and give it
      one or more category words, for example “Food”, “Ores &amp; Gems” or “Weapons, Armor”. At the
      chest, <strong>hold R</strong> (quick stack) or use a Quick Stack Station nearby: every item
      of those categories moves from your backpack into the chest, even if it does not hold any yet.
    </p>
    <ul>
      <li>Case does not matter and the plural “s” is optional: “Ore” works like “Ores”.</li>
      <li>Unknown words are ignored: “Bob's Food Box” means “Food”.</li>
      <li>
        Equipped items are never deposited: armour, rings, weapons, ammo, spell, glider, backpack,
        the item in your hand and the action bar.
      </li>
      <li>
        The categories come from a file on the server, reloaded live: the editor below changes it.
      </li>
    </ul>
    <h4>With the client plugin</h4>
    <ul>
      <li>
        <strong>Lock slots</strong>: hover a slot of your backpack and press <strong>L</strong>, in
        a chest screen or in your inventory. It gets a gold rim and chestsort will never deposit it
        (not by tapping R, not by holding R, not with a station). Press L again to unlock. The lock
        belongs to the <em>slot</em>, not the item. It is kept on your PC, per server. After
        joining, open any chest once: that is how the plugin learns your backpack layout.
      </li>
      <li>
        <strong>Search in a chest</strong>: open a chest then press <strong>/</strong> (or click
        SEARCH). Items that do not match fade out, in your backpack and in the chest. Esc clears, X
        clears and closes.
      </li>
      <li>
        <strong>MODS tab</strong> (K key): the “Chest categories” window lists the categories and
        tells you, for an item you search, which category (so which chest name) it belongs to.
      </li>
      <li>
        <strong>Searches are in English</strong> (English item names, for example “iron bar”).
      </li>
    </ul>

    <h3>storage: all chests as one box</h3>
    <p>
      <strong>Needs the client plugin.</strong> In the MODS tab, “Storage” shows everything stored
      in the chests within 40 m as one grid, largest stacks first, with a search (in English). Click
      an item to take it from every chest at once, as much as your backpack can hold.
    </p>

    <h3>The client plugin (optional)</h3>
    <p>
      It adds the MODS tab, the search, slot locks and the Storage window. It stays completely
      silent on servers without ShroudLink, and it switches itself off if a game update changed the
      game too much (the game keeps working).
    </p>
    <ol>
      <li>
        Download
        <a
          href="https://github.com/bjck/shroudlink/releases/download/v0.8.0/shroudlink-client.zip"
          rel="noopener noreferrer"
          >shroudlink-client.zip</a
        >
        (it contains <code>dinput8.dll</code>): this is the
        <strong>validated version, v0.8.0</strong>
        (checksum:
        <a
          href="https://github.com/bjck/shroudlink/releases/download/v0.8.0/SHA256SUMS.txt"
          rel="noopener noreferrer"
          ><code>SHA256SUMS.txt</code></a
        >). Newer versions are on the
        <a
          href="https://github.com/bjck/shroudlink/releases"
          target="_blank"
          rel="noopener noreferrer"
          >releases page</a
        >, but they have not been validated for this server.
      </li>
      <li>In Steam: right-click Enshrouded, then Manage, then Browse local files.</li>
      <li>Copy <code>dinput8.dll</code> into that folder, next to <code>enshrouded.exe</code>.</li>
      <li>Start the game.</li>
    </ol>
    <ul>
      <li>
        To uninstall, delete <code>dinput8.dll</code>. To update, close the game and replace the
        file.
      </li>
      <li>
        The plugin creates <code>shroudlink_client.log</code> (what it did, look there when
        something seems off) and <code>shroudlink_store.json</code> (your locks, per server) in the
        game folder.
      </li>
      <li>
        Some antivirus programs are wary of this file because it loads as
        <code>dinput8.dll</code>: the code is open (MIT licence) and every version is built from the
        repository.
      </li>
    </ul>
  `,
})
export class ModsAboutEn {}
