import { Component } from '@angular/core';

/** What the installed mods do and how to install the client plugin (French). */
@Component({
  selector: 'app-mods-about-fr',
  template: `
    <p class="hint">
      Le serveur utilise
      <a href="https://github.com/bjck/shroudlink" target="_blank" rel="noopener noreferrer"
        >ShroudLink</a
      >. Le côté client (le plugin) n'est <strong>pas obligatoire</strong> : on peut rejoindre le
      serveur et jouer normalement sans lui.
    </p>

    <h3>chestsort : ranger les coffres par leur nom</h3>
    <p>
      <strong>Pour tous les joueurs, sans plugin.</strong> Posez un coffre, appuyez sur Renommer et
      donnez-lui un ou plusieurs mots de catégorie, par exemple « Food », « Ores &amp; Gems » ou «
      Weapons, Armor ». Devant le coffre, <strong>maintenez R</strong> (rangement rapide) ou
      utilisez une station de rangement rapide à proximité : tous les objets de ces catégories
      passent de votre sac au coffre, même s'il n'en contient pas encore.
    </p>
    <ul>
      <li>La casse ne compte pas, le « s » du pluriel est facultatif : « Ore » vaut « Ores ».</li>
      <li>Les mots inconnus sont ignorés : « Bob's Food Box » veut dire « Food ».</li>
      <li>
        Les objets équipés ne sont jamais déposés : armure, anneaux, armes, munitions, sort,
        planeur, sac, objet en main et barre d'action.
      </li>
      <li>
        Les catégories viennent d'un fichier du serveur, rechargé en direct : l'éditeur plus bas le
        modifie.
      </li>
    </ul>
    <h4>Avec le plugin client</h4>
    <ul>
      <li>
        <strong>Verrouiller des emplacements</strong> : survolez un emplacement de votre sac et
        appuyez sur <strong>L</strong>, dans un coffre ou dans l'inventaire. Il prend un liseré doré
        et chestsort ne le rangera jamais (ni en tapant R, ni en maintenant R, ni avec une station).
        Appuyez de nouveau sur L pour déverrouiller. Le verrou appartient à l'<em>emplacement</em>,
        pas à l'objet. Il est gardé sur votre PC, par serveur. Après être entré dans le jeu, ouvrez
        un coffre une fois : c'est ainsi que le plugin découvre votre sac.
      </li>
      <li>
        <strong>Recherche dans un coffre</strong> : ouvrez un coffre puis appuyez sur
        <strong>/</strong> (ou cliquez sur SEARCH). Les objets qui ne correspondent pas s'estompent,
        dans le sac comme dans le coffre. Échap efface, X efface et ferme.
      </li>
      <li>
        <strong>Onglet MODS</strong> (touche K) : la fenêtre « Chest categories » liste les
        catégories et indique, pour un objet cherché, dans quelle catégorie (donc quel nom de
        coffre) il va.
      </li>
      <li>
        <strong>Les recherches se font en anglais</strong> (noms d'objets anglais, par exemple «
        iron bar »).
      </li>
    </ul>

    <h3>storage : tous les coffres comme une seule boîte</h3>
    <p>
      <strong>Nécessite le plugin client.</strong> Dans l'onglet MODS, « Storage » affiche tout ce
      qui est rangé dans les coffres à moins de 40 m, en une seule grille, les plus grosses piles en
      premier, avec une recherche (en anglais). Un clic sur un objet le prend dans tous les coffres
      à la fois, autant que votre sac peut en contenir.
    </p>

    <h3>Le plugin client (facultatif)</h3>
    <p>
      Il ajoute l'onglet MODS, la recherche, le verrouillage des emplacements et la fenêtre Storage.
      Il reste totalement silencieux sur les serveurs sans ShroudLink, et il se désactive tout seul
      si une mise à jour du jeu l'a trop changé (le jeu continue de fonctionner).
    </p>
    <ol>
      <li>
        Téléchargez
        <a
          href="https://github.com/bjck/shroudlink/releases/download/v0.8.0/shroudlink-client.zip"
          rel="noopener noreferrer"
          >shroudlink-client.zip</a
        >
        (il contient <code>dinput8.dll</code>) : c'est la <strong>version validée, v0.8.0</strong>
        (somme de contrôle :
        <a
          href="https://github.com/bjck/shroudlink/releases/download/v0.8.0/SHA256SUMS.txt"
          rel="noopener noreferrer"
          ><code>SHA256SUMS.txt</code></a
        >). Les versions plus récentes sont sur la
        <a
          href="https://github.com/bjck/shroudlink/releases"
          target="_blank"
          rel="noopener noreferrer"
          >page des versions</a
        >, mais elles n'ont pas été validées pour ce serveur.
      </li>
      <li>
        Dans Steam : clic droit sur Enshrouded, puis Gérer, puis Parcourir les fichiers locaux.
      </li>
      <li>
        Copiez <code>dinput8.dll</code> dans ce dossier, à côté de <code>enshrouded.exe</code>.
      </li>
      <li>Lancez le jeu.</li>
    </ol>
    <ul>
      <li>
        Pour désinstaller : supprimez <code>dinput8.dll</code>. Pour mettre à jour : fermez le jeu,
        remplacez le fichier.
      </li>
      <li>
        Le plugin crée dans le dossier du jeu <code>shroudlink_client.log</code> (ce qu'il a fait, à
        consulter en cas de souci) et <code>shroudlink_store.json</code> (vos verrous, par serveur).
      </li>
      <li>
        Certains antivirus se méfient de ce fichier, car il se charge comme
        <code>dinput8.dll</code> : le code est ouvert (licence MIT) et chaque version est construite
        depuis le dépôt.
      </li>
    </ul>
  `,
})
export class ModsAboutFr {}
