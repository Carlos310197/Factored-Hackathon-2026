import type { NextConfig } from "next";

// standalone: the web ships as a container on ECS Fargate Spot (not Amplify).
const nextConfig: NextConfig = { output: "standalone" };

export default nextConfig;
