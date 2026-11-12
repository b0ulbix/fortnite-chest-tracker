# Third-party notices

## FortniteReplayDecompressor

Fortnite Chest Tracker reads replays with **FortniteReplayDecompressor** by Shiqan
(https://github.com/Shiqan/FortniteReplayDecompressor), released under the MIT License.
A copy of its source is in `vendor/FortniteReplayDecompressor`, with the changes listed in
`vendor/fortnite-chest-tracker.patch` (chests parsed in normal mode, current frame time exposed, season chest classes,
who searches a chest, gizmo actors, treasure prize chests, and the raw-probe hooks from LED-N's patched `ReplayReader.cs`).

```
MIT License

Copyright (c) 2020-2026 Shiqan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Python / Tcl-Tk / .NET runtime

The release executables bundle the Python runtime (PSF License), Tcl/Tk (BSD-style license) and the
.NET runtime (MIT License).

Fortnite is a trademark of Epic Games, Inc. This project is not affiliated with or endorsed by Epic Games.

## Fortnite-ChestCounter (LED-N)

The treasure detection (every treasure received is a `GA_TreasureHandler` ability granted to the recording player,
read from the raw `ActivatableAbilities` data) and the patched `Unreal.Core/ReplayReader.cs` + `RawProbe.cs` come from
**Fortnite-ChestCounter** by LED-N (https://github.com/LED-N/Fortnite-ChestCounter), MIT License.
The treasure-hunt catalog (weeks, prize ids, odds, Treasure Hours) is downloaded from its public `content/content.json`.

```
MIT License

Copyright (c) 2026 LED-N

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## LNXcounter (Linox-IDK)

The golden-chest prize reading (`PrizeTemplateId` / `OpeningPawn` of the animated treasure chest) is adapted from
**LNXcounter** by Linox-IDK (https://github.com/Linox-IDK/LNXcounter), MIT License.

```
MIT License

Copyright (c) 2026 Linox-IDK

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

