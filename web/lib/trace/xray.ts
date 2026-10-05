// Link from a trace block to its CloudWatch X-Ray trace. Only well-formed X-Ray ids pass,
// so a record can never inject an arbitrary URL.
const XRAY_ID = /^1-[0-9a-f]{8}-[0-9a-f]{24}$/;

export function xrayTraceUrl(traceId: string, region = "us-east-1"): string | null {
  if (!XRAY_ID.test(traceId)) return null;
  return `https://${region}.console.aws.amazon.com/cloudwatch/home?region=${region}#xray:traces/${traceId}`;
}
