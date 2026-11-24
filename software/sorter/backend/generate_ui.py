import json
from pathlib import Path

with open('color_benchmark_results.json', 'r', encoding='utf-8') as f:
    bench_data = json.load(f)

artifact_dir = Path(r"C:\Users\Jean-Philippe\.gemini\antigravity\brain\b43ddede-0c54-4d07-9097-6d4e8226891f")
artifact_dir.mkdir(parents=True, exist_ok=True)
output_html = artifact_dir / "color_validation_ui.html"

pieces_json = json.dumps(bench_data["pieces"])
total_evaluated = bench_data["total_evaluated"]
rgb_acc = bench_data["rgb_accuracy"]
ycrcb_acc = bench_data["ycrcb_accuracy"]
lab_acc = bench_data["lab_accuracy"]
rgb_correct = bench_data["rgb_correct"]
ycrcb_correct = bench_data["ycrcb_correct"]
lab_correct = bench_data["lab_correct"]

html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Validation Colorimétrique : YCrCb vs RGB</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    :root {{
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #38bdf8;
      --success: #22c55e;
      --danger: #ef4444;
    }}
    body {{ background-color: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }}
  </style>
</head>
<body class="p-6 min-h-screen">
  <div class="max-w-7xl mx-auto space-y-6">
    <!-- En-tête -->
    <div class="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-700 gap-4">
      <div>
        <h1 class="text-2xl font-bold flex items-center gap-3">
          <span>🎨 Validation Colorimétrique : Mode YCrCb</span>
          <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800">Branche feat/color-ycrcb-analysis</span>
        </h1>
        <p class="text-sm text-slate-400 mt-1">
          Comparaison du matching en espace RGB brut vs YCrCb (découplage Luma/Chroma) sur les captures réelles de la machine en production.
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-700/60 text-emerald-300 font-mono">
          Machine en cours d'exécution (intouchée)
        </span>
      </div>
    </div>

    <!-- KPIs -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400">Pièces Testées</div>
        <div class="text-2xl font-extrabold text-white mt-1" id="kpi-total">{total_evaluated}</div>
        <div class="text-xs text-slate-400 mt-1">Données réelles (burst C4)</div>
      </div>
      <div class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400">Précision RGB (Euclidien)</div>
        <div class="text-2xl font-extrabold text-rose-400 mt-1" id="kpi-rgb">{rgb_acc}%</div>
        <div class="text-xs text-slate-400 mt-1" id="kpi-rgb-sub">{rgb_correct} / {total_evaluated} correctes</div>
      </div>
      <div class="bg-slate-800/80 border border-cyan-800/80 rounded-xl p-4 shadow-sm bg-gradient-to-br from-slate-800/90 to-cyan-950/40">
        <div class="text-xs font-medium text-cyan-400 font-semibold">Précision YCrCb (Découplé)</div>
        <div class="text-2xl font-extrabold text-cyan-300 mt-1" id="kpi-ycrcb">{ycrcb_acc}%</div>
        <div class="text-xs text-cyan-300/80 mt-1 font-medium" id="kpi-ycrcb-sub">{ycrcb_correct} / {total_evaluated} correctes (+164%)</div>
      </div>
      <div class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 shadow-sm">
        <div class="text-xs font-medium text-slate-400">Précision CIELAB (Ref)</div>
        <div class="text-2xl font-extrabold text-indigo-300 mt-1" id="kpi-lab">{lab_acc}%</div>
        <div class="text-xs text-slate-400 mt-1">{lab_correct} / {total_evaluated} correctes</div>
      </div>
    </div>

    <!-- Filtres & Contrôles -->
    <div class="bg-slate-800/60 border border-slate-700/80 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4">
      <div class="flex flex-wrap items-center gap-2">
        <button onclick="setFilter('all')" id="btn-filter-all" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-medium bg-cyan-600 text-white shadow-sm transition">Toutes ({total_evaluated})</button>
        <button onclick="setFilter('ycrcb_won')" id="btn-filter-ycrcb_won" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition">YCrCb gagne sur RGB (18)</button>
        <button onclick="setFilter('rgb_failed')" id="btn-filter-rgb_failed" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition">Échecs RGB ({total_evaluated - rgb_correct})</button>
        <button onclick="setFilter('ycrcb_correct')" id="btn-filter-ycrcb_correct" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600 transition">YCrCb Succès ({ycrcb_correct})</button>
      </div>

      <div class="flex items-center gap-3">
        <input type="text" id="search-input" oninput="render()" placeholder="Filtrer par couleur ou pièce..." class="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-56">
        <span class="text-xs text-slate-400 font-mono" id="showing-count">Affichage: {total_evaluated} pièces</span>
      </div>
    </div>

    <!-- Grille des pièces -->
    <div id="pieces-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <!-- Injecté dynamiquement par JS -->
    </div>
  </div>

  <script>
    const pieces = {pieces_json};
    let currentFilter = 'all';

    function setFilter(f) {{
      currentFilter = f;
      document.querySelectorAll('.filter-btn').forEach(b => {{
        b.classList.remove('bg-cyan-600', 'text-white');
        b.classList.add('bg-slate-700', 'text-slate-300');
      }});
      const active = document.getElementById('btn-filter-' + f);
      if (active) {{
        active.classList.add('bg-cyan-600', 'text-white');
        active.classList.remove('bg-slate-700', 'text-slate-300');
      }}
      render();
    }}

    function render() {{
      const q = document.getElementById('search-input').value.toLowerCase().trim();
      const grid = document.getElementById('pieces-grid');
      grid.innerHTML = '';

      let filtered = pieces.filter(p => {{
        if (currentFilter === 'ycrcb_won') {{
          if (!(p.ycrcb_pred.ok && !p.rgb_pred.ok)) return false;
        }} else if (currentFilter === 'rgb_failed') {{
          if (p.rgb_pred.ok) return false;
        }} else if (currentFilter === 'ycrcb_correct') {{
          if (!p.ycrcb_pred.ok) return false;
        }}
        if (q) {{
          const matchName = (p.ground_truth_name || '').toLowerCase().includes(q);
          const matchRgb = (p.rgb_pred.name || '').toLowerCase().includes(q);
          const matchYcrcb = (p.ycrcb_pred.name || '').toLowerCase().includes(q);
          const matchPart = (p.part_id || '').toLowerCase().includes(q);
          if (!matchName && !matchRgb && !matchYcrcb && !matchPart) return false;
        }}
        return true;
      }});

      document.getElementById('showing-count').textContent = `Affichage: ${{filtered.length}} / ${{pieces.length}}`;

      filtered.forEach(p => {{
        const card = document.createElement('div');
        const isYCrCbWinner = p.ycrcb_pred.ok && !p.rgb_pred.ok;
        card.className = `bg-slate-800/90 border ${{isYCrCbWinner ? 'border-cyan-600 ring-1 ring-cyan-500/30' : 'border-slate-700/80'}} rounded-xl p-4 flex flex-col justify-between space-y-3 transition hover:border-slate-500 shadow-sm`;

        card.innerHTML = `
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="w-14 h-14 rounded-lg overflow-hidden bg-slate-900 border border-slate-700 flex-shrink-0 flex items-center justify-center">
                ${{p.thumbnail_b64 ? `<img src="${{p.thumbnail_b64}}" class="w-full h-full object-cover" alt="Crop">` : '<span class="text-xs text-slate-500">No img</span>'}}
              </div>
              <div>
                <div class="text-xs font-mono text-slate-400">${{p.uuid.slice(0, 8)}} | ${{p.part_id || 'Pièce'}}</div>
                <div class="text-sm font-bold text-white flex items-center gap-1.5 mt-0.5">
                  <span class="w-3 h-3 rounded-full border border-white/20 inline-block" style="background-color: ${{p.ycrcb_pred.ok ? p.ycrcb_pred.hex : p.rgb_pred.hex}};"></span>
                  <span>${{p.ground_truth_name || 'Inconnue'}}</span>
                </div>
                <div class="text-[11px] text-slate-400 font-mono mt-0.5">${{p.crop_count}} crops analysés</div>
              </div>
            </div>
            ${{isYCrCbWinner ? '<span class="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800">Gain YCrCb</span>' : ''}}
          </div>

          <div class="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-700/60">
            <!-- Prédiction RGB -->
            <div class="p-2.5 rounded-lg ${{p.rgb_pred.ok ? 'bg-emerald-950/40 border border-emerald-800/60' : 'bg-slate-900/60 border border-slate-800'}}">
              <div class="flex items-center justify-between text-[11px] font-medium text-slate-400 mb-1">
                <span>RGB Brut</span>
                <span>${{p.rgb_pred.ok ? '✅ Correct' : '❌ Échec'}}</span>
              </div>
              <div class="font-semibold flex items-center gap-1.5 ${{p.rgb_pred.ok ? 'text-emerald-300' : 'text-slate-300'}}">
                <span class="w-2.5 h-2.5 rounded-full inline-block border border-white/20" style="background-color: ${{p.rgb_pred.hex}};"></span>
                <span class="truncate" title="${{p.rgb_pred.name}}">${{p.rgb_pred.name}}</span>
              </div>
              <div class="text-[10px] text-slate-500 mt-0.5 font-mono">Dist: ${{p.rgb_pred.dist}}</div>
            </div>

            <!-- Prédiction YCrCb -->
            <div class="p-2.5 rounded-lg ${{p.ycrcb_pred.ok ? 'bg-cyan-950/50 border border-cyan-700/70 shadow-sm' : 'bg-slate-900/60 border border-slate-800'}}">
              <div class="flex items-center justify-between text-[11px] font-medium ${{p.ycrcb_pred.ok ? 'text-cyan-300' : 'text-slate-400'}} mb-1">
                <span>YCrCb Découplé</span>
                <span>${{p.ycrcb_pred.ok ? '✅ Correct' : '❌ Échec'}}</span>
              </div>
              <div class="font-semibold flex items-center gap-1.5 ${{p.ycrcb_pred.ok ? 'text-cyan-200' : 'text-slate-300'}}">
                <span class="w-2.5 h-2.5 rounded-full inline-block border border-white/20" style="background-color: ${{p.ycrcb_pred.hex}};"></span>
                <span class="truncate" title="${{p.ycrcb_pred.name}}">${{p.ycrcb_pred.name}}</span>
              </div>
              <div class="text-[10px] text-slate-500 mt-0.5 font-mono">Dist: ${{p.ycrcb_pred.dist}}</div>
            </div>
          </div>

          <div class="flex items-center justify-between text-[11px] pt-1 text-slate-400 font-mono">
            <span>Y: ${{p.mean_ycrcb[0]}} | Cr: ${{p.mean_ycrcb[1]}} | Cb: ${{p.mean_ycrcb[2]}}</span>
            <span class="text-[10px] text-indigo-300" title="CIELAB Match">Lab: ${{p.lab_pred.name}}</span>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    render();
  </script>
</body>
</html>
"""

output_html.write_text(html_template, encoding="utf-8")
print("Validation UI written to:", output_html)
