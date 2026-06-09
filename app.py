import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   OAuth2.0 Authorization Server Simulator                    ║
║                                                              ║
║   Starting server on http://localhost:{port:<5d}             ║
║                                                              ║
║   Available endpoints:                                       ║
║   • GET  /                        - Dashboard                ║
║   • GET  /oauth/authorize           - Authorization Endpoint ║
║   • POST /oauth/token               - Token Endpoint         ║
║   • POST /oauth/introspect          - Introspect Endpoint    ║
║   • POST /oauth/revoke              - Revoke Endpoint        ║
║   • GET  /admin                     - Admin Panel            ║
║   • GET  /docs                      - API Documentation      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=port, debug=True)
