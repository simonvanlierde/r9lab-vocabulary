// Keys for the verdicts, undo and pause, and the time a card spends hidden or paused, which each
// verdict reports in `away` so the server can leave it out of review_seconds. A static script, so
// the page needs no eval.
const pause = document.getElementById("pause");
const pausedNote = document.getElementById("paused");
const main = document.querySelector("main");
const KEYS = new Set(["a", "u", "d", "z"]);
let away = 0; // milliseconds the card on screen has been hidden or paused
let awaySince = null;
let card = document.getElementById("card");

function countAway() {
  const out = document.hidden || main.hidden;
  if (out && awaySince === null) awaySince = performance.now();
  if (!out && awaySince !== null) {
    away += performance.now() - awaySince;
    awaySince = null;
  }
}

function togglePause() {
  main.hidden = !main.hidden;
  pause.setAttribute("aria-pressed", String(main.hidden));
  pause.textContent = main.hidden ? "Resume" : "Pause";
  pausedNote.hidden = !main.hidden;
  countAway();
  if (!main.hidden) document.getElementById("card-tag")?.focus();
}

pause.hidden = false;
pause.addEventListener("click", togglePause);
document.addEventListener("visibilitychange", countAway);
countAway();

document.addEventListener("keydown", (event) => {
  if (event.repeat || event.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
  const key = event.key.toLowerCase();
  if (key === "p") return togglePause();
  // Nothing while paused or while a verdict is on its way, so a double press cannot judge the next card.
  if (!KEYS.has(key) || main.hidden || document.querySelector(".htmx-request")) return;
  document.querySelector(`#card [data-key="${key}"]`)?.click();
});

// Capture runs before htmx reads the form.
document.addEventListener(
  "submit",
  (event) => {
    const field = event.target.elements?.away;
    if (field) field.value = (away / 1000).toFixed(1);
  },
  true,
);

// A new card (not a progress update): its away time starts at zero, and focus goes to its tag.
document.addEventListener("htmx:after:settle", () => {
  if (document.getElementById("card") === card) return;
  card = document.getElementById("card");
  away = 0;
  document.getElementById("card-tag")?.focus();
});
