/** Colors come from CSS variables (see index.css) so light/dark themes need no `dark:` variants. */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"), surface: v("surface"), raised: v("raised"), line: v("line"), ink: v("ink"), muted: v("muted"),
        onbrand: v("onbrand"),
        brand: { 50: v("b50"), 100: v("b100"), 500: v("b500"), 600: v("b600"), 700: v("b700") },
        sev: { low: v("low"), mod: v("mod"), high: v("high"), crit: v("crit") },
      },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], display: ["Plus Jakarta Sans", "Inter", "system-ui", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgb(15 23 42 / .04), 0 4px 16px rgb(15 23 42 / .05)", pop: "0 12px 40px rgb(15 23 42 / .18)" },
      borderRadius: { xl2: "1.25rem" },
    },
  },
  plugins: [],
};
