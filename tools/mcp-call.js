// Roept een MCP-server (bijv. mcp-server-gsc) aan zonder Claude-koppeling.
// Gebruik: node tools/mcp-call.js <npm-pakket> [toolnaam] [json-argumenten]   (OUT=bestand.json om op te slaan)
const { spawn } = require('child_process');
const [pkg, tool, argsJson] = process.argv.slice(2);
const srv = spawn('cmd', ['/c', 'npx', '-y', pkg], { env: process.env, stdio: ['pipe', 'pipe', 'pipe'] });
let buf = '', id = 0; const wait = {};
srv.stdout.on('data', d => {
  buf += d;
  let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line.startsWith('{')) continue;
    try { const m = JSON.parse(line); if (m.id && wait[m.id]) { wait[m.id](m); delete wait[m.id]; } } catch (e) {}
  }
});
let err = ''; srv.stderr.on('data', d => { err += d; });
const call = (method, params) => new Promise(res => { const n = ++id; wait[n] = res; srv.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: n, method, params }) + '\n'); });
(async () => {
  const t = setTimeout(() => { console.log('TIMEOUT', err.slice(-400)); srv.kill(); process.exit(1); }, 90000);
  await call('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'test', version: '1' } });
  srv.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const tl = await call('tools/list', {});
  const names = (tl.result && tl.result.tools || []).map(x => x.name);
  console.log('Aantal tools:', names.length); console.log('Tools:', names.slice(0, 40).join(', '));
  if (process.env.SCHEMA) {
    const s = (tl.result.tools || []).find(x => x.name === process.env.SCHEMA);
    console.log('Schema:', JSON.stringify(s && s.inputSchema).slice(0, 1500));
  }
  if (tool) {
    // Argumenten als JSON, of '@bestand.json' om ze uit een bestand te lezen
    const raw = argsJson && argsJson.startsWith('@') ? require('fs').readFileSync(argsJson.slice(1), 'utf8') : argsJson;
    const r = await call('tools/call', { name: tool, arguments: raw ? JSON.parse(raw) : {} });
    const txt = JSON.stringify(r.result || r.error);
    if (process.env.OUT) {
      const t = r.result && r.result.content && r.result.content[0] && r.result.content[0].text;
      require('fs').writeFileSync(process.env.OUT, t || txt);
      console.log('Opgeslagen in', process.env.OUT, '(' + (t || txt).length + ' tekens)');
    } else {
      console.log('Resultaat', tool + ':', txt.slice(0, 1500));
    }
  }
  clearTimeout(t); srv.kill(); process.exit(0);
})();
