// Empty locally; the deployment builder sets this meta tag for a separate game server.
export function webSocketEndpoint() {
  const configured = document.querySelector('meta[name="game-websocket"]')?.content.trim();
  return configured || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
}
