// Simple script to add staggered animation delay to fade-in elements
document.addEventListener("DOMContentLoaded", () => {
  const fadeEls = document.querySelectorAll(".fade-in");
  fadeEls.forEach((el, i) => {
    el.style.animationDelay = `${i * 0.15}s`;
  });
});
