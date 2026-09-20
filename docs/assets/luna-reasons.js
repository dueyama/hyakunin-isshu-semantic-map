/* All output is rendered at build time; this script only filters local cards. */
(() => {
  "use strict";
  const form = document.getElementById("reasoned-filters");
  const container = document.getElementById("reasoned-poems");
  if (!form || !container) return;

  const corpus = document.getElementById("corpus-filter");
  const season = document.getElementById("season-filter");
  const query = document.getElementById("poem-search");
  const changed = document.getElementById("changed-filter");
  const count = document.getElementById("result-count");
  const empty = document.getElementById("no-results");
  const cards = [...container.querySelectorAll(".reasoned-poem")];
  const normalize = value => value.normalize("NFKC").toLocaleLowerCase("ja").replace(/\s+/gu, "");
  const searchable = new Map(cards.map(card => [card, normalize(card.dataset.search || "")]));

  function update() {
    const terms = query.value.trim().split(/\s+/u).filter(Boolean).map(normalize);
    let ogura = 0;
    let shuka = 0;
    for (const card of cards) {
      const data = card.dataset;
      const visible = (corpus.value === "all" || data.corpus === corpus.value) &&
        (season.value === "all" || data.season === season.value) &&
        (!changed.checked || data.changed === "true") &&
        terms.every(term => searchable.get(card).includes(term));
      card.hidden = !visible;
      if (visible) data.corpus === "ogura" ? ogura++ : shuka++;
    }
    count.textContent = `${ogura + shuka}首を表示（小倉${ogura}首・秀歌${shuka}首）`;
    empty.hidden = ogura + shuka !== 0;
  }

  function revealAnchor() {
    const card = document.getElementById(location.hash.slice(1));
    if (!card || !container.contains(card) || !card.hidden) return;
    form.reset();
    update();
    card.scrollIntoView({block: "center"});
  }

  form.addEventListener("submit", event => event.preventDefault());
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  form.addEventListener("reset", () => setTimeout(update, 0));
  window.addEventListener("hashchange", revealAnchor);
  form.hidden = false;
  update();
  revealAnchor();
})();
