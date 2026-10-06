import "server-only";
import { z } from "zod";

const Env = z.object({
  IDP_URL: z.string().url().default("http://localhost:8081"),
  IDP_ISSUER: z.string().default("http://localhost:8081"),
  IDP_AUDIENCE: z.string().default("bankagent"),
  STAFF_AUDIENCE: z.string().default("bankagent-staff"),
  AGENTCORE_INVOKE_URL: z.string().url().default("http://localhost:8080/invocations"),
  AWS_REGION: z.string().default("us-east-1"),
  TABLE_PREFIX: z.string().default("bankagent-dev"),
  DYNAMODB_ENDPOINT: z.string().url().optional(),
  DEMO_MODE: z.enum(["0", "1"]).default("0"),
  CHAT_ASYNC: z.enum(["0", "1"]).default("0"),
});
// fail fast in production rather than silently defaulting to localhost
const ProdEnv = Env.extend({ IDP_URL: z.string().url(), IDP_ISSUER: z.string().min(1) });
export type Env = z.infer<typeof Env>;

export function env(): Env {
  return (process.env.NODE_ENV === "production" ? ProdEnv : Env).parse({ ...process.env, DYNAMODB_ENDPOINT: process.env.DYNAMODB_ENDPOINT || undefined });
}
export const demoMode = () => env().DEMO_MODE === "1";
