/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["../static/**/*.html", "../static/assets/**/*.js"],
  theme: {
    extend: {
      colors: {
        cream: { 50: "#FFFBF5", 100: "#FBF3E6", 200: "#F3E3CB", 300: "#E9D2AF" },
        clay: { 100: "#F8E3D8", 500: "#C65A2E", 600: "#A94A23", 700: "#8A3B1C" },
        ink: { 900: "#1E2B26", 800: "#2B3A34", 700: "#3A4A43", 500: "#56655E" },
        sage: { 100: "#E4ECE4", 200: "#CBDACD", 600: "#4F6F5D", 700: "#3E5A4A" },
        sun: { 200: "#F8E2B0", 300: "#F2C66D" },
      },
      fontFamily: {
        display: ['"Iowan Old Style"', '"Palatino Linotype"', "Palatino", "Georgia", "ui-serif", "serif"],
        sans: ["ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", '"Helvetica Neue"', "Arial", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(30,43,38,.06), 0 8px 24px -8px rgba(30,43,38,.12)",
      },
    },
  },
  plugins: [],
};
