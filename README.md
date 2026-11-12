<p align="center"><img src="app/icon.png" width="96" alt=""></p>

<h1 align="center">Fortnite Chest Tracker</h1>

<p align="center">Counts every chest you open (and break) in Fortnite, game after game, from your replays, with a full stats dashboard and the Treasure Hunters hunt.<br>
Compte tous les coffres que tu ouvres (et casses) sur Fortnite, game après game, grâce à tes replays, avec un tableau de stats complet et la chasse au trésor.</p>

<p align="center">
  <a href="https://github.com/b0ulbix/fortnite-chest-tracker/releases/download/v2.0.0/FortniteChestTracker-v2.0.0.zip"><img src="https://img.shields.io/badge/DOWNLOAD%20%2F%20T%C3%89L%C3%89CHARGER-v2.0.0%20(Windows)-2ea44f?style=for-the-badge&logo=windows&logoColor=white" alt="Download / Télécharger v2.0.0 (Windows)"></a>
</p>

<p align="center"><b>⚠️ The green "Code" button does NOT contain the app: use the download button above.</b><br>
<b>⚠️ Le bouton vert « Code » ne contient PAS l'appli : utilise le bouton de téléchargement ci-dessus.</b><br>
Unzip → open the <code>FortniteChestTracker</code> folder → double-click <code>FortniteChestTracker.exe</code>.<br>
Dézippe → ouvre le dossier <code>FortniteChestTracker</code> → double-clique sur <code>FortniteChestTracker.exe</code>.</p>

<p align="center"><a href="#english">English</a> · <a href="#français">Français</a> · Español: la app y el panel están en español (elígelo en la configuración o con el botón ES).</p>

---

## English

### What it does
- After each game, reads the replay Fortnite saves on your PC and counts **the chests you opened or broke**. The replay says
  exactly who searched and who broke each chest, so the count is exact: normal, rare, relic, buried (Sprite) and wanted-poster chests.
- **You choose what you need** at the first launch (and any time in Settings): the dashboard only shows those parts.

| Feature | What you get |
|---|---|
| **Chest counter** (always on) | Total chests (opened / broken), last game, every game with its details |
| **Treasure hunt** | Your chances with Epic's published odds, your weekly rewards collection, Treasure Hours countdown, treasures received (yours and your squad's), golden chest rewards seen near you |
| **Squad** | Your regular mates: games together, wins, what each of them finds |
| **Detailed stats** | Charts, chest types, stats by mode, best days and hours, personal records |
| **Chest calendar** | Week by week, hour by hour: how many chests and how long you played |
| **Goals & sessions** | Next chest milestone with an estimated date, your current session |
| **Stream overlay (OBS)** | A live chest counter to add as a *Browser source* in OBS |

- The dashboard is a local web page (`http://127.0.0.1:47321/`) that updates by itself when a game is added.
- Available in **English, French and Spanish** (English by default; switch in the setup or with the EN / FR / ES buttons).
- Warns you if **replay recording is turned off** in Fortnite, and can **start with Windows**.
- 100 % local: no account, no login. It only **reads** your replays. The only download is the public treasure-hunt catalog
  (weeks, rewards, odds, Treasure Hours) once a day.

### Install (2 minutes)
1. Click the **download button** above (or open [Releases](../../releases/latest)) and get `FortniteChestTracker-v2.0.0.zip`.
2. Unzip it anywhere (for example in `Documents`). Keep the two `.exe` files together.
3. Double-click **`FortniteChestTracker.exe`**. A short setup opens:
   - **your Fortnite name** (exactly as in game) and your **language**,
   - **what you will use it for**: tick the features you want, or pick *Everything*, *Just my chests* or *Streamer*,
   - **a check that replays are turned on**,
   - options: start with Windows, count the replays already on your PC, and the chests you had already opened before (optional).
4. Play. About 20 seconds after each game, your chests are added. Click **Open my dashboard** to see your stats.

> **Turn on replays in Fortnite** (otherwise nothing can be counted):
> Settings (gear) → **Game** tab → **Replays** section → **Record Replays: ON** and **Record Large Team Replays: ON** (for squads).

> **Windows SmartScreen / antivirus**: the app is not code-signed (a certificate costs money), so Windows may show
> "Windows protected your PC". Click **More info → Run anyway**. You can check the source code here and build it yourself.

> **Updating from v1**: just replace the two `.exe` files. Your games are read again once at the first start to fill the new stats.

### Good to know
- Fortnite only keeps your **latest** replays and deletes older ones: games played before installing the tool can't be recovered.
  The tool copies each replay to its own folder so it never loses one.
- A game is counted when it **ends** (back to the lobby or "Play again"), not live.
- Treasures are shared with your squad: the ones your mates find are listed apart. A reward found far from you is not in your replay.
- Your data: `%LOCALAPPDATA%\FortniteChestTracker` (`games.db`, `dashboard.html`, `collection.json`, `log.txt`, `replays\`).
  Delete this folder to reset everything.
- Uninstall: in the app, **Settings** → untick "Start with Windows", then delete the app folder and the data folder.

### Build from source
Requirements: Windows, [.NET 10 SDK](https://dotnet.microsoft.com/download), Python 3.12 with `pip install pyinstaller pillow`.
Run `build.bat` → `build\FortniteChestTracker-vX.Y.Z.zip`.

- `src/ChestCounter` — C# replay reader that outputs the chests, treasures and squad as JSON (built on
  [FortniteReplayDecompressor](https://github.com/Shiqan/FortniteReplayDecompressor), MIT).
- `app/` — Python app: setup window, background watcher, SQLite database, local web server, dashboard (`webpage.py`,
  `site_template.html`, `i18n.js`).
- Treasure detection methods adapted from [LED-N/Fortnite-ChestCounter](https://github.com/LED-N/Fortnite-ChestCounter) and
  [Linox-IDK/LNXcounter](https://github.com/Linox-IDK/LNXcounter) (MIT). See `THIRD_PARTY_NOTICES.md`.

---

## Français

### Ce que ça fait
- Après chaque game, lit le replay que Fortnite enregistre sur ton PC et compte **les coffres que tu as ouverts ou cassés**. Le replay dit
  exactement qui fouille et qui casse chaque coffre : le comptage est exact (normaux, rares, reliques, coffres à esprit enterrés, avis de recherche).
- **Tu choisis ce dont tu as besoin** au premier lancement (et à tout moment dans Réglages) : le tableau n'affiche que ces parties.

| Fonctionnalité | Ce que tu obtiens |
|---|---|
| **Compteur de coffres** (toujours actif) | Total (ouverts / cassés), dernière game, toutes tes games avec le détail |
| **Chasse au trésor** | Tes chances avec les cotes publiées par Epic, ta collection de récompenses de la semaine, compte à rebours des Treasure Hours, trésors reçus (les tiens et ceux de ton escouade), récompenses de coffre doré vues près de toi |
| **Escouade** | Tes mates réguliers : games ensemble, Top 1, ce que chacun trouve |
| **Stats détaillées** | Graphiques, types de coffres, stats par mode, meilleurs jours et heures, records |
| **Calendrier des coffres** | Semaine par semaine, heure par heure : combien de coffres et combien de temps de jeu |
| **Objectifs et sessions** | Prochain palier de coffres avec date estimée, ta session en cours |
| **Overlay de stream (OBS)** | Un compteur de coffres en direct à ajouter comme *Source navigateur* dans OBS |

- Le tableau est une page web locale (`http://127.0.0.1:47321/`) qui se met à jour toute seule quand une game est ajoutée.
- Disponible en **anglais, français et espagnol** (anglais par défaut ; à changer dans l'assistant ou avec les boutons EN / FR / ES).
- Te prévient si **l'enregistrement des replays est désactivé**, et peut **se lancer au démarrage de Windows**.
- 100 % local : pas de compte, pas de connexion. Il **lit** seulement tes replays. Le seul téléchargement est le catalogue public
  de la chasse au trésor (semaines, récompenses, cotes, Treasure Hours), une fois par jour.

### Installation (2 minutes)
1. Clique sur le **bouton de téléchargement** ci-dessus (ou ouvre [Releases](../../releases/latest)) et récupère `FortniteChestTracker-v2.0.0.zip`.
2. Dézippe-le où tu veux (par exemple dans `Documents`). Garde les deux `.exe` ensemble.
3. Double-clique sur **`FortniteChestTracker.exe`**. Un petit assistant s'ouvre :
   - **ton pseudo Fortnite** (exactement comme en jeu) et ta **langue**,
   - **à quoi va te servir le tool** : coche les fonctionnalités voulues, ou choisis *Tout*, *Juste mes coffres* ou *Streamer*,
   - **une vérification que les replays sont activés**,
   - les options : lancement au démarrage de Windows, comptage des replays déjà présents, coffres déjà ouverts avant (facultatif).
4. Joue. Environ 20 secondes après chaque game, tes coffres sont ajoutés. Clique sur **Ouvrir mon tableau** pour voir tes stats.

> **Active les replays dans Fortnite** (sinon rien ne peut être compté) :
> Réglages (roue dentée) → onglet **Jeu** → section **Replays** → **Enregistrer les replays : ACTIVÉ** et
> **Enregistrer les replays d'équipes nombreuses : ACTIVÉ** (pour les squads).

> **SmartScreen / antivirus** : l'appli n'est pas signée (un certificat est payant), Windows peut afficher
> « Windows a protégé votre ordinateur ». Clique sur **Informations complémentaires → Exécuter quand même**.

> **Mise à jour depuis la v1** : remplace simplement les deux `.exe`. Tes games sont relues une fois au premier lancement pour remplir les nouvelles stats.

### Bon à savoir
- Fortnite ne garde que tes **derniers** replays : les games jouées avant d'installer le tool ne peuvent pas être récupérées.
  Le tool copie chaque replay dans son propre dossier pour ne jamais en perdre.
- Une game est comptée **à la fin** (retour au lobby ou « Rejouer »), pas en direct.
- Les trésors sont partagés avec ton escouade : ceux de tes mates sont listés à part. Une récompense trouvée loin de toi n'est pas dans ton replay.
- Tes données : `%LOCALAPPDATA%\FortniteChestTracker` (`games.db`, `dashboard.html`, `collection.json`, `log.txt`, `replays\`).
  Supprime ce dossier pour tout remettre à zéro.
- Désinstaller : dans l'appli, **Réglages** → décoche « Lancer au démarrage de Windows », puis supprime le dossier de l'appli et le dossier de données.

---

MIT License · Not affiliated with or endorsed by Epic Games. Fortnite is a trademark of Epic Games, Inc.
