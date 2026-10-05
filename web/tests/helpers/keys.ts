import { SignJWT, createLocalJWKSet, exportJWK, generateKeyPair } from "jose";

export const ISS = "http://idp.test";
export async function testKeys() {
  const { privateKey, publicKey } = await generateKeyPair("RS256");
  const jwk = { ...(await exportJWK(publicKey)), kid: "k1", alg: "RS256", use: "sig" };
  const getKey = createLocalJWKSet({ keys: [jwk] });
  const sign = (claims: Record<string, unknown>, aud: string, exp = "15m") =>
    new SignJWT(claims).setProtectedHeader({ alg: "RS256", kid: "k1" }).setIssuer(ISS).setAudience(aud)
      .setIssuedAt().setExpirationTime(exp).sign(privateKey);
  return { getKey, sign };
}
