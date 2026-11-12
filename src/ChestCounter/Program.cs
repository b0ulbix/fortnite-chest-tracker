// ChestCounter : compte les coffres ouverts par le joueur qui a enregistré le replay.
// Principe :
//  1. un coffre passe à "bAlreadySearched = true" à l'instant T ;
//  2. le coffre n'a pas de position dans le replay (objet fixe de la carte), mais
//     les objets qui en sortent si : leur "LootInitialPosition" = position du coffre ;
//  3. si le joueur était à moins de N mètres de ce point à l'instant T, c'est lui qui l'a ouvert.
using System.Text.Json;
using FortniteReplayReader.Models.NetFieldExports;
using FortniteReplayReader.Models.NetFieldExports.Items;
using Unreal.Core.Contracts;
using Unreal.Core.Models;
using Unreal.Core.Models.Enums;

var debug = args.Contains("--debug");
var maxDist = 300.0; // cm : il faut être collé au coffre pour l'ouvrir
foreach (var a in args) if (a.StartsWith("--dist=")) maxDist = double.Parse(a[7..]);

static double Dist(FVector a, FVector b) =>
    Math.Sqrt(Math.Pow(a.X - b.X, 2) + Math.Pow(a.Y - b.Y, 2) + Math.Pow(a.Z - b.Z, 2));

static double? LandTime(List<(double t, FVector p)> track)
{
    // bus à ~60 000 cm : on prend le dernier point à cette altitude, puis le 1er moment où le joueur
    // ne descend plus (moins de 1 m/s de chute sur au moins 1 s) = il est au sol
    var busIdx = track.FindLastIndex(x => x.t < 600 && x.p.Z > 55000);
    if (busIdx < 0) return null;
    for (int i = busIdx + 1; i < track.Count - 1; i++)
    {
        int j = i + 1;
        while (j < track.Count - 1 && track[j].t - track[i].t < 1.0) j++;
        var dt = track[j].t - track[i].t;
        if (dt >= 1.0 && dt < 10 && (track[i].p.Z - track[j].p.Z) / dt < 100) return track[i].t;
    }
    return null;
}

var results = new List<object>();
foreach (var file in args.Where(a => !a.StartsWith("--")))
{
    try
    {
        var reader = new ChestReader();
        var replay = reader.ReadReplay(file);
        // joueur qui a enregistré le replay ; sinon celui qu'on suit le plus (c'est toujours lui)
        // joueur suivi : le pseudo donné (--player=), sinon celui qui a enregistré le replay,
        // sinon celui dont on a le plus de positions (c'est toujours lui)
        var wanted = args.FirstOrDefault(a => a.StartsWith("--player="))?[9..];
        var owner = (string.IsNullOrWhiteSpace(wanted) ? null
                        : replay.PlayerData?.FirstOrDefault(p => string.Equals(p.PlayerName, wanted, StringComparison.OrdinalIgnoreCase)))
                    ?? replay.PlayerData?.FirstOrDefault(p => p.IsReplayOwner)
                    ?? replay.PlayerData?.OrderByDescending(p => p.Locations?.Count ?? 0).FirstOrDefault();
        var track = owner?.Locations?
            .Where(l => l.ReplicatedMovement.HasValue && l.ReplicatedMovement.Value.Location != null)
            .Select(l => (t: reader.LocTime.TryGetValue(l.ReplicatedMovement.Value.Location, out var lt) ? lt : (l.ReplicatedWorldTimeSecondsDouble ?? l.ReplicatedWorldTimeSeconds ?? 0), p: l.ReplicatedMovement.Value.Location))
            .OrderBy(x => x.t).ToList() ?? new();

        var dumpArg = args.FirstOrDefault(a => a.StartsWith("--dump="));
        if (dumpArg != null)   // diagnostic : trajectoire, objets apparus et coffres, pour analyse externe
            File.WriteAllText(dumpArg[7..], JsonSerializer.Serialize(new
            {
                track = track.Select(x => new[] { x.t, x.p.X, x.p.Y, x.p.Z }),
                pickups = reader.Pickups.Select(p => new[] { p.Time, p.Pos.X, p.Pos.Y, p.Pos.Z }),
                searches = reader.Searches.Select(s => new { s.Time, s.Type, s.Channel }),
                others = replay.PlayerData?.Where(p => p != owner && p.TeamIndex == owner?.TeamIndex).Select(p => new
                {
                    p.PlayerName,
                    pts = p.Locations?.Where(l => l.ReplicatedMovement.HasValue && l.ReplicatedMovement.Value.Location != null)
                        .Select(l => new[] { reader.LocTime.TryGetValue(l.ReplicatedMovement.Value.Location, out var lt) ? lt : -1,
                                             l.ReplicatedMovement.Value.Location.X, l.ReplicatedMovement.Value.Location.Y, l.ReplicatedMovement.Value.Location.Z })
                }),
            }));
        if (debug)
            foreach (var pl in (replay.PlayerData ?? Enumerable.Empty<FortniteReplayReader.Models.PlayerData>()).OrderByDescending(p => p.Locations?.Count ?? 0).Take(6))
                Console.Error.WriteLine($"joueur {pl.PlayerName} owner={pl.IsReplayOwner} positions={pl.Locations?.Count}");
        if (args.Contains("--items"))
        {
            var ownerPawns = owner?.Locations?.Where(l => l.ReplicatedMovement?.Location != null && reader.LocPawn.ContainsKey(l.ReplicatedMovement.Value.Location))
                .Select(l => reader.LocPawn[l.ReplicatedMovement.Value.Location]).Distinct().ToList() ?? new();
            Console.Error.WriteLine($"playlist={replay.GameData?.CurrentPlaylist} teamSize={replay.GameData?.TeamSize} maxPlayers={replay.GameData?.MaxPlayers} ownerPawns={string.Join(",", ownerPawns)}");
            foreach (var g in reader.PickedUp.GroupBy(x => x.name).OrderBy(g => g.Key))
                Console.Error.WriteLine($"  PICK {g.Key} x{g.Count()} owner={g.Count(x => ownerPawns.Contains(x.target))}");
            foreach (var kv in reader.Archetypes.Where(k => System.Text.RegularExpressions.Regex.IsMatch(k.Key, "Chest|Treasure|Relic|Gizmo|Pirate|Gold|Loot|Container", System.Text.RegularExpressions.RegexOptions.IgnoreCase)).OrderBy(k => k.Key))
                Console.Error.WriteLine($"  ARCH {kv.Key} x{kv.Value}");
            foreach (var k in reader.GroupNames.Where(k => System.Text.RegularExpressions.Regex.IsMatch(k, "Gizmo|Locator|Extractor|Firework|RelicFinder|Smuggler|Llama|Taco|Snack|Celeb|Booster", System.Text.RegularExpressions.RegexOptions.IgnoreCase)))
                Console.Error.WriteLine($"  GROUP {k}");
            foreach (var l in reader.GrantLog) Console.Error.WriteLine("  GRANT " + l);
            foreach (var g in reader.PrizeGroups) Console.Error.WriteLine("  PRIZEGROUP " + g);
            foreach (var pz in reader.Prizes.Values) Console.Error.WriteLine($"  PRIZE t={pz.t:F1} {pz.id} opener={pz.opener}");
            foreach (var g in reader.Gizmos) Console.Error.WriteLine($"  GIZMO t={g.t:F1} {g.kind} pawn={g.pawn}");
            foreach (var l in reader.SearchPawnLog.Where(x => !x.StartsWith("UPGRADE") && reader.Gizmos.Any(g => x.Contains("pawn=" + g.pawn + "") ))) Console.Error.WriteLine("  BYGIZMOPAWN " + l);
            foreach (var l in reader.SearchPawnLog.Where(x => x.StartsWith("UPGRADE")).Take(40)) Console.Error.WriteLine("  SEARCHPAWN " + l);
            Console.Error.WriteLine($"  SEARCHPAWN total={reader.SearchPawnLog.Count}");
            foreach (var g in reader.InvLog.GroupBy(x => x.name).OrderBy(g => g.Key))
                Console.Error.WriteLine($"  INV {g.Key} x{g.Count()}");
        }
        if (debug && track.Count > 0)
        {
            Console.Error.WriteLine($"positions joueur : {track.First().t:F0}s -> {track.Last().t:F0}s");
            for (int i = 1; i < track.Count; i++)
                if (track[i].t - track[i - 1].t > 3)
                    Console.Error.WriteLine($"  TROU {track[i - 1].t:F1}s -> {track[i].t:F1}s ({Dist(track[i - 1].p, track[i].p) / 100:F0} m parcourus)");
            foreach (var e in reader.ContainerLog) Console.Error.WriteLine("  " + e);
        }
        var details = new List<object>();
        int mine = 0, located = 0, broken = 0, gapCount = 0, lagged = 0;
        var usedLoot = new HashSet<Pickup>(ReferenceEqualityComparer.Instance);
        var unmatched = new List<Search>();
        var mineArch = new List<string>();
        var mineSet = new HashSet<Search>(ReferenceEqualityComparer.Instance);
        foreach (var s in reader.Searches)
        {
            // objets apparus juste après l'ouverture (hors objets lâchés par un joueur) :
            // ils sortent du coffre, donc leur point de départ = position du coffre
            var loot = reader.Pickups.Where(p => p.Time >= s.Time - 0.5 && p.Time <= s.Time + 2.0).ToList();
            if (loot.Count > 0) located++; else unmatched.Add(s);
            foreach (var l in loot) usedLoot.Add(l);
            var near = track.Where(x => Math.Abs(x.t - s.Time) <= 1.5).ToList();
            double? dist = null;
            FVector chestPos = null;
            foreach (var l in loot)
                foreach (var x in near)
                {
                    var d = Dist(x.p, l.Pos);
                    if (dist == null || d < dist) { dist = d; chestPos = l.Pos; }
                }
            var isMine = dist != null && dist <= (s.Type == "casse" ? maxDist + 200 : maxDist);

            // Trou dans la trajectoire (le replay n'envoie parfois plus la position du joueur pendant 30-60 s) :
            // le coffre est compté si le joueur pouvait l'atteindre entre son dernier point connu et le suivant.
            var viaGap = false;
            if (!isMine && near.Count == 0 && loot.Count > 0)
            {
                var prev = track.LastOrDefault(x => x.t < s.Time);
                var next = track.FirstOrDefault(x => x.t > s.Time);
                var lim = s.Type == "casse" ? maxDist + 200 : maxDist;
                if (prev.p != null && next.p != null && next.t - prev.t <= 60)
                {
                    var moved = Dist(prev.p, next.p);
                    if (moved < 500)
                        // immobile (le replay n'envoie la position que quand on bouge) : coffre juste à côté
                        viaGap = loot.Any(l => Dist(prev.p, l.Pos) <= lim);
                    else
                    {
                        // en déplacement : position estimée sur le trajet, tolérance 10 m
                        var k = (s.Time - prev.t) / (next.t - prev.t);
                        var est = new FVector(prev.p.X + (next.p.X - prev.p.X) * k, prev.p.Y + (next.p.Y - prev.p.Y) * k,
                                              prev.p.Z + (next.p.Z - prev.p.Z) * k);
                        viaGap = loot.Any(l => Dist(est, l.Pos) <= lim + 1000);
                    }
                    isMine = viaGap;
                }
            }
            if (viaGap) gapCount++;
            if (isMine) { mine++; mineArch.Add(s.Arch ?? "?"); mineSet.Add(s); }
            if (isMine && s.Type == "casse") broken++;
            if (debug)
            {
                // point du joueur le plus proche du coffre, toutes périodes confondues (diagnostic)
                double? anyD = null, anyT = null;
                foreach (var l in loot)
                    foreach (var x in track)
                    {
                        var d = Dist(x.p, l.Pos);
                        if (anyD == null || d < anyD) { anyD = d; anyT = x.t; }
                    }
                var groups = loot.GroupBy(l => (Math.Round(l.Pos.X / 50), Math.Round(l.Pos.Y / 50), Math.Round(l.Pos.Z / 50)))
                                 .Select(g => $"{g.Count()}x({g.Key.Item1 * 50:F0},{g.Key.Item2 * 50:F0}) dt={g.Min(x => x.Time) - s.Time:F2} dmin={(near.Count > 0 ? near.Min(x => Dist(x.p, g.First().Pos)) : -1):F0}").ToList();
                Console.Error.WriteLine($"COFFRE t={s.Time:F1} {s.Type}: " + string.Join(" | ", groups));
                if (loot.Count == 0)
                {
                    var wide = reader.Pickups.Where(p => Math.Abs(p.Time - s.Time) <= 6).ToList();
                    var nearW = track.Where(x => Math.Abs(x.t - s.Time) <= 1.5).ToList();
                    Console.Error.WriteLine($"   large: {wide.Count} objets, joueur suivi={nearW.Count} pts; " + string.Join(" | ",
                        wide.Take(8).Select(p => $"dt={p.Time - s.Time:F1} d={(nearW.Count > 0 ? nearW.Min(x => Dist(x.p, p.Pos)) : -1):F0}")));
                }
                details.Add(new { t = Math.Round(s.Time, 1), s.Type, s.Arch, x = chestPos?.X, y = chestPos?.Y, dist = dist == null ? (double?)null : Math.Round(dist.Value), mine = isMine, age = Math.Round(s.Age, 1), nloot = loot.Count,
                                  any_dist = anyD == null ? (double?)null : Math.Round(anyD.Value), any_t = anyT == null ? (double?)null : Math.Round(anyT.Value, 1), near = near.Count });
            }
        }

        // 2e passe : coffres dont l'info "ouvert" arrive en décalé (jusqu'à ~10 s après le loot, ou un peu avant).
        // Le loot d'un coffre = au moins 2 objets sortis du même point au même moment. Si un tel groupe, non
        // rattaché à un autre coffre, est apparu à côté du joueur, on l'associe au coffre "ouvert" sans loot le plus proche dans le temps.
        var clusters = new List<(double t, FVector p, int n)>();
        foreach (var p in reader.Pickups.Where(p => !usedLoot.Contains(p)).OrderBy(p => p.Time))
        {
            var i = clusters.FindIndex(c => p.Time - c.t < 1.5 && Dist(c.p, p.Pos) < 80);
            if (i >= 0) clusters[i] = (clusters[i].t, clusters[i].p, clusters[i].n + 1);
            else clusters.Add((p.Time, p.Pos, 1));
        }
        foreach (var c in clusters.Where(c => c.n >= 2 && c.n <= 5))   // > 5 objets = loot d'un joueur éliminé
        {
            var s = unmatched.Where(u => u.Time >= c.t - 5 && u.Time <= c.t + 12).OrderBy(u => Math.Abs(u.Time - c.t)).FirstOrDefault();
            if (s == null) continue;
            var lim = s.Type == "casse" ? maxDist + 200 : maxDist;
            var nearC = track.Where(x => Math.Abs(x.t - c.t) <= 1.5).ToList();
            if (nearC.Count == 0 || nearC.Min(x => Dist(x.p, c.p)) > lim) continue;
            unmatched.Remove(s);
            mine++; lagged++; mineArch.Add(s.Arch ?? "?"); mineSet.Add(s);
            if (s.Type == "casse") broken++;
            if (debug) Console.Error.WriteLine($"DECALE coffre t={s.Time:F1} <- loot t={c.t:F1} ({c.n} objets) à côté du joueur");
        }

        List<uint> PawnsOf(FortniteReplayReader.Models.PlayerData? pl) =>
            pl?.Locations?.Where(l => l.ReplicatedMovement?.Location != null && reader.LocPawn.ContainsKey(l.ReplicatedMovement.Value.Location))
              .Select(l => reader.LocPawn[l.ReplicatedMovement.Value.Location]).Distinct().ToList() ?? new();
        var myPawns = PawnsOf(owner);
        var mates = (replay.PlayerData ?? Enumerable.Empty<FortniteReplayReader.Models.PlayerData>())
            .Where(p => p != owner && owner?.TeamIndex != null && p.TeamIndex == owner.TeamIndex).ToList();
        var mateName = new Dictionary<uint, string>();
        foreach (var m in mates) foreach (var pw in PawnsOf(m)) mateName[pw] = m.PlayerName ?? "mate";
        var mateTracks = mates.Select(m => (name: m.PlayerName ?? "mate", tr: m.Locations?
            .Where(l => l.ReplicatedMovement?.Location != null && reader.LocTime.ContainsKey(l.ReplicatedMovement.Value.Location))
            .Select(l => (t: reader.LocTime[l.ReplicatedMovement.Value.Location], p: l.ReplicatedMovement.Value.Location)).ToList() ?? new())).ToList();
        // coffres spéciaux ouverts par un mate : son point le plus proche du loot, au moment de l'ouverture
        var mateChests = new List<object>();
        foreach (var s in reader.Searches.Where(x => x.Arch != "Chest" && x.Arch != null && !mineSet.Contains(x)))
        {
            var loot = reader.Pickups.Where(p => p.Time >= s.Time - 0.5 && p.Time <= s.Time + 2.0).ToList();
            var lim = s.Type == "casse" ? maxDist + 200 : maxDist;
            string? by = null; double best = double.MaxValue;
            foreach (var (name, tr) in mateTracks)
                foreach (var x in tr.Where(x => Math.Abs(x.t - s.Time) <= 1.5))
                    foreach (var l in loot)
                    {
                        var d = Dist(x.p, l.Pos);
                        if (d <= lim && d < best) { best = d; by = name; }
                    }
            if (by != null) mateChests.Add(new { kind = s.Arch, by });
        }
        // objets de la chasse au trésor (gizmos...) ramassés par moi ou par un mate
        var treasureRx = new System.Text.RegularExpressions.Regex("^WID_Relic|Gizmo|Treasure|Booty|Pirate", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        var treasure = reader.PickedUp.Where(x => treasureRx.IsMatch(x.name) && (myPawns.Contains(x.target) || mateName.ContainsKey(x.target)))
            .GroupBy(x => x.ch).Select(g => g.First()).OrderBy(x => x.t)
            .Select(x => new { item = x.name, me = myPawns.Contains(x.target), by = myPawns.Contains(x.target) ? null : mateName[x.target] }).ToList();
        // Gizmo GAGNÉ = il apparaît dans les mains d'un joueur de l'escouade <= 5 s après qu'un joueur de l'escouade
        // a fouillé un coffre (récompense de coffre au trésor). La récompense est partagée : les autres de l'escouade
        // reçoivent le même gizmo dans les ~30 s. Un gizmo gardé d'une game précédente n'apparaît pas juste après un coffre.
        bool InSquad(uint pw) => myPawns.Contains(pw) || mateName.ContainsKey(pw);
        string? Who(uint pw) => myPawns.Contains(pw) ? null : mateName[pw];
        // règle stricte : le gizmo apparaît dans les mains d'un joueur <= 5 s après que CE joueur a fouillé un coffre
        var rewards = new List<(double t, string item, uint opener, List<uint> got)>();
        foreach (var g in reader.Gizmos.Where(g => InSquad(g.pawn)).OrderBy(g => g.t))
        {
            var own = reader.SearchBy.Any(x => x.pawn == g.pawn && x.t <= g.t + 0.5 && g.t - x.t <= 5);
            if (own && !rewards.Any(r => r.item == g.kind && r.opener == g.pawn))
                rewards.Add((g.t, g.kind, g.pawn, new List<uint> { g.pawn }));
        }
        var gizmos = rewards.Select(r => new { item = r.item, me = myPawns.Contains(r.opener), by = Who(r.opener),
                                               t = Math.Round(r.t), shared = r.got.Select(Who).ToList() }).ToList();
        // Trésors reçus : un "grant" par trésor sur le PlayerState de l'enregistreur. Qui l'a trouvé = qui a fouillé
        // le coffre à ce moment (fenêtre -3 / +2 s, +4 s pour un coffre enterré). Coffre doré à +-5 s = déjà dans prizes.
        var myPS = myPawns.Where(reader.PawnToPS.ContainsKey).Select(pw => reader.PawnToPS[pw]).ToHashSet();
        var grantTimes = reader.Grants.Where(g => myPS.Count == 0 || myPS.Contains(g.ps)).Select(g => g.t).OrderBy(t => t).ToList();
        var treasures = new List<object>();
        for (int hi = 0; hi < grantTimes.Count; hi++)
        {
            var h = grantTimes[hi]; var next = hi + 1 < grantTimes.Count ? grantTimes[hi + 1] : double.MaxValue;
            if (reader.Prizes.Values.Any(p => Math.Abs(p.t - h) <= 5)) continue;
            var closest = reader.SearchBy.Where(x => x.t >= h - 3 && (x.t <= h + 2 || (x.t <= h + 4 && x.kind == "BuriedChest")))
                .OrderBy(x => Math.Abs(x.t - h)).Select(x => ((double t, uint pawn, string kind)?)x).FirstOrDefault();
            bool mineT = closest is { } c1 && myPawns.Contains(c1.pawn);
            string? byMate = closest is { } c2 && mateName.TryGetValue(c2.pawn, out var mn) ? mn : null;
            string? item = null;
            if (mineT)
            {
                item = reader.FirstExport.Where(kv => kv.Key.StartsWith("WID_") && !kv.Key.Contains("Consumable") && Math.Abs(kv.Value - h) <= 1).Select(kv => kv.Key).FirstOrDefault();
                if (item == null)
                {
                    var later = reader.Gizmos.Where(g => myPawns.Contains(g.pawn) && g.t >= h && g.t < next).Select(g => g.kind).Distinct().ToList();
                    if (later.Count == 1) item = later[0];
                }
            }
            treasures.Add(new { t = Math.Round(h), item, me = mineT, by = byMate, source = closest?.kind });
        }
        // Comptage exact (méthode LNXcounter / oneboyler) : ouvert = le coffre dit que c'est TON pawn qui l'a fouillé ;
        // cassé = détruit par un coup mortel de ton pawn, sans que tu l'aies ouvert avant.
        var myKillT = new Dictionary<uint, double>();
        foreach (var hh in reader.Hits) if (hh.fatal && myPawns.Contains(hh.hitter) && !myKillT.ContainsKey(hh.target)) myKillT[hh.target] = hh.t;
        var exactOpened = new Dictionary<string, int>(); int exactBroken = 0;
        foreach (var (actorId, tk) in reader.Tracks)
        {
            if (tk.Kind == "") continue;
            bool opened = tk.Searched && tk.PawnAtOpen is uint po2 && myPawns.Contains(po2);
            bool broke = !opened && tk.Destroyed && (!tk.Searched || tk.SearchedAt > tk.DestroyedAt)
                         && ((tk.Breaker is uint bk && myPawns.Contains(bk))
                             || (tk.Breaker == null && myKillT.TryGetValue(actorId, out var kt) && kt >= tk.DestroyedAt - 5 && kt <= tk.DestroyedAt + 1));
            if (opened) exactOpened[tk.Kind] = exactOpened.GetValueOrDefault(tk.Kind) + 1;
            else if (broke) { exactOpened[tk.Kind] = exactOpened.GetValueOrDefault(tk.Kind) + 1; exactBroken++; }
        }
        var pawnName = new Dictionary<uint, string>();
        foreach (var pl in replay.PlayerData ?? Enumerable.Empty<FortniteReplayReader.Models.PlayerData>())
            foreach (var pw in PawnsOf(pl)) pawnName[pw] = pl.PlayerName ?? (pl.IsBot ? "Bot" : "?");
        var seenPrizes = reader.Prizes.Values.Where(p => p.opener is uint so && !myPawns.Contains(so) && !mateName.ContainsKey(so))
            .Select(p => new { id = p.id, t = Math.Round(p.t), who = p.opener is uint w && pawnName.TryGetValue(w, out var nm) ? nm : "?" }).ToList();
        var specialChests = mineArch.Where(a => a != "Chest" && a != "?").GroupBy(a => a).ToDictionary(g => g.Key, g => g.Count());
        if (args.Contains("--items"))
            foreach (var g in reader.Searches.GroupBy(x => x.Arch ?? "?").OrderBy(g => g.Key))
                Console.Error.WriteLine($"  CHEST {g.Key} x{g.Count()} mine={mineArch.Count(m => m == g.Key)}");
        results.Add(new
        {
            file,
            ok = true,
            // comptage exact (qui fouille / qui casse, écrit dans le replay) ; ancien comptage par distance en secours
            chests_opened = myPawns.Count > 0 ? exactOpened.Values.Sum() : (track.Count > 0 ? mine : (int?)null),
            chests_broken = myPawns.Count > 0 ? exactBroken : broken,
            chests_proximity = track.Count > 0 ? mine : (int?)null,
            chests_in_gaps = gapCount,
            chests_lagged = lagged,
            player = owner?.PlayerName,
            team = owner?.TeamIndex,
            winning_team = replay.GameData?.WinningTeam,
            player_place = owner?.Placement,
            team_won = owner?.TeamIndex != null && replay.GameData?.WinningTeam != null && (uint)owner.TeamIndex == replay.GameData.WinningTeam,
            // temps réellement en jeu (secondes du replay) : atterrissage -> dernière position (mort ou fin)
            land_time = LandTime(track),
            last_pos_time = track.Count > 0 ? track[^1].t : (double?)null,
            playlist = replay.GameData?.CurrentPlaylist,
            treasure,
            special_chests = specialChests,
            mate_chests = mateChests,
            mates = mates.Select(m => m.PlayerName ?? "mate").Distinct().ToList(),
            exact_total = exactOpened.Values.Sum(),
            exact_broken = exactBroken,
            hits_debug = args.Contains("--items") ? new { total = reader.Hits.Count, fatal = reader.Hits.Count(x => x.fatal), mine = reader.Hits.Count(x => myPawns.Contains(x.hitter)),
                onChest = reader.Hits.Count(x => reader.Tracks.ContainsKey(x.target)), mineOnChest = reader.Hits.Count(x => myPawns.Contains(x.hitter) && reader.Tracks.ContainsKey(x.target)),
                destroyedTracks = reader.Tracks.Values.Count(t => t.Destroyed), tracks = reader.Tracks.Count,
                openedByCls = reader.Tracks.Values.Where(t => t.Searched && t.PawnAtOpen is uint q && myPawns.Contains(q)).GroupBy(t => t.Cls).ToDictionary(g => g.Key, g => g.Count()),
                openedTimes = string.Join(" ", reader.Tracks.Values.Where(t => t.Searched && t.PawnAtOpen is uint q && myPawns.Contains(q)).Select(t => Math.Round(t.SearchedAt)).OrderBy(x => x)),
                myFatal = reader.Hits.Where(x => x.fatal && myPawns.Contains(x.hitter)).Take(12).Select(x => $"{x.t:F0} {x.target} {reader.PathOfGuid(x.target)}").ToList(),
                destroyedKeys = reader.Tracks.Where(kv => kv.Value.Destroyed).Take(8).Select(kv => $"{kv.Value.DestroyedAt:F0} {kv.Key} {reader.PathOfGuid(kv.Key)}").ToList() } : null,
            by_type = exactOpened,
            seen_prizes = seenPrizes,
            treasures,
            grants_debug = args.Contains("--items") ? reader.Grants.Select(g => $"{g.t:F1} ps={g.ps} {g.handler}").ToList() : null,
            exports_debug = args.Contains("--items") ? reader.FirstExport.Select(kv => $"{kv.Value:F1} {kv.Key}").ToList() : null,
            myps_debug = args.Contains("--items") ? string.Join(",", myPawns.Where(reader.PawnToPS.ContainsKey).Select(pw => reader.PawnToPS[pw])) : null,
            prizes = reader.Prizes.Values.Where(p => p.opener is not uint po || myPawns.Contains(po) || mateName.ContainsKey(po)).OrderBy(p => p.t).Select(p => new { id = p.id, t = Math.Round(p.t), me = p.opener is uint o && myPawns.Contains(o), by = p.opener is uint o2 && mateName.ContainsKey(o2) ? mateName[o2] : null }).ToList(),
            gizmos,
            chests_seen_opened = reader.Searches.Count,
            chests_located = located,
            owner_positions = track.Count,
            pickups = reader.Pickups.Count,
            details = debug ? details : null,
        });
    }
    catch (Exception ex)
    {
        results.Add(new { file, ok = false, error = ex.Message });
    }
}
Console.WriteLine(JsonSerializer.Serialize(results, new JsonSerializerOptions { WriteIndented = debug }));

class Search { public double Time; public double Age; public string Type; public uint Channel; public string? Arch; }
class Pickup { public double Time; public FVector Pos; }

class ChestReader : FortniteReplayReader.ReplayReader
{
    public List<Search> Searches = new();
    public List<Pickup> Pickups = new();
    public List<string> ContainerLog = new();
    public Dictionary<FVector, double> LocTime = new(ReferenceEqualityComparer.Instance);
    public Dictionary<FVector, uint> LocPawn = new(ReferenceEqualityComparer.Instance);   // position -> pawn (GUID réseau)
    public List<(double t, uint target, string name, uint ch)> PickedUp = new();                   // objets ramassés : qui, quoi
    public List<(double t, uint ch, uint? pawn, string name)> InvLog = new();
    readonly Dictionary<uint, string> _pickupName = new();
    public Dictionary<string, int> Archetypes = new();
    public Dictionary<uint, string> ChannelArch = new();
    public List<string> GroupNames = new();
    public List<string> GrantLog = new();
    public List<(double t, uint pawn, string kind)> SearchBy = new();          // coffre fouillé : quand, par qui
    public HashSet<(uint, uint)> SearchBySeen = new();
    public List<(double t, string kind, uint pawn)> Gizmos = new();
    public HashSet<(string, uint)> GizmoSeen = new();
    public List<string> SearchPawnLog = new();
    protected override void Cleanup()
    {
        GroupNames = _netGuidCache.NetFieldExportGroupMap.Keys.ToList();
        if (Environment.GetEnvironmentVariable("CC_FIELDS") is string pat)
            foreach (var kv in _netGuidCache.NetFieldExportGroupMap.Where(k => System.Text.RegularExpressions.Regex.IsMatch(k.Key, pat)))
                Console.Error.WriteLine($"FIELDS {kv.Key}: " + string.Join(", ", kv.Value.NetFieldExports.Where(f => f != null).Select(f => f.Name)));
        base.Cleanup();
    }
    readonly HashSet<uint> _searched = new();
    readonly HashSet<uint> _pickupSeen = new();
    readonly Dictionary<uint, double> _firstSeen = new();
    // heure de l'image du replay (avant : heure du GameState, trop rarement mise à jour -> décalages de 10-40 s)
    double _time => DemoTime;

    public ChestReader() : base(null, ParseMode.Full)
    {
        // Trésors reçus (méthode reprise de LED-N/Fortnite-ChestCounter, licence MIT) : chaque trésor de la chasse donne une
        // capacité "GA_TreasureHandler_*" au joueur qui enregistre (les trésors sont partagés avec l'escouade).
        // Ces capacités ne sont pas décodées par la librairie : on lit à la main le FastArray "ActivatableAbilities".
        Unreal.Core.RawProbe.Filter = path => path.Contains("FortAbilitySystemComponent", StringComparison.Ordinal);
        Unreal.Core.RawProbe.Sink = (ch, group, field, data, bits) =>
        {
            if (group.Contains("AbilitySystemComponent", StringComparison.Ordinal) && group.EndsWith("_ClassNetCache", StringComparison.Ordinal)
                && field is "?" or "ActivatableAbilities" && HandlerGuids.Count > 0)
                ReadAbilityGrants(ch, data, bits);
        };
    }

    public class ChestTrack { public string Kind = "", Cls = ""; public bool Searched, Destroyed; public double SearchedAt, DestroyedAt; public uint? LastPawn, PawnAtOpen, Breaker; }
    public Dictionary<uint, ChestTrack> Tracks = new();
    public string PathOfGuid(uint g) => _netGuidCache.TryGetPathName(g, out var p) ? p : "";
    public List<(uint hitter, uint target, bool fatal, double t)> Hits = new();
    static string KindOf(BaseContainer c) => c switch
    {
        RareChest => "rare",
        RelicChest or RelicChestV1 or RelicChestV2 => "relic",
        BuriedChest or BuriedChestRelicFinder => "buried",
        BootyChest or BootyChestV1 or BootyChestV2 => "booty",
        Chest or AlwaysSpawnChest or FactionChest => "normal",
        _ => "",   // caisses d'extraction, munitions... : pas des coffres
    };
    public Dictionary<uint, string> HandlerGuids = new();
    public Dictionary<string, double> FirstExport = new();
    public List<(double t, uint ps, int elem, string handler)> Grants = new();
    public Dictionary<uint, uint> PawnToPS = new();
    static readonly System.Text.RegularExpressions.Regex TrackedExport =
        new(@"TreasureHandler|WID_(FlameCeleb|RelicExtractor|RelicFinder|LuckyLocator|SmugglerExtractionKey|ExtractionAccelerat)");

    protected override void OnNetGuidExported(uint netGuid, string pathName)
    {
        if (!TrackedExport.IsMatch(pathName)) return;
        var name = pathName[(pathName.LastIndexOf('/') + 1)..];
        var dot = name.LastIndexOf('.'); if (dot >= 0) name = name[(dot + 1)..];
        FirstExport.TryAdd(name, _time);
        if (name.Contains("TreasureHandler", StringComparison.Ordinal)) HandlerGuids[netGuid] = name.Replace("Default__", "");
    }

    void ReadAbilityGrants(uint channel, byte[] data, int bits)
    {
        var pos = 1;
        int Bit() => pos < bits ? (data[pos >> 3] >> (pos & 7)) & 1 : throw new IndexOutOfRangeException();
        uint Read(int n) { uint v = 0; for (var k = 0; k < n; k++) { v |= (uint)Bit() << k; pos++; } return v; }
        uint ReadPacked()
        {
            uint v = 0;
            for (var shift = 0; shift < 35; shift += 7) { var b = Read(8); v |= (b >> 1) << shift; if ((b & 1) == 0) return v; }
            throw new InvalidDataException();
        }
        try
        {
            _ = Read(32); _ = Read(32);
            var deletes = Read(32); var changed = Read(32);
            if (deletes > 512 || changed > 512 || bits < 129) return;
            pos += (int)deletes * 32;
            for (var i = 0; i < changed; i++)
            {
                var elementId = (int)Read(32);
                while (true)
                {
                    var handle = ReadPacked(); if (handle == 0) break;
                    var numBits = (int)ReadPacked();
                    if (numBits < 0 || pos + numBits > bits) return;
                    if (numBits is 8 or 16 or 24 or 32 or 40)
                    {
                        var start = pos; uint guid = 0;
                        for (var shift = 0; pos < start + numBits; shift += 7) { var b = Read(8); guid |= (b >> 1) << shift; if ((b & 1) == 0) break; }
                        pos = start + numBits;
                        if (HandlerGuids.TryGetValue(guid, out var handler))
                        {
                            var actor = Channels[channel]?.Actor?.ActorNetGUID?.Value ?? 0;
                            if (!Grants.Any(g => g.ps == actor && g.elem == elementId)) Grants.Add((_time, actor, elementId, handler));
                        }
                    }
                    else pos += numBits;
                }
            }
        }
        catch (Exception e) when (e is IndexOutOfRangeException or InvalidDataException) { }
    }

    // ---- Récompenses des coffres dorés de la chasse au trésor (méthode reprise de LNXcounter, Linox-IDK, licence MIT) ----
    // Le coffre doré est un acteur "…TreasureHunt…Chest…" que la librairie ne décode pas : on lit ses champs à la main.
    // PrizeTemplateId = identifiant de la récompense (DelilahPrize:dpid_itemN ou GUID du jeton Pirate Shop), OpeningPawn = qui l'ouvre.
    static readonly System.Text.RegularExpressions.Regex PrizeText =
        new(@"[A-Za-z][A-Za-z0-9_]*:[A-Za-z0-9_.\-]+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}");
    public Dictionary<uint, (string id, uint? opener, double t)> Prizes = new();
    public List<string> PrizeGroups = new();

    public override bool ReceiveProperties(Unreal.Core.FBitArchive ar, NetFieldExportGroup group, uint ch,
        [System.Diagnostics.CodeAnalysis.NotNullWhen(true)] out INetFieldExportGroup? export, bool checksum = true, bool delta = false)
    {
        var path = group.PathName ?? "";
        if (delta || !(path.Contains("TreasureHunt", StringComparison.OrdinalIgnoreCase) && path.Contains("Chest", StringComparison.OrdinalIgnoreCase)))
            return base.ReceiveProperties(ar, group, ch, out export, checksum, delta);
        export = null;
        if (!PrizeGroups.Contains(path)) PrizeGroups.Add(path);
        if (Channels[ch] == null) return false;
        if (checksum) ar.ReadBit();
        uint? holder = null; string? prizeId = null; bool? success = null;
        while (true)
        {
            uint idx = ar.ReadIntPacked(); if (idx == 0) break; idx--;
            if (!group.IsValidIndex(idx)) return false;
            var fe = group.NetFieldExports[idx]; int bits = (int)ar.ReadIntPacked(); if (bits == 0) continue;
            if (fe == null || ar.GetBitsLeft() < bits) { ar.SkipBits(bits); continue; }
            switch (fe.Name)
            {
                case "Instigator": case "OpeningPawn": case "Owner":
                {
                    uint p = new Unreal.Core.NetBitReader(ar.ReadBits(bits), bits).SerializePropertyObject();
                    if (p != 0 && (holder == null || fe.Name != "Owner")) holder = p;
                    break;
                }
                case "bSuccess": { success = ar.ReadBit(); if (bits > 1) ar.SkipBits(bits - 1); break; }
                case "PrizeTemplateId":
                {
                    var bytes = ar.ReadBits(bits);
                    var sb = new System.Text.StringBuilder(bytes.Length);
                    foreach (var b in bytes) sb.Append(b is >= 32 and < 127 ? (char)b : ' ');
                    var m = PrizeText.Match(sb.ToString()); if (m.Success) prizeId = m.Value;
                    break;
                }
                default: ar.SkipBits(bits); break;
            }
        }
        if (prizeId != null && success != false && !Prizes.ContainsKey(ch)) Prizes[ch] = (prizeId, holder, _time);
        else if (Prizes.TryGetValue(ch, out var pr) && pr.opener == null && holder != null) Prizes[ch] = (pr.id, holder, pr.t);
        return true;
    }

    protected override void OnChannelClosed(uint channelIndex, NetworkGUID? actor)
    {
        if (_firstSeen.ContainsKey(channelIndex)) ContainerLog.Add($"t={_time:F1} ch={channelIndex} FERME");
        base.OnChannelClosed(channelIndex, actor);
    }

    protected override void OnChannelOpened(uint channelIndex, NetworkGUID? actor)
    {
        base.OnChannelOpened(channelIndex, actor);
        var arch = Channels[channelIndex]?.Actor?.Archetype?.Value;
        ChannelArch.Remove(channelIndex);
        if (arch is uint a && _netGuidCache.TryGetPathName(a, out var path)) { Archetypes[path] = Archetypes.GetValueOrDefault(path) + 1; ChannelArch[channelIndex] = path; }
        _searched.Remove(channelIndex);
        _firstSeen.Remove(channelIndex);
        _pickupSeen.Remove(channelIndex);
    }

    protected override void OnExportRead(uint channelIndex, INetFieldExportGroup? exportGroup)
    {
        base.OnExportRead(channelIndex, exportGroup);
        switch (exportGroup)
        {
            case PlayerPawn pps when pps.PlayerState is uint psid && psid != 0 && Channels[channelIndex]?.Actor?.ActorNetGUID?.Value is uint pawnId && !PawnToPS.ContainsKey(pawnId):
                PawnToPS[pawnId] = psid;
                if (pps.ReplicatedMovement.HasValue && pps.ReplicatedMovement.Value.Location != null) { LocTime[pps.ReplicatedMovement.Value.Location] = _time; LocPawn[pps.ReplicatedMovement.Value.Location] = pawnId; }
                break;
            case PlayerPawn pp when pp.ReplicatedMovement.HasValue && pp.ReplicatedMovement.Value.Location != null:
                LocTime[pp.ReplicatedMovement.Value.Location] = _time;
                if (Channels[channelIndex]?.Actor?.ActorNetGUID?.Value is uint pg) LocPawn[pp.ReplicatedMovement.Value.Location] = pg;
                break;
            case FortInventory inv:
                if (inv.ItemDefinition?.Name != null) InvLog.Add((_time, channelIndex, inv.ReplayPawn, inv.ItemDefinition.Name));
                break;
            case GizmoWeapon gw:
                if (gw.Instigator is > 0 && GizmoSeen.Add((gw.GetType().Name, gw.Instigator.Value)))
                    Gizmos.Add((_time, gw.GetType().Name, gw.Instigator.Value));
                break;
            case GrantedItemProvider g:
                {
                    var act = Channels[channelIndex]?.Actor;
                    string? ap = act?.Archetype?.Value is uint aa && _netGuidCache.TryGetPathName(aa, out var pth) ? pth : null;
                    var names = (g.ReplicatedItemsToGrant ?? Array.Empty<GrantedItemEntry>()).Select(e => $"{e?.ItemDefinition?.Name}x{e?.Amount}")
                        .Append(g.ItemDefinition?.Name != null ? $"{g.ItemDefinition.Name}x{g.Amount}" : null).Where(x => x != null);
                    GrantLog.Add($"t={_time:F1} ch={channelIndex} actor={act?.ActorNetGUID?.Value} arch={ap} items={string.Join(",", names)}");
                }
                break;
            case FortniteReplayReader.Models.NetFieldExports.RPC.BatchedDamageCues dc when Channels[channelIndex]?.Actor?.ActorNetGUID?.Value is uint hitter:
                if (dc.NonPlayerHitActor is uint t1 && t1 != 0) Hits.Add((hitter, t1, dc.NonPlayerbIsFatal == true, _time));
                if (dc.HitActor is uint t2 && t2 != 0) Hits.Add((hitter, t2, dc.bIsFatal == true, _time));
                break;
            case BaseContainer c:
                ContainerLog.Add($"t={_time:F1} ch={channelIndex} {c.GetType().Name} searched={c.bAlreadySearched} destroyed={c.bDestroyed} hp={c.Health}/{c.MaxHealth} anim={c.SearchAnimationCount}");
                if (!_firstSeen.ContainsKey(channelIndex)) _firstSeen[channelIndex] = _time;
                if (Channels[channelIndex]?.Actor?.ActorNetGUID?.Value is uint chestId)
                {
                    if (!Tracks.TryGetValue(chestId, out var tk)) Tracks[chestId] = tk = new ChestTrack { Kind = KindOf(c), Cls = c.GetType().Name };
                    uint? sp = c.SearchingPawn is uint spv && spv != 0 ? spv : null;
                    if (c.bDestroyed)
                    {
                        // la mise à jour qui casse le coffre nomme qui l'a cassé (méthode oneboyler, 1430/1439 vérifiés)
                        if (!tk.Destroyed) { tk.Destroyed = true; tk.DestroyedAt = _time; tk.Breaker = sp; }
                    }
                    else
                    {
                        if (sp != null) { tk.LastPawn = sp; if (tk.Searched) tk.PawnAtOpen ??= sp; }
                        if (c.bAlreadySearched && !tk.Searched) { tk.Searched = true; tk.SearchedAt = _time; tk.PawnAtOpen = sp ?? tk.LastPawn; }
                    }
                }
                if (c.SearchingPawn is > 0 && SearchBySeen.Add((channelIndex, c.SearchingPawn.Value))) SearchBy.Add((_time, c.SearchingPawn.Value, c.GetType().Name));
                if (c.SearchingPawn is > 0) SearchPawnLog.Add($"t={_time:F1} ch={channelIndex} {c.GetType().Name} pawn={c.SearchingPawn}");
                if (c.ChosenRandomUpgrade is int up && up != 0) SearchPawnLog.Add($"UPGRADE t={_time:F1} ch={channelIndex} {c.GetType().Name} up={up} searched={c.bAlreadySearched}");
                if ((c.bAlreadySearched || c.bDestroyed) && _searched.Add(channelIndex))
                    Searches.Add(new Search { Time = _time, Age = _time - _firstSeen[channelIndex], Type = c.bAlreadySearched ? "ouvert" : "casse", Channel = channelIndex, Arch = c.GetType().Name });
                break;
            case FortPickup p:
                if (p.ItemDefinition?.Name != null) _pickupName[channelIndex] = p.ItemDefinition.Name;
                if (p.PickupTarget is > 0 && _pickupName.TryGetValue(channelIndex, out var pn))
                    PickedUp.Add((_time, p.PickupTarget.Value, pn, channelIndex));
                if (p.PawnWhoDroppedPickup is > 0) { _pickupSeen.Add(channelIndex); break; }
                var pos = p.LootInitialPosition ?? Channels[channelIndex]?.Actor?.Location
                          ?? (p.ReplicatedMovement.HasValue ? p.ReplicatedMovement.Value.Location : null);
                if (pos != null && _pickupSeen.Add(channelIndex))
                    Pickups.Add(new Pickup { Time = _time, Pos = pos });
                break;
        }
    }
}

