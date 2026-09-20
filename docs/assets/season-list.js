/* Local filtering only. All result rows are already present in the HTML. */
(() => {
  "use strict";
  const form = document.getElementById("season-filters");
  const tbody = document.getElementById("season-rows");
  if (!form || !tbody) return;

  const corpus = document.getElementById("corpus-filter");
  const model = document.getElementById("model-filter");
  const season = document.getElementById("season-filter");
  const query = document.getElementById("poem-search");
  const disagreement = document.getElementById("disagreement-filter");
  const count = document.getElementById("result-count");
  const empty = document.getElementById("no-results");
  const rows = [...tbody.querySelectorAll("tr")];
  const normalize = value => value.normalize("NFKC").toLocaleLowerCase("ja").replace(/\s+/gu, "");
  const searchable = new Map(rows.map(row => [row, normalize(row.dataset.search || "")]));

  function update() {
    const terms = query.value.trim().split(/\s+/u).filter(Boolean).map(normalize);
    let ogura = 0;
    let shuka = 0;
    for (const row of rows) {
      const data = row.dataset;
      const seasonMatches = season.value === "all" ||
        (model.value === "either" ? data.jev === season.value || data.gpt === season.value : data[model.value] === season.value);
      const visible = (corpus.value === "all" || data.corpus === corpus.value) && seasonMatches &&
        (!disagreement.checked || data.disagreement === "true") && terms.every(term => searchable.get(row).includes(term));
      row.hidden = !visible;
      if (visible) data.corpus === "ogura" ? ogura++ : shuka++;
    }
    count.textContent = `${ogura + shuka}首を表示（小倉${ogura}首・秀歌${shuka}首）`;
    empty.hidden = ogura + shuka !== 0;
  }

  // A link from a shared Shuka row should also work when filters hide Ogura.
  function revealAnchor() {
    const target = document.getElementById(location.hash.slice(1));
    if (!target || !tbody.contains(target) || !target.hidden) return;
    form.reset();
    update();
    target.scrollIntoView({block: "center"});
  }

  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  // Native reset defaults can run after the event's microtask checkpoint.
  // Re-filter in the next task, after all controls have their default values.
  form.addEventListener("reset", () => setTimeout(update, 0));
  tbody.addEventListener("click", event => {
    const link = event.target.closest('a[href^="#poem-"]');
    if (!link) return;
    const target = document.getElementById(link.getAttribute("href").slice(1));
    if (target && target.hidden) {
      form.reset();
      update();
    }
  });
  window.addEventListener("hashchange", revealAnchor);
  form.hidden = false;
  update();
  revealAnchor();
})();
