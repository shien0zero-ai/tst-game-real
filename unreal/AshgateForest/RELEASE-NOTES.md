UE5 5.8.4 Windows x64 forest demo: pistol surface and hand lighting integration.

Preserves authored curved normals and 4K PBR maps; restores source grip color/relief, adjusts metal/nonmetal/rubber response and leather gloves, and groups pistol/hand shadows. Existing M1911 remains playable with F3. Previous games, assets, audio, releases and saves are preserved.

1920x1080, Cinematic, internal resolution100%, original forest lighting/fog/foliage retained. Native RTX5080 routes averaged 45.82FPS across two measurements. The 60/80/100FPS targets remain unmet. 64スレッド群の候補はWindowsパッケージでGPUクラッシュ（DXGI_ERROR_DEVICE_HUNG）が発生したため非採用。測定不成立でFPS値はありません。既定32スレッド群を維持。クラッシュの内部原因は未確定で、ドライバー/エンジンのどちらかに断定していません。

Editor build, real PIE and Windows world checks passed (30 each). Exact generated ZIP must pass the existing 13-snapshot native input gate before publication. No new software installed or engine edited. Model detail and procedural reload limitations remain; this does not claim commercial FPS quality.

Extract the whole ZIP and run AshgateForest.exe. WASD/mouse, left-click shoot, right-click aim, R reload, N inspect, F2 scenery, F3 M1911, Esc pause/quit. See VALIDATION.md and the repository comparison report for raw measurements and images.
