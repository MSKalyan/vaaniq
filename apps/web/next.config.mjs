import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  transpilePackages: ["@nenuaikadu/shared"],
  webpack: (config) => {
    config.resolve.alias["@nenuaikadu/shared"] = path.resolve(
      __dirname,
      "../../packages/shared/index.ts",
    );
    return config;
  },
};

export default nextConfig;