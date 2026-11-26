// Keyboard verdicts: a, u, d press the matching button. A static script, so the page needs no eval.
document.addEventListener("keyup", (event) => {
  if (event.target.closest("input, textarea") || event.ctrlKey || event.metaKey || event.altKey) return;
  document.querySelector(`#card [data-key="${event.key.toLowerCase()}"]`)?.click();
});
