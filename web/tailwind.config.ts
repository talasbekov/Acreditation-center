import type { Config } from "tailwindcss";

const config: Config = {
  // relative: пути считаются от этого файла, а не от каталога, из которого запущен next.
  content: {
    relative: true,
    files: [
      "./app/**/*.{js,ts,jsx,tsx,mdx}",
      "./components/**/*.{js,ts,jsx,tsx,mdx}",
      "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    ],
  },
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
      },
    },
  },
  plugins: [],
};

export default config;
