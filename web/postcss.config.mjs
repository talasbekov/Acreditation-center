import { fileURLToPath } from "node:url";

// Путь к конфигу Tailwind — от этого файла: next может быть запущен из другого каталога.
const config = fileURLToPath(new URL("./tailwind.config.ts", import.meta.url));

/** @type {import('postcss-load-config').Config} */
export default {
  plugins: {
    tailwindcss: { config },
    autoprefixer: {},
  },
};
