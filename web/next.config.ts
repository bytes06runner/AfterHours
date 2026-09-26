import type { NextConfig } from "next";

// Hosts allowed to load dev-only resources (HMR). Next 16 blocks every host but localhost by
// default; WEB_DEV_ORIGINS (comma separated, see .env.example) adds more, e.g. 127.0.0.1.
const devOrigins = (process.env.WEB_DEV_ORIGINS ?? "")
  .split(",")
  .map((h) => h.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  allowedDevOrigins: devOrigins,
  // Keep QA screenshots free of the dev-mode badge.
  devIndicators: false,
};

export default nextConfig;
