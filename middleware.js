// Edge Middleware — HTTP Basic Auth voor het hele dashboard.
//
// Beschermt elke request (HTML, data.json, Excel, etc.) achter een
// browser-prompt. Credentials staan als Vercel env-vars:
//     BASIC_AUTH_USER       — gebruikersnaam
//     BASIC_AUTH_PASSWORD   — wachtwoord
//
// Configureer ze in Vercel: Project → Settings → Environment Variables
// (set voor Production + Preview). Daarna komt een redeploy.

export const config = {
  // Beveilig alles. Favicon en /_vercel/* (interne assets) blijven open.
  matcher: ['/((?!_vercel|favicon\\.ico).*)'],
};

export default function middleware(request) {
  const expectedUser = process.env.BASIC_AUTH_USER;
  const expectedPwd  = process.env.BASIC_AUTH_PASSWORD;

  // Fail-closed: zonder env-vars ingesteld blokkeert het dashboard sowieso.
  if (!expectedUser || !expectedPwd) {
    return new Response(
      'Configuration error: BASIC_AUTH_USER en BASIC_AUTH_PASSWORD ontbreken in Vercel env-vars.',
      { status: 503, headers: { 'content-type': 'text/plain; charset=utf-8' } }
    );
  }

  const header = request.headers.get('authorization') || '';
  if (header.startsWith('Basic ')) {
    try {
      const decoded = atob(header.slice(6));
      const idx = decoded.indexOf(':');
      if (idx >= 0) {
        const user = decoded.slice(0, idx);
        const pwd  = decoded.slice(idx + 1);
        if (user === expectedUser && pwd === expectedPwd) {
          return; // doorlaten
        }
      }
    } catch (_) { /* ongeldige base64 → val door naar 401 */ }
  }

  return new Response('Authentication required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Purple Media Dashboard", charset="UTF-8"',
      'content-type': 'text/plain; charset=utf-8',
    },
  });
}
