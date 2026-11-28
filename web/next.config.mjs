/**
 * В разработке Next.js проксирует запросы Django на `DJANGO_ORIGIN`
 * (по умолчанию http://127.0.0.1:8000), чтобы интерфейс и API жили на одном
 * origin и работали cookie сессии и CSRF. В бою то же самое делает nginx.
 *
 * Django-адреса заканчиваются на «/», поэтому редирект Next.js на адрес без
 * слеша отключён (skipTrailingSlashRedirect).
 */
const DJANGO = process.env.DJANGO_ORIGIN || "http://127.0.0.1:8000";

/** Пути, которые обслуживает Django, а не Next.js. */
const DJANGO_PATHS = [
  "api",
  "media",
  "static",
  "embankment",
  "operator-access",
  "auth_check",
  // Выгрузки старой АЦ — интерфейс вызывает их как есть.
  "download_json",
  "download_guests_json",
  "download_all_guests_json",
  "download_request_json",
  "download_photos",
  "download_file",
  "check_archive_status",
  "export_delta",
  "export_package",
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  output: "standalone",
  async rewrites() {
    return DJANGO_PATHS.flatMap((p) => [
      { source: `/${p}/:path*/`, destination: `${DJANGO}/${p}/:path*/` },
      { source: `/${p}/:path*`, destination: `${DJANGO}/${p}/:path*` },
    ]);
  },
};

export default nextConfig;
