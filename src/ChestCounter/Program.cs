// ChestCounter: counts the chests opened by the player who recorded a Fortnite replay.
// How it works:
//  1. a chest switches to "bAlreadySearched" (opened) or "bDestroyed" (broken);
//  2. chests have no position in the replay, but the items that pop out of them do
//     ("LootInitialPosition" = chest position);
//  3. if the player was within a few metres of that point at that moment, the chest is theirs.
//     The "opened" state sometimes arrives 5-12 s after the loot: a 2nd pass handles that.
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

var results = new List<object>();
foreach (var file in args.Where(a => !a.StartsWith("--")))
{
    try
    {
        var reader = new ChestReader();
        var replay = reader.ReadReplay(file);
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
            if (isMine) mine++;
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
                details.Add(new { t = Math.Round(s.Time, 1), s.Type, x = chestPos?.X, y = chestPos?.Y, dist = dist == null ? (double?)null : Math.Round(dist.Value), mine = isMine, age = Math.Round(s.Age, 1), nloot = loot.Count,
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
            mine++; lagged++;
            if (s.Type == "casse") broken++;
            if (debug) Console.Error.WriteLine($"DECALE coffre t={s.Time:F1} <- loot t={c.t:F1} ({c.n} objets) à côté du joueur");
        }

        results.Add(new
        {
            file,
            ok = true,
            chests_opened = track.Count > 0 ? mine : (int?)null,
            chests_broken = broken,
            chests_in_gaps = gapCount,
            chests_lagged = lagged,
            player = owner?.PlayerName,
            team = owner?.TeamIndex,
            winning_team = replay.GameData?.WinningTeam,
            player_place = owner?.Placement,
            team_won = owner?.TeamIndex != null && replay.GameData?.WinningTeam != null && (uint)owner.TeamIndex == replay.GameData.WinningTeam,
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

class Search { public double Time; public double Age; public string Type; public uint Channel; }
class Pickup { public double Time; public FVector Pos; }

class ChestReader : FortniteReplayReader.ReplayReader
{
    public List<Search> Searches = new();
    public List<Pickup> Pickups = new();
    public List<string> ContainerLog = new();
    public Dictionary<FVector, double> LocTime = new(ReferenceEqualityComparer.Instance);
    readonly HashSet<uint> _searched = new();
    readonly HashSet<uint> _pickupSeen = new();
    readonly Dictionary<uint, double> _firstSeen = new();
    // heure de l'image du replay (avant : heure du GameState, trop rarement mise à jour -> décalages de 10-40 s)
    double _time => DemoTime;

    public ChestReader() : base(null, ParseMode.Full) { }

    protected override void OnChannelClosed(uint channelIndex, NetworkGUID? actor)
    {
        if (_firstSeen.ContainsKey(channelIndex)) ContainerLog.Add($"t={_time:F1} ch={channelIndex} FERME");
        base.OnChannelClosed(channelIndex, actor);
    }

    protected override void OnChannelOpened(uint channelIndex, NetworkGUID? actor)
    {
        base.OnChannelOpened(channelIndex, actor);
        _searched.Remove(channelIndex);
        _firstSeen.Remove(channelIndex);
        _pickupSeen.Remove(channelIndex);
    }

    protected override void OnExportRead(uint channelIndex, INetFieldExportGroup? exportGroup)
    {
        base.OnExportRead(channelIndex, exportGroup);
        switch (exportGroup)
        {
            case PlayerPawn pp when pp.ReplicatedMovement.HasValue && pp.ReplicatedMovement.Value.Location != null:
                LocTime[pp.ReplicatedMovement.Value.Location] = _time;
                break;
            case BaseContainer c:
                ContainerLog.Add($"t={_time:F1} ch={channelIndex} {c.GetType().Name} searched={c.bAlreadySearched} destroyed={c.bDestroyed} hp={c.Health}/{c.MaxHealth} anim={c.SearchAnimationCount}");
                if (!_firstSeen.ContainsKey(channelIndex)) _firstSeen[channelIndex] = _time;
                if ((c.bAlreadySearched || c.bDestroyed) && _searched.Add(channelIndex))
                    Searches.Add(new Search { Time = _time, Age = _time - _firstSeen[channelIndex], Type = c.bAlreadySearched ? "ouvert" : "casse", Channel = channelIndex });
                break;
            case FortPickup p:
                if (p.PawnWhoDroppedPickup is > 0) { _pickupSeen.Add(channelIndex); break; }
                var pos = p.LootInitialPosition ?? Channels[channelIndex]?.Actor?.Location
                          ?? (p.ReplicatedMovement.HasValue ? p.ReplicatedMovement.Value.Location : null);
                if (pos != null && _pickupSeen.Add(channelIndex))
                    Pickups.Add(new Pickup { Time = _time, Pos = pos });
                break;
        }
    }
}
