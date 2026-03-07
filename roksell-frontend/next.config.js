/* eslint-disable @typescript-eslint/no-require-imports */
// next.config.js (CommonJS, funciona com next-pwa)
const withPWA = require("next-pwa")({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  runtimeCaching: [
    {
      urlPattern: ({ url }) => url.pathname.startsWith("/catalogo"),
      handler: "StaleWhileRevalidate",
    },
  ],
});

module.exports = withPWA({
  reactStrictMode: true,
  async redirects() {
    return [
      { source: "/portal", destination: "/roksell", permanent: true },
      { source: "/portal/:path*", destination: "/roksell/:path*", permanent: true },
      { source: "/roksell/catalog", destination: "/roksell/produtos", permanent: true },
    ];
  },
});
