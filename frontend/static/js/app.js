// Page behaviour shared by every screen. Kept in a file (not inline) so the
// Content-Security-Policy can forbid inline scripts entirely.

// Close the language menu when clicking elsewhere or pressing Escape.
document.addEventListener("click", (e) => {
  document.querySelectorAll("details.lang-menu[open]").forEach((m) => {
    if (!m.contains(e.target)) m.removeAttribute("open");
  });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.querySelectorAll("details.lang-menu[open]").forEach((m) => m.removeAttribute("open"));
});

// Ask before destructive actions: <form data-confirm="..."> or <button data-confirm="...">.
document.addEventListener("submit", (e) => {
  const form = e.target;
  const button = e.submitter;
  const message = (button && button.dataset.confirm) || form.dataset.confirm;
  if (message && !window.confirm(message)) e.preventDefault();
});

// <select data-autosubmit> submits its form as soon as a new option is picked.
document.addEventListener("change", (e) => {
  if (e.target.matches("select[data-autosubmit]")) e.target.form.submit();
});
