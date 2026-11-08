<p align="center"><img src="app/icon.png" width="96" alt=""></p>

<h1 align="center">Fortnite Chest Tracker</h1>

<p align="center">Counts every chest you open (and break) in Fortnite, game after game, from your replays.<br>
Compte tous les coffres que tu ouvres (et casses) sur Fortnite, game après game, grâce à tes replays.</p>

<p align="center"><a href="#english">English</a> · <a href="#français">Français</a> · Español: la app y el panel están en español (elígelo en la configuración).</p>

---

## English

### What it does
- After each game, reads the replay Fortnite saves on your PC and counts **the chests you opened or broke**.
- Keeps a **local stats page** (`dashboard.html`): total chests, wins, kills, K/D, damage, accuracy, time played,
  **personal bests** (most chests / kills / damage in one game, wins in a row, best day…) and the list of all your games.
- Warns you (Windows notification) if **replay recording is turned off** in Fortnite.
- Can **start with Windows**, so you never miss a game.
- Available in **English, French and Spanish** (English by default, change it in the setup or with the EN / FR / ES buttons).
- 100 % local: no account, no login, nothing is sent anywhere. It only **reads** your replays.

### Install (2 minutes)
1. Download `FortniteChestTracker-vX.Y.Z.zip` from the [Releases](../../releases/latest) page.
2. Unzip it anywhere (for example in `Documents`). Keep the two `.exe` files together.
3. Double-click **`FortniteChestTracker.exe`**. A small setup opens:
   - **your Fortnite name** (exactly as in game),
   - **a check that replays are turned on**,
   - options: start with Windows, count the replays already on your PC,
     and **the chests you had already opened before** (optional) so your total starts from where you really are.
4. Play. About 20 seconds after each game, your chests are added. Click **Open my dashboard** to see your stats.

> **Turn on replays in Fortnite** (otherwise nothing can be counted):
> Settings (gear) → **Game** tab → **Replays** section → **Record Replays: ON** and **Record Large Team Replays: ON** (for squads).

> **Windows SmartScreen / antivirus**: the app is not code-signed (a certificate costs money), so Windows may show
> "Windows protected your PC". Click **More info → Run anyway**. You can check the source code here and build it yourself.

### Good to know
- Fortnite only keeps your **latest** replays and deletes older ones: games played before installing the tool can't be recovered.
  The tool copies each replay to its own folder so it never loses one.
- A game is counted when it **ends** (when you return to the lobby or click "Play again"), not live.
- Your data: `%LOCALAPPDATA%\FortniteChestTracker` (`games.db`, `dashboard.html`, `log.txt`, `replays\`).
  Delete this folder to reset everything.
- Uninstall: in the app, **Settings** → untick "Start with Windows", then delete the app folder and the data folder.

### How chests are detected
Chests have no position in the replay, but the items that pop out of them do. When a chest switches to "opened" or
"destroyed", the tool looks at where its loot appeared and checks that **you** were standing right there at that moment.
Chests opened by teammates or enemies are not counted. It is very accurate but not perfect (Fortnite sometimes sends
the "opened" information several seconds late; this is handled).

### Build from source
Requirements: Windows, [.NET 10 SDK](https://dotnet.microsoft.com/download), Python 3.12 with `pip install pyinstaller pillow`.
Run `build.bat` → `build\FortniteChestTracker-vX.Y.Z.zip`.

- `src/ChestCounter` — C# replay reader that outputs the chest count as JSON (built on
  [FortniteReplayDecompressor](https://github.com/Shiqan/FortniteReplayDecompressor), MIT, see `THIRD_PARTY_NOTICES.md`).
- `app/` — Python app: setup window, background watcher, SQLite database, HTML dashboard.

---

## Français

### Ce que ça fait
- Après chaque game, lit le replay que Fortnite enregistre sur ton PC et compte **les coffres que tu as ouverts ou cassés**.
- Tient à jour une **page de stats en local** (`dashboard.html`) : total de coffres, Top 1, kills, K/D, dégâts, précision, temps de jeu,
  **records** (plus de coffres / kills / dégâts en une game, Top 1 d'affilée, meilleure journée…) et la liste de toutes tes games.
- Te prévient (notification Windows) si **l'enregistrement des replays est désactivé** dans Fortnite.
- Peut **se lancer au démarrage de Windows** pour ne rater aucune game.
- Disponible en **anglais, français et espagnol** (anglais par défaut, à changer dans l'assistant ou avec les boutons EN / FR / ES).
- 100 % local : pas de compte, pas de connexion, rien n'est envoyé nulle part. Il **lit** seulement tes replays.

### Installation (2 minutes)
1. Télécharge `FortniteChestTracker-vX.Y.Z.zip` sur la page [Releases](../../releases/latest).
2. Dézippe-le où tu veux (par exemple dans `Documents`). Garde les deux `.exe` ensemble.
3. Double-clique sur **`FortniteChestTracker.exe`**. Un petit assistant s'ouvre :
   - **ton pseudo Fortnite** (exactement comme en jeu),
   - **une vérification que les replays sont activés**,
   - les options : lancement au démarrage de Windows, comptage des replays déjà présents sur ton PC,
     et **les coffres que tu avais déjà ouverts avant** (facultatif) pour que ton total parte de là où tu en es vraiment.
4. Joue. Environ 20 secondes après chaque game, tes coffres sont ajoutés. Clique sur **Ouvrir mon tableau** pour voir tes stats.

> **Active les replays dans Fortnite** (sinon rien ne peut être compté) :
> Réglages (roue dentée) → onglet **Jeu** → section **Replays** → **Enregistrer les replays : ACTIVÉ** et
> **Enregistrer les replays d'équipes nombreuses : ACTIVÉ** (pour les squads).

> **SmartScreen / antivirus** : l'appli n'est pas signée (un certificat est payant), Windows peut afficher
> « Windows a protégé votre ordinateur ». Clique sur **Informations complémentaires → Exécuter quand même**.
> Le code source est ici, tu peux le vérifier et le compiler toi-même.

### Bon à savoir
- Fortnite ne garde que tes **derniers** replays et efface les anciens : les games jouées avant d'installer le tool ne peuvent pas être récupérées.
  Le tool copie chaque replay dans son propre dossier pour ne jamais en perdre.
- Une game est comptée **à la fin** (retour au lobby ou « Rejouer »), pas en direct.
- Tes données : `%LOCALAPPDATA%\FortniteChestTracker` (`games.db`, `dashboard.html`, `log.txt`, `replays\`).
  Supprime ce dossier pour tout remettre à zéro.
- Désinstaller : dans l'appli, **Réglages** → décoche « Lancer au démarrage de Windows », puis supprime le dossier de l'appli et le dossier de données.

### Comment les coffres sont détectés
Les coffres n'ont pas de position dans le replay, mais les objets qui en sortent si. Quand un coffre passe à « ouvert » ou
« détruit », le tool regarde où son loot est apparu et vérifie que **toi** tu étais juste à côté à ce moment-là.
Les coffres ouverts par tes mates ou des ennemis ne sont pas comptés. C'est très précis mais pas parfait (Fortnite envoie
parfois l'info « ouvert » quelques secondes en retard ; c'est géré).

---

MIT License · Not affiliated with or endorsed by Epic Games. Fortnite is a trademark of Epic Games, Inc.
