import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12151c", paper: "#f7f6f2", panel: "#ffffff",
        stated: "#1f6feb", inferred: "#8250df",
        preserved: "#1a7f37", partial: "#bf8700", lost: "#cf222e", unresolved: "#8c6d1f",
      },
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"] },
    },
  },
  plugins: [],
};
export default config;
