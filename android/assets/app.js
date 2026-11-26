"use strict";
const el = (id) => document.getElementById(id);
function node(tag, text, parent) {
  const n = document.createElement(tag);
  n.textContent = text;
  parent.append(n);
  return n;
}
function unpack(text) {
  const obj = JSON.parse(text);
  if (obj.error) throw Error(obj.error);
  return obj.data;
}
let current = "overview",
  previous = [],
  historyRows = [],
  groups = new Map();
function show(page, remember = true) {
  if (remember && current !== page) previous.push(current);
  current = page;
  for (const b of document.querySelectorAll("nav button")) {
    const selected = b.dataset.page === page;
    el(b.dataset.page).hidden = !selected;
    if (selected) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  window.scrollTo(0, 0);
}
function backTab() {
  if (!previous.length) return false;
  show(previous.pop(), false);
  return true;
}
for (const b of document.querySelectorAll("nav button"))
  b.onclick = () => show(b.dataset.page);
function theme() {
  const choice = el("theme").value;
  document.documentElement.dataset.theme =
    choice === "system"
      ? matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : choice;
}
el("theme").value = Local.theme();
theme();
el("theme").onchange = () => {
  Local.saveTheme(el("theme").value);
  theme();
};
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", theme);
function option(parent, value, text) {
  const o = node("option", text, parent);
  o.value = value;
}
function card(parent, title, detail) {
  const c = node("div", "", parent);
  c.className = "card";
  node("strong", title, c);
  node("small", detail, c);
  return c;
}
const archive = unpack(Local.evidence());
let games = 0,
  seasons = 0;
for (const [id, league] of Object.entries(archive.leagues)) {
  option(
    el("league"),
    id,
    { "en.1": "English Premier League", "de.1": "German Bundesliga" }[id] || id,
  );
  for (const record of league.holdouts) {
    games += record.source.n;
    seasons++;
  }
}
el("games").textContent = games.toLocaleString();
el("seasons").textContent = seasons;
function research() {
  const parent = el("research"),
    sources = el("sources");
  parent.replaceChildren();
  sources.replaceChildren();
  const league = archive.leagues[el("league").value];
  for (const r of league.holdouts) {
    const c = card(
      parent,
      r.source.season + " · " + r.source.n + " matches",
      "Frequency " +
        r.frequency.brier.toFixed(4) +
        "  /  Uniform " +
        r.uniform.brier.toFixed(4),
    );
    const bar = document.createElement("meter");
    bar.min = 0;
    bar.max = 1;
    bar.value = r.frequency.brier;
    bar.setAttribute("aria-label", "Frequency Brier score");
    c.append(bar);
  }
  for (const s of [league.train, ...league.holdouts.map((r) => r.source)])
    card(sources, s.season, s.url + " · SHA-256 " + s.sha256);
}
research();
el("league").onchange = research;
function names() {
  return el("market").value === "1X2"
    ? ["home", "draw", "away"]
    : ["first", "second"];
}
function prices() {
  const parent = el("prices");
  parent.replaceChildren();
  el("outcome").replaceChildren();
  el("result").replaceChildren();
  const defaults = {
    decimal: ["2", "3", "4"],
    fractional: ["1/1", "2/1", "3/1"],
    american: ["+100", "+200", "+300"],
  }[el("format").value];
  names().forEach((name, i) => {
    const label = node(
      "label",
      name.charAt(0).toUpperCase() + name.slice(1) + " price",
      parent,
    );
    const input = node("input", "", label);
    input.id = "price-" + name;
    input.value = defaults[i];
    input.maxLength = 80;
    option(el("outcome"), name, name);
  });
}
el("market").onchange = prices;
el("format").onchange = prices;
prices();
function percent(s) {
  return (
    (Number(s) * 100).toLocaleString(undefined, { maximumFractionDigits: 5 }) +
    "%"
  );
}
el("calculate").onclick = () => {
  const body = {
      market: el("market").value,
      format: el("format").value,
      prices: {},
    },
    parent = el("result");
  parent.replaceChildren();
  for (const name of names()) body.prices[name] = el("price-" + name).value;
  if (el("prob").value || el("basis").value)
    body.assumption = {
      outcome: el("outcome").value,
      probability: el("prob").value,
      basis: el("basis").value,
    };
  try {
    const r = unpack(Local.calculate(JSON.stringify(body)));
    card(
      parent,
      "Market summary",
      "Overround " +
        percent(r.overround) +
        " · Theoretical margin " +
        percent(r.theoretical_margin),
    );
    for (const [name, v] of Object.entries(r.outcomes))
      card(
        parent,
        name +
          " · " +
          Number(v.decimal).toLocaleString(undefined, {
            maximumSignificantDigits: 10,
          }),
        "Implied " +
          percent(v.implied) +
          " · Normalized " +
          percent(v.normalized) +
          " · Fair decimal " +
          Number(v.fair_decimal).toPrecision(6),
      );
    if (r.expected_value)
      card(
        parent,
        "Expected net per unit " + r.expected_value.net_per_unit,
        "Assumption " +
          r.expected_value.probability +
          " · " +
          r.expected_value.basis,
      );
  } catch (e) {
    card(parent, "Check your inputs", e.message);
  }
};
function refresh() {
  historyRows = unpack(Local.history()).observations;
  el("count").textContent = historyRows.length;
  const selected = el("series").value,
    query = el("query").value.trim().toLowerCase();
  groups = new Map();
  for (const r of historyRows) {
    const fields = [r.event, r.source, r.selection];
    if (!fields.join(" ").toLowerCase().includes(query)) continue;
    const key = JSON.stringify(fields);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }
  el("series").replaceChildren();
  for (const key of groups.keys())
    option(el("series"), key, JSON.parse(key).join(" · "));
  if (groups.has(selected)) el("series").value = selected;
  movement();
}
function movement() {
  const rows = groups.get(el("series").value) || [],
    parent = el("records"),
    chart = el("movement");
  parent.replaceChildren();
  chart.replaceChildren();
  if (!rows.length) {
    node(
      "p",
      historyRows.length
        ? "No matching observations."
        : "No observations imported.",
      parent,
    );
    return;
  }
  const times = new Map();
  for (const r of rows) {
    if (!times.has(r.at)) times.set(r.at, []);
    times.get(r.at).push(r);
  }
  const points = [...times].map(([at, items]) => ({
    t: Date.parse(at),
    y: items.length === 1 ? Number(items[0].decimal) : null,
  }));
  const valid = points.filter((p) => p.y !== null);
  if (valid.length) {
    const lo = Math.min(...valid.map((p) => p.y)),
      hi = Math.max(...valid.map((p) => p.y));
    const ns = "http://www.w3.org/2000/svg",
      svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 320 110");
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      "Historical decimal odds, " + lo + " to " + hi,
    );
    chart.append(svg);
    let last = null;
    for (const p of points) {
      if (p.y === null) {
        last = null;
        continue;
      }
      const x =
          10 +
          (300 * (p.t - points[0].t)) /
            Math.max(1, points[points.length - 1].t - points[0].t),
        y = hi === lo ? 55 : 95 - (80 * (p.y - lo)) / (hi - lo);
      if (last) {
        const line = document.createElementNS(ns, "line");
        for (const [k, v] of Object.entries({
          x1: last.x,
          y1: last.y,
          x2: x,
          y2: y,
          stroke: "currentColor",
          "stroke-width": 2,
        }))
          line.setAttribute(k, v);
        svg.append(line);
      }
      const dot = document.createElementNS(ns, "circle");
      dot.setAttribute("cx", x);
      dot.setAttribute("cy", y);
      dot.setAttribute("r", 3);
      dot.setAttribute("fill", "currentColor");
      svg.append(dot);
      last = { x, y };
    }
  }
  for (const [at, items] of [...times].reverse())
    card(
      parent,
      items.map((r) => r.decimal).join(" / ") +
        (items.length > 1 ? " · conflicting quotes" : ""),
      at + " · " + items[0].source,
    );
}
function documentResult(message) {
  el("docstatus").textContent = message;
  refresh();
}
for (const name of ["import", "csv", "json"])
  el(name).onclick = () => Local.selectDocument(name);
el("query").oninput = refresh;
el("series").onchange = movement;
refresh();
show("overview", false);
