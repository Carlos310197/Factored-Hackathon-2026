const [httpDomain, realtimeDomain, token, channel] = process.argv.slice(2);
const b64url = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");
const auth = { host: httpDomain, Authorization: token };
const ws = new WebSocket(`wss://${realtimeDomain}/event/realtime`, ["aws-appsync-event-ws", `header-${b64url(auth)}`]);
ws.onopen = () => ws.send(JSON.stringify({ type: "connection_init" }));
ws.onmessage = (m) => {
  const msg = JSON.parse(String(m.data));
  console.log(msg.type, JSON.stringify(msg.errors ?? ""));
  if (msg.type === "connection_ack") ws.send(JSON.stringify({ type: "subscribe", id: crypto.randomUUID(), channel, authorization: auth }));
  if (msg.type === "subscribe_success" || msg.type === "subscribe_error") ws.close();
};
