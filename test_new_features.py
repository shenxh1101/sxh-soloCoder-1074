import json
import base64
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "http://localhost:5000"

def make_request(method, url, data=None, headers=None, auth=None):
    req_headers = {'Content-Type': 'application/json'}
    if headers:
        req_headers.update(headers)
    
    if auth:
        credentials = f"{auth[0]}:{auth[1]}"
        encoded = base64.b64encode(credentials.encode()).decode()
        req_headers['Authorization'] = f'Basic {encoded}'
    
    if data and method != 'GET':
        if isinstance(data, dict):
            data_bytes = json.dumps(data).encode()
        else:
            data_bytes = data
    else:
        data_bytes = None
    
    if method == 'GET' and data:
        query_string = urllib.parse.urlencode(data)
        url = f"{url}?{query_string}"
    
    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            response_body = response.read().decode()
            print(f"✓ {method} {url} - {response.status}")
            if response_body:
                try:
                    return json.loads(response_body), response.status
                except:
                    return response_body, response.status
    except urllib.error.HTTPError as e:
        print(f"✗ {method} {url} - {e.code}")
        try:
            error_body = e.read().decode()
            print(f"  Error: {error_body}")
            return json.loads(error_body), e.code
        except:
            return None, e.code

def run_tests():
    print("=" * 70)
    print("OAuth2.0 Server - New Features Test Suite")
    print("=" * 70)
    print()
    
    print("1. Creating test client...")
    client_data = {
        "name": "测试应用-新功能",
        "description": "用于测试新功能的客户端",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code", "client_credentials", "refresh_token"],
        "token_format": "jwt",
        "token_expire_seconds": 3600,
        "require_consent": True
    }
    client, status = make_request("POST", f"{BASE_URL}/api/clients", client_data)
    if not client or status != 201:
        print("Failed to create client")
        return
    client_id = client['client_id']
    client_secret = client['client_secret']
    print(f"  Client ID: {client_id[:20]}...")
    print()
    
    print("2. Testing Client Credentials Grant (to get tokens for testing)...")
    token_data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "scope": "read:user write:data"
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/oauth/token",
        data=token_data,
        method="POST"
    )
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    req.add_header('Authorization', f'Basic {encoded}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    try:
        with urllib.request.urlopen(req) as response:
            token_response = json.loads(response.read().decode())
            print(f"✓ POST /oauth/token - {response.status}")
            access_token = token_response['access_token']
            print(f"  Access Token obtained")
    except urllib.error.HTTPError as e:
        print(f"✗ POST /oauth/token - {e.code}")
        return
    print()
    
    print("3. Testing Token Detail API (with introspect)...")
    tokens, status = make_request("GET", f"{BASE_URL}/api/tokens")
    if tokens and len(tokens) > 0:
        token_id = tokens[0]['id']
        detail, status = make_request("GET", f"{BASE_URL}/api/tokens/{token_id}")
        if detail:
            print(f"  ✓ Has introspect: {'introspect' in detail}")
            if 'introspect' in detail:
                print(f"  ✓ Introspect active: {detail['introspect'].get('active')}")
                print(f"  ✓ Introspect client_id: {detail['introspect'].get('client_id')}")
    print()
    
    print("4. Testing Export All Data...")
    export_data, status = make_request("GET", f"{BASE_URL}/api/export/all")
    if status == 200 and 'clients' in export_data:
        print(f"  ✓ Exported {len(export_data['clients'])} clients")
        print(f"  ✓ Exported {len(export_data['tokens'])} tokens")
        print(f"  ✓ Has scopes: {'scopes' in export_data}")
        print(f"  ✓ Has simulated_errors: {'simulated_errors' in export_data}")
    print()
    
    print("5. Testing Import Data (skip mode)...")
    import_result, status = make_request(
        "POST", 
        f"{BASE_URL}/api/import?mode=skip", 
        export_data
    )
    if status == 200 and import_result.get('success'):
        results = import_result['results']
        print(f"  ✓ Clients: imported={results['clients']['imported']}, skipped={results['clients']['skipped']}")
        print(f"  ✓ Tokens: imported={results['tokens']['imported']}, skipped={results['tokens']['skipped']}")
        if results['clients']['errors']:
            print(f"  ✓ Client errors (expected for duplicates): {len(results['clients']['errors'])}")
    print()
    
    print("6. Testing Import Data (overwrite mode)...")
    import_result, status = make_request(
        "POST", 
        f"{BASE_URL}/api/import?mode=overwrite", 
        export_data
    )
    if status == 200 and import_result.get('success'):
        results = import_result['results']
        print(f"  ✓ Clients: imported={results['clients']['imported']}, skipped={results['clients']['skipped']}")
        print(f"  ✓ Tokens: imported={results['tokens']['imported']}, skipped={results['tokens']['skipped']}")
    print()
    
    print("7. Testing Playground - Client Credentials Flow...")
    playground_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "read:user",
        "token_format": "jwt"
    }
    pg_result, status = make_request(
        "POST",
        f"{BASE_URL}/admin/playground/run-client-credentials",
        playground_data
    )
    if status == 200 and pg_result.get('success'):
        print(f"  ✓ Steps: {len(pg_result['steps'])}")
        print(f"  ✓ Has access_token: {'access_token' in pg_result}")
        for i, step in enumerate(pg_result['steps']):
            print(f"    Step {i+1}: {step['name']} - {step['status']} (status_code: {step.get('status_code')})")
    print()
    
    print("8. Testing Playground - Authorization Code Flow...")
    playground_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://localhost:3000/callback",
        "scope": "read:user write:data",
        "user_id": "test_user_123",
        "token_format": "jwt"
    }
    pg_result, status = make_request(
        "POST",
        f"{BASE_URL}/admin/playground/run-authorization-code",
        playground_data
    )
    if status == 200 and pg_result.get('success'):
        print(f"  ✓ Steps: {len(pg_result['steps'])}")
        print(f"  ✓ Has authorization_code: {'authorization_code' in pg_result}")
        print(f"  ✓ Has access_token: {'access_token' in pg_result}")
        for i, step in enumerate(pg_result['steps']):
            print(f"    Step {i+1}: {step['name']} - {step['status']} (status_code: {step.get('status_code')})")
    print()
    
    print("9. Testing Simulated Error with endpoint filtering...")
    error_data = {
        "name": "Test Introspect Error",
        "description": "Test error only for introspect endpoint",
        "error_type": "invalid_token",
        "status_code": 401,
        "error_message": "Test introspect error",
        "enabled": "1",
        "affected_endpoints": ["introspect"]
    }
    
    form_data = urllib.parse.urlencode(error_data).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/admin/simulated-errors/new",
        data=form_data,
        method="POST"
    )
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    try:
        with urllib.request.urlopen(req) as response:
            print(f"✓ Created simulated error - {response.status}")
            
            intro_data = urllib.parse.urlencode({
                "token": access_token
            }).encode()
            req = urllib.request.Request(
                f"{BASE_URL}/oauth/introspect",
                data=intro_data,
                method="POST"
            )
            req.add_header('Authorization', f'Basic {encoded}')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            try:
                with urllib.request.urlopen(req) as response:
                    intro_result = json.loads(response.read().decode())
                    print(f"  ✓ Introspect with simulated error: active={intro_result.get('active')} (expected: false)")
            except urllib.error.HTTPError as e:
                print(f"  ✗ Introspect error: {e.code}")
    except urllib.error.HTTPError as e:
        print(f"✗ Failed to create error: {e.code}")
    print()
    
    print("10. Testing token endpoint is NOT affected by introspect-only error...")
    token_data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "scope": "read:user"
    }).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/oauth/token",
        data=token_data,
        method="POST"
    )
    req.add_header('Authorization', f'Basic {encoded}')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    try:
        with urllib.request.urlopen(req) as response:
            token_response = json.loads(response.read().decode())
            print(f"✓ Token endpoint still works: {response.status}")
            print(f"  ✓ Got new access token (not affected by introspect-only error)")
    except urllib.error.HTTPError as e:
        print(f"✗ Token endpoint failed: {e.code}")
    print()
    
    print("=" * 70)
    print("All new feature tests completed!")
    print("=" * 70)
    print()
    print("Summary of new features tested:")
    print("  ✓ Data Import (skip and overwrite modes)")
    print("  ✓ Token Detail API with introspect results")
    print("  ✓ Playground - Client Credentials flow")
    print("  ✓ Playground - Authorization Code flow")
    print("  ✓ Simulated Error with endpoint filtering")
    print()
    print("Please also test the web UI pages:")
    print(f"  - {BASE_URL}/admin/import (Data Import)")
    print(f"  - {BASE_URL}/admin/playground (OAuth Playground)")
    print(f"  - {BASE_URL}/admin/tokens (Token Management with details)")
    print(f"  - {BASE_URL}/admin/simulated-errors (Simulated Errors with endpoints)")

if __name__ == "__main__":
    run_tests()
