import json
from pathlib import Path

with open("color_benchmark_results.json", "r", encoding="utf-8") as f:
    bench_data = json.load(f)

artifact_dir = Path(r"C:\Users\Jean-Philippe\.gemini\antigravity\brain\b43ddede-0c54-4d07-9097-6d4e8226891f")
artifact_dir.mkdir(parents=True, exist_ok=True)
output_html = artifact_dir / "color_validation_ui.html"

# Sort palette alphabetically by name
sorted_palette = sorted(bench_data["palette"], key=lambda c: c["name"].lower())

pieces_json = json.dumps(bench_data["pieces"])
palette_json = json.dumps(sorted_palette)
total_evaluated = bench_data["total_evaluated"]
rgb_acc = bench_data["rgb_accuracy"]
ycrcb_acc = bench_data["ycrcb_accuracy"]
lab_acc = bench_data["lab_accuracy"]
rgb_correct = bench_data["rgb_correct"]
ycrcb_correct = bench_data["ycrcb_correct"]

html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Studio d'Étiquetage et Validation Colorimétrique YCrCb</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    :root {{
      --bg: #0b1120;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #0284c7;
      --accent: #38bdf8;
      --success: #10b981;
    }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .custom-scrollbar::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .custom-scrollbar::-webkit-scrollbar-track {{
      background: #1e293b;
    }}
    .custom-scrollbar::-webkit-scrollbar-thumb {{
      background: #475569;
      border-radius: 3px;
    }}
  </style>
</head>
<body class="p-4 md:p-6 min-h-screen">
  <div class="max-w-7xl mx-auto space-y-5">
    
    <!-- En-tête Principal -->
    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-xl md:text-2xl font-black tracking-tight text-white flex items-center gap-2">
            <span>🎯 Studio d'Étiquetage & Validation Colorimétrique</span>
          </h1>
          <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/80">
            YCrCb vs RGB
          </span>
        </div>
        <p class="text-xs md:text-sm text-slate-400 mt-1">
          Validez la <strong>vraie couleur</strong> des pièces pour alimenter le dataset d'apprentissage. Les tuiles validées sont automatiquement masquées de la file de travail.
        </p>
      </div>

      <!-- Actions Globales d'Apprentissage -->
      <div class="flex flex-wrap items-center gap-2.5">
        <button onclick="exportTrainingDataset()" class="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-950 transition active:scale-95">
          <span>📥 Exporter Dataset Apprentissage (JSON)</span>
        </button>
        <button onclick="exportSQLUpdates()" class="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 shadow-sm transition active:scale-95">
          <span>💾 Script SQL Corrections</span>
        </button>
        <button onclick="resetAllLabels()" class="px-2.5 py-2 rounded-xl text-xs text-rose-400 hover:bg-rose-950/40 border border-transparent hover:border-rose-900/60 transition" title="Réinitialiser les étiquettes locales">
          ↺
        </button>
      </div>
    </div>

    <!-- KPIs & Synthèse -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3.5">
      <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5">
        <div class="text-[11px] font-medium text-slate-400 uppercase tracking-wider">File de travail</div>
        <div class="text-xl md:text-2xl font-black text-white mt-1" id="kpi-remaining-count">{total_evaluated}</div>
        <div class="text-[11px] text-slate-500 mt-0.5">Pièces restantes à étiqueter</div>
      </div>
      <div class="bg-slate-900/80 border border-emerald-900/60 rounded-xl p-3.5 bg-gradient-to-br from-slate-900 to-emerald-950/30">
        <div class="text-[11px] font-medium text-emerald-400 uppercase tracking-wider flex items-center justify-between">
          <span>Étiquetées & Prêtes</span>
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        </div>
        <div class="text-xl md:text-2xl font-black text-emerald-300 mt-1" id="kpi-verified-count">0</div>
        <div class="text-[11px] text-emerald-400/80 mt-0.5 font-medium" id="kpi-verified-pct">0% complété</div>
      </div>
      <div class="bg-slate-900/80 border border-cyan-900/60 rounded-xl p-3.5 bg-gradient-to-br from-slate-900 to-cyan-950/30">
        <div class="text-[11px] font-medium text-cyan-400 uppercase tracking-wider">Succès YCrCb</div>
        <div class="text-xl md:text-2xl font-black text-cyan-300 mt-1" id="kpi-ycrcb">{ycrcb_acc}%</div>
        <div class="text-[11px] text-cyan-400/80 mt-0.5">{ycrcb_correct} / {total_evaluated} pièces</div>
      </div>
      <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5">
        <div class="text-[11px] font-medium text-rose-400 uppercase tracking-wider">Succès RGB Brut</div>
        <div class="text-xl md:text-2xl font-black text-rose-300 mt-1" id="kpi-rgb">{rgb_acc}%</div>
        <div class="text-[11px] text-slate-500 mt-0.5">{rgb_correct} / {total_evaluated} pièces</div>
      </div>
    </div>

    <!-- Barre d'outils et Filtres -->
    <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-1.5">
        <button onclick="setFilter('unverified')" id="btn-filter-unverified" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-cyan-600 text-white transition">
          ⚡ À étiqueter (<span id="btn-count-unverified">{total_evaluated}</span>)
        </button>
        <button onclick="setFilter('verified')" id="btn-filter-verified" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition">
          ✓ Déjà validées (<span id="btn-count-verified">0</span>)
        </button>
        <button onclick="setFilter('all')" id="btn-filter-all" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition">
          Toutes ({total_evaluated})
        </button>
        <button onclick="setFilter('ycrcb_win')" id="btn-filter-ycrcb_win" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition">
          YCrCb bat RGB
        </button>
        <button onclick="setFilter('disagree')" id="btn-filter-disagree" class="filter-btn px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition">
          Désaccord YCrCb / Modèle
        </button>
      </div>

      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
          <input type="checkbox" id="toggle-hide-verified" checked onchange="render()" class="rounded bg-slate-950 border-slate-700 text-cyan-500 focus:ring-0">
          <span>Masquer les validées</span>
        </label>
        <input type="text" id="search-input" oninput="render()" placeholder="Filtrer couleur, part ID ou UUID..." class="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-56">
        <span class="text-xs text-slate-400 font-mono" id="showing-count">{total_evaluated} pièces</span>
      </div>
    </div>

    <!-- Grille des pièces -->
    <div id="pieces-grid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <!-- Rendu dynamique -->
    </div>
  </div>

  <!-- Modal Aperçu Image Grand Format -->
  <div id="zoom-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4" onclick="closeZoom()">
    <div class="bg-slate-900 border border-slate-700 p-3 rounded-2xl max-w-lg w-full flex flex-col items-center gap-3" onclick="event.stopPropagation()">
      <img id="zoom-img" src="" class="w-full max-h-96 object-contain rounded-xl bg-slate-950 border border-slate-800" alt="Zoom Crop">
      <div class="flex items-center justify-between w-full text-xs text-slate-400 px-1">
        <span id="zoom-caption" class="font-mono"></span>
        <button onclick="closeZoom()" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded-lg">Fermer</button>
      </div>
    </div>
  </div>

  <script>
    const rawPieces = {pieces_json};
    // Palette triée rigoureusement par ordre alphabétique
    const palette = {palette_json};
    palette.sort((a, b) => a.name.localeCompare(b.name, 'fr', {{ sensitivity: 'base' }}));

    // Chargement des vérifications existantes depuis le localStorage
    const STORAGE_KEY = 'sorter_color_labels_v1';
    let verifiedLabels = {{}};
    try {{
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) verifiedLabels = JSON.parse(saved);
    }} catch (e) {{
      console.warn('LocalStorage error:', e);
    }}

    // Par défaut : afficher les pièces à étiqueter (les validées sont cachées de la file)
    let currentFilter = 'unverified';

    function saveLabels() {{
      try {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify(verifiedLabels));
      }} catch (e) {{}}
      updateKPIs();
    }}

    function setTrueColor(uuid, colorId, colorName, colorHex) {{
      verifiedLabels[uuid] = {{
        color_id: parseInt(colorId),
        color_name: colorName,
        color_hex: colorHex,
        verified_at: new Date().toISOString()
      }};
      saveLabels();
      render();
    }}

    function confirmSelectColor(uuid) {{
      const sel = document.getElementById('select-color-' + uuid);
      if (!sel || !sel.value) {{
        alert("Veuillez sélectionner une couleur dans la liste déroulante.");
        return;
      }}
      const opt = sel.options[sel.selectedIndex];
      setTrueColor(uuid, sel.value, opt.dataset.name, opt.dataset.hex);
    }}

    function clearLabel(uuid) {{
      delete verifiedLabels[uuid];
      saveLabels();
      render();
    }}

    function resetAllLabels() {{
      if (confirm('Voulez-vous effacer toutes vos étiquettes personnalisées enregistrées dans le navigateur ?')) {{
        verifiedLabels = {{}};
        saveLabels();
        render();
      }}
    }}

    function updateKPIs() {{
      const count = Object.keys(verifiedLabels).length;
      const remaining = rawPieces.length - count;
      const pct = Math.round((count / rawPieces.length) * 100);

      document.getElementById('kpi-verified-count').textContent = count;
      document.getElementById('kpi-remaining-count').textContent = remaining;
      document.getElementById('kpi-verified-pct').textContent = `${{pct}}% complété`;
      
      document.getElementById('btn-count-verified').textContent = count;
      document.getElementById('btn-count-unverified').textContent = remaining;
    }}

    function setFilter(f) {{
      currentFilter = f;
      document.querySelectorAll('.filter-btn').forEach(b => {{
        b.classList.remove('bg-cyan-600', 'text-white');
        b.classList.add('bg-slate-800', 'text-slate-300');
      }});
      const active = document.getElementById('btn-filter-' + f);
      if (active) {{
        active.classList.add('bg-cyan-600', 'text-white');
        active.classList.remove('bg-slate-800', 'text-slate-300');
      }}
      render();
    }}

    function openZoom(src, caption) {{
      document.getElementById('zoom-img').src = src;
      document.getElementById('zoom-caption').textContent = caption;
      document.getElementById('zoom-modal').classList.remove('hidden');
    }}

    function closeZoom() {{
      document.getElementById('zoom-modal').classList.add('hidden');
    }}

    function render() {{
      const q = document.getElementById('search-input').value.toLowerCase().trim();
      const hideVerifiedCheckbox = document.getElementById('toggle-hide-verified').checked;
      const grid = document.getElementById('pieces-grid');
      grid.innerHTML = '';

      let filtered = rawPieces.filter(p => {{
        const isVerified = Boolean(verifiedLabels[p.uuid]);
        const trueColorId = isVerified ? verifiedLabels[p.uuid].color_id : p.initial_model_color_id;
        const isYCrCbCorrect = p.ycrcb_pred.id === trueColorId;
        const isRgbCorrect = p.rgb_pred.id === trueColorId;
        const isModelDisagree = p.ycrcb_pred.id !== p.initial_model_color_id;

        // Si l'option "Masquer les validées" est active, masquer sauf si on consulte expressément l'onglet "Déjà validées"
        if (currentFilter !== 'verified') {{
          if (currentFilter === 'unverified' && isVerified) return false;
          if (hideVerifiedCheckbox && isVerified) return false;
        }} else {{
          if (!isVerified) return false;
        }}

        if (currentFilter === 'ycrcb_win' && !(isYCrCbCorrect && !isRgbCorrect)) return false;
        if (currentFilter === 'disagree' && !isModelDisagree) return false;

        if (q) {{
          const matchInitial = (p.initial_model_color_name || '').toLowerCase().includes(q);
          const matchTrue = isVerified ? verifiedLabels[p.uuid].color_name.toLowerCase().includes(q) : false;
          const matchRgb = (p.rgb_pred.name || '').toLowerCase().includes(q);
          const matchYcrcb = (p.ycrcb_pred.name || '').toLowerCase().includes(q);
          const matchPart = (p.part_id || '').toLowerCase().includes(q);
          const matchUuid = p.uuid.toLowerCase().includes(q);
          if (!matchInitial && !matchTrue && !matchRgb && !matchYcrcb && !matchPart && !matchUuid) return false;
        }}
        return true;
      }});

      document.getElementById('showing-count').textContent = `${{filtered.length}} pièces affichées`;

      if (filtered.length === 0) {{
        grid.innerHTML = `
          <div class="col-span-full py-16 text-center space-y-3 bg-slate-900/40 border border-slate-800/80 rounded-2xl">
            <div class="text-3xl">🎉</div>
            <div class="text-base font-bold text-slate-200">Aucune pièce à afficher dans cette vue !</div>
            <div class="text-xs text-slate-400 max-w-md mx-auto">
              ${{currentFilter === 'unverified' || hideVerifiedCheckbox 
                ? 'Toutes les pièces visibles ont été validées ou filtrées. Vous pouvez revoir vos choix dans l\\'onglet "✓ Déjà validées".' 
                : 'Aucune pièce ne correspond à vos critères de recherche.'}}
            </div>
            ${{currentFilter === 'unverified' ? `<button onclick="setFilter('verified')" class="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 text-white rounded-xl text-xs font-bold shadow-md transition">Voir les pièces validées</button>` : ''}}
          </div>
        `;
        return;
      }}

      filtered.forEach(p => {{
        const userLabel = verifiedLabels[p.uuid];
        const isVerified = Boolean(userLabel);
        const trueColorId = isVerified ? userLabel.color_id : p.initial_model_color_id;
        const trueColorName = isVerified ? userLabel.color_name : p.initial_model_color_name;
        const trueColorHex = isVerified ? userLabel.color_hex : (palette.find(c => c.id === trueColorId)?.hex || '#808080');

        const ycrcbCorrect = p.ycrcb_pred.id === trueColorId;
        const rgbCorrect = p.rgb_pred.id === trueColorId;
        const ycrcbWon = ycrcbCorrect && !rgbCorrect;

        const card = document.createElement('div');
        card.className = `bg-slate-900/90 border ${{isVerified ? 'border-emerald-600/90 ring-1 ring-emerald-500/20' : ycrcbWon ? 'border-cyan-600/80 ring-1 ring-cyan-500/20' : 'border-slate-800'}} rounded-2xl p-4 flex flex-col justify-between space-y-3 shadow-md transition hover:border-slate-600`;

        // Génération des options du dropdown couleur (triées par ordre alphabétique)
        let optionsHtml = '<option value="">-- Choisir une autre couleur --</option>';
        palette.forEach(c => {{
          const sel = c.id === trueColorId ? 'selected' : '';
          optionsHtml += `<option value="${{c.id}}" data-name="${{c.name}}" data-hex="${{c.hex}}" ${{sel}}>${{c.name}} (#${{c.id}})</option>`;
        }});

        card.innerHTML = `
          <!-- Header de la Pièce -->
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <div onclick="openZoom('${{p.thumbnail_b64}}', '${{p.part_name || p.part_id}} (${{p.uuid.slice(0, 8)}})')" class="w-16 h-16 rounded-xl overflow-hidden bg-slate-950 border border-slate-700/80 flex-shrink-0 flex items-center justify-center cursor-zoom-in hover:scale-105 transition" title="Cliquer pour agrandir le crop">
                ${{p.thumbnail_b64 ? `<img src="${{p.thumbnail_b64}}" class="w-full h-full object-cover">` : '<span class="text-xs text-slate-500">No img</span>'}}
              </div>
              <div>
                <div class="text-[11px] font-mono text-slate-400 flex items-center gap-1.5">
                  <span class="bg-slate-800 px-1.5 py-0.5 rounded text-slate-300 font-semibold">${{p.part_id || 'Piece'}}</span>
                  <span>${{p.uuid.slice(0, 8)}}</span>
                </div>
                <div class="text-xs font-semibold text-slate-200 truncate max-w-[180px] mt-0.5" title="${{p.part_name || ''}}">
                  ${{p.part_name || 'Part'}}
                </div>
                <div class="text-[10px] text-slate-500 mt-0.5">
                  ${{p.crop_count}} vues C4 analysées
                </div>
              </div>
            </div>

            <div class="flex flex-col items-end gap-1">
              ${{isVerified ? '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700">✓ Validé</span>' : '<span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">À étiqueter</span>'}}
              ${{ycrcbWon ? '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800">YCrCb Gagnant</span>' : ''}}
            </div>
          </div>

          <!-- Section VRAIE COULEUR (Cœur de l'étiquetage pour l'apprentissage) -->
          <div class="bg-slate-950/80 border ${{isVerified ? 'border-emerald-800/80' : 'border-slate-800'}} rounded-xl p-3 space-y-2">
            <div class="flex items-center justify-between text-xs">
              <span class="text-slate-400 font-medium">Vraie Couleur (Ground Truth) :</span>
              ${{isVerified ? `<button onclick="clearLabel('${{p.uuid}}')" class="text-[10px] text-slate-500 hover:text-rose-400 underline">Dé-valider</button>` : ''}}
            </div>
            
            <div class="flex items-center gap-2">
              <span class="w-4 h-4 rounded-full border border-white/20 flex-shrink-0 shadow-sm" style="background-color: ${{trueColorHex}};"></span>
              <span class="text-xs font-bold text-white flex-1 truncate">${{trueColorName}}</span>
              <span class="text-[10px] font-mono text-slate-400">ID: ${{trueColorId}}</span>
            </div>

            <!-- Actions Rapides en 1 Clic -->
            <div class="pt-1 flex flex-wrap items-center gap-1.5 text-[11px]">
              <span class="text-[10px] text-slate-500 mr-0.5">Valider vite :</span>
              <button onclick="setTrueColor('${{p.uuid}}', '${{p.ycrcb_pred.id}}', '${{p.ycrcb_pred.name}}', '${{p.ycrcb_pred.hex}}')" class="px-2 py-1 rounded-lg bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-800 text-cyan-200 font-semibold transition active:scale-95" title="Définir YCrCb comme la vraie couleur">
                YCrCb (${{p.ycrcb_pred.name}})
              </button>
              <button onclick="setTrueColor('${{p.uuid}}', '${{p.rgb_pred.id}}', '${{p.rgb_pred.name}}', '${{p.rgb_pred.hex}}')" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition active:scale-95" title="Définir RGB comme la vraie couleur">
                RGB (${{p.rgb_pred.name}})
              </button>
              ${{p.initial_model_color_id && p.initial_model_color_id !== p.ycrcb_pred.id && p.initial_model_color_id !== p.rgb_pred.id ? `
              <button onclick="setTrueColor('${{p.uuid}}', '${{p.initial_model_color_id}}', '${{p.initial_model_color_name}}', '${{trueColorHex}}')" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 transition active:scale-95" title="Définir la prédiction initiale de la machine comme la vraie couleur">
                Modèle (${{p.initial_model_color_name}})
              </button>
              ` : ''}}
            </div>

            <!-- Sélecteur complet de catalogue (Alphabétique) avec Bouton Confirmer -->
            <div class="pt-1 flex items-center gap-1.5">
              <select id="select-color-${{p.uuid}}" class="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer">
                ${{optionsHtml}}
              </select>
              <button onclick="confirmSelectColor('${{p.uuid}}')" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-sm transition active:scale-95 flex items-center gap-1 flex-shrink-0" title="Confirmer la couleur choisie dans la liste">
                <span>✓ Confirmer</span>
              </button>
            </div>
          </div>

          <!-- Comparaison Prédictions YCrCb vs RGB -->
          <div class="grid grid-cols-2 gap-2 text-xs pt-1">
            <!-- YCrCb -->
            <div class="p-2.5 rounded-xl ${{ycrcbCorrect ? 'bg-cyan-950/40 border border-cyan-700/80 shadow-sm' : 'bg-slate-950/50 border border-slate-800'}}">
              <div class="flex items-center justify-between text-[10px] font-semibold text-slate-400 mb-1">
                <span class="${{ycrcbCorrect ? 'text-cyan-300 font-bold' : ''}}">YCrCb Découplé</span>
                <span>${{ycrcbCorrect ? '✅ Juste' : '❌ Faux'}}</span>
              </div>
              <div class="font-bold flex items-center gap-1.5 ${{ycrcbCorrect ? 'text-cyan-200' : 'text-slate-300'}}">
                <span class="w-2.5 h-2.5 rounded-full inline-block border border-white/20 flex-shrink-0" style="background-color: ${{p.ycrcb_pred.hex}};"></span>
                <span class="truncate" title="${{p.ycrcb_pred.name}}">${{p.ycrcb_pred.name}}</span>
              </div>
              <div class="text-[10px] text-slate-500 mt-1 font-mono">Dist: ${{p.ycrcb_pred.dist}}</div>
            </div>

            <!-- RGB -->
            <div class="p-2.5 rounded-xl ${{rgbCorrect ? 'bg-emerald-950/40 border border-emerald-800/80 shadow-sm' : 'bg-slate-950/50 border border-slate-800'}}">
              <div class="flex items-center justify-between text-[10px] font-semibold text-slate-400 mb-1">
                <span class="${{rgbCorrect ? 'text-emerald-300 font-bold' : ''}}">RGB Brut</span>
                <span>${{rgbCorrect ? '✅ Juste' : '❌ Faux'}}</span>
              </div>
              <div class="font-bold flex items-center gap-1.5 ${{rgbCorrect ? 'text-emerald-200' : 'text-slate-300'}}">
                <span class="w-2.5 h-2.5 rounded-full inline-block border border-white/20 flex-shrink-0" style="background-color: ${{p.rgb_pred.hex}};"></span>
                <span class="truncate" title="${{p.rgb_pred.name}}">${{p.rgb_pred.name}}</span>
              </div>
              <div class="text-[10px] text-slate-500 mt-1 font-mono">Dist: ${{p.rgb_pred.dist}}</div>
            </div>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    // Exportation du dataset structuré pour l'entraînement
    function exportTrainingDataset() {{
      const exportList = [];
      rawPieces.forEach(p => {{
        const userLabel = verifiedLabels[p.uuid];
        if (userLabel) {{
          exportList.push({{
            piece_uuid: p.uuid,
            part_id: p.part_id,
            part_name: p.part_name,
            verified_color_id: userLabel.color_id,
            verified_color_name: userLabel.color_name,
            verified_color_hex: userLabel.color_hex,
            crop_count: p.crop_count,
            mean_ycrcb: p.mean_ycrcb,
            mean_rgb: p.mean_rgb,
            verified_at: userLabel.verified_at
          }});
        }}
      }});

      if (exportList.length === 0) {{
        alert("Vous n'avez pas encore étiqueté de pièces manuellement ! Cliquez sur les boutons de validation ou sélectionnez des couleurs pour étiqueter vos pièces avant d'exporter.");
        return;
      }}

      const blob = new Blob([JSON.stringify(exportList, null, 2)], {{ type: 'application/json' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dataset_apprentissage_couleurs_${{exportList.length}}_pieces.json`;
      a.click();
      URL.revokeObjectURL(url);
    }}

    // Exportation du script SQL pour injecter dans local_state.sqlite
    function exportSQLUpdates() {{
      const keys = Object.keys(verifiedLabels);
      if (keys.length === 0) {{
        alert("Aucune pièce étiquetée pour générer le script SQL.");
        return;
      }}
      let sql = `-- Script d'injection des vraies couleurs dans local_state.sqlite\n-- Généré le ${{new Date().toLocaleString()}}\n\n`;
      keys.forEach(uuid => {{
        const l = verifiedLabels[uuid];
        sql += `UPDATE piece_records SET color_corrected_id = '${{l.color_id}}' WHERE uuid = '${{uuid}}';\n`;
      }});

      const blob = new Blob([sql], {{ type: 'text/sql' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `corrections_couleurs_${{keys.length}}_pieces.sql`;
      a.click();
      URL.revokeObjectURL(url);
    }}

    updateKPIs();
    render();
  </script>
</body>
</html>
"""

output_html.write_text(html_content, encoding="utf-8")
print("Updated UI generated at:", output_html)
